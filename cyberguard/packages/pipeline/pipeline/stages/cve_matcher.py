from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from pipeline.db.models import (
    Component,
    ExploitAvailability,
    Finding,
    ReachabilityStatus,
    SBOMSnapshot,
    Severity,
    TriageStatus,
)
from pipeline.errors import CVEMatchingError
from pipeline.runner import run_tool

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------


@dataclass
class CVEMatchResult:
    snapshot_id: uuid.UUID
    grype_count: int
    osv_count: int
    deduplicated_count: int


# ---------------------------------------------------------------------------
# Internal normalised match — shared shape for both tool outputs
# ---------------------------------------------------------------------------


@dataclass
class _RawMatch:
    purl: str
    cve_id: str
    severity: Severity
    cvss_score: float | None
    cvss_vector: str | None
    description: str | None
    fix_version: str | None
    source: str  # "grype" | "osv"  (mutated to "grype+osv" during dedup)
    # OSV omits PURL — these fields enable name-based component lookup as fallback
    pkg_name: str = field(default="")       # e.g. "org.apache.logging.log4j:log4j-core"
    pkg_ecosystem: str = field(default="")  # e.g. "maven"
    pkg_version: str = field(default="")    # e.g. "2.14.1"


# ---------------------------------------------------------------------------
# Severity helpers
# ---------------------------------------------------------------------------

_GRYPE_SEVERITY: dict[str, Severity] = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
    "negligible": Severity.NEGLIGIBLE,
    "unknown": Severity.INFO,
}


def _score_to_severity(score: float) -> Severity:
    """Map a numeric CVSS base score to a Severity enum value.

    A score of exactly 0.0 is NEGLIGIBLE (rated, near-zero impact) — not INFO,
    which is reserved for cases where no rating exists at all.
    """
    if score >= 9.0:
        return Severity.CRITICAL
    if score >= 7.0:
        return Severity.HIGH
    if score >= 4.0:
        return Severity.MEDIUM
    if score > 0.0:
        return Severity.LOW
    return Severity.NEGLIGIBLE


# ---------------------------------------------------------------------------
# Stage entrypoint
# ---------------------------------------------------------------------------


def run_cve_stage(
    snapshot_id: uuid.UUID,
    sbom_path: Path,
    *,
    db: Session,
    grype_executable: str = "grype",
    osv_executable: str = "osv-scanner",
    timeout: int = 300,
) -> CVEMatchResult:
    """Stage 2: match SBOM components against NVD/OSV, deduplicate, persist Findings.

    Both Grype and OSV-Scanner exit with code 1 when they find vulnerabilities —
    that is expected and treated as success. Only if both tools exit with an
    unexpected code does this stage raise CVEMatchingError.

    Deduplication key is (component_id, cve_id) — matching the DB unique constraint
    so the same CVE reported by both tools becomes one Finding with source='grype+osv'.
    """
    components = _load_components(db, snapshot_id)
    purl_to_component, name_to_component = _build_component_lookups(components)

    grype_matches, grype_ok, grype_exit = _run_grype(grype_executable, sbom_path, timeout)
    osv_matches, osv_ok, osv_exit = _run_osv(osv_executable, sbom_path, timeout)

    if not grype_ok and not osv_ok:
        raise CVEMatchingError(
            f"Both Grype (exit {grype_exit}) and OSV-Scanner (exit {osv_exit}) failed."
        )

    merged_matches, merged_components = _deduplicate_matches(
        grype_matches, osv_matches, purl_to_component, name_to_component
    )
    written = _persist_findings(db, snapshot_id, merged_matches, merged_components)
    _mark_cve_done(db, snapshot_id)

    return CVEMatchResult(
        snapshot_id=snapshot_id,
        grype_count=len(grype_matches),
        osv_count=len(osv_matches),
        deduplicated_count=written,
    )


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------


def _load_components(db: Session, snapshot_id: uuid.UUID) -> list[Component]:
    """Fetch all Component rows for a snapshot, or raise if there are none to match against."""
    components = db.execute(
        select(Component).where(Component.snapshot_id == snapshot_id)
    ).scalars().all()
    if not components:
        raise CVEMatchingError(f"No components found for snapshot {snapshot_id}")
    return list(components)


def _build_component_lookups(
    components: list[Component],
) -> tuple[dict[str, Component], dict[tuple[str, str, str], Component]]:
    """Build PURL-based and name-based lookup tables for resolving tool matches.

    OSV-Scanner omits PURL from its output. Maven packages use "groupId:artifactId" in
    OSV but we store only the artifactId as Component.name, so the name-based lookup is
    keyed on (ecosystem, simple_name, version) as a fallback for that case.
    """
    purl_to_component = {c.purl: c for c in components}
    name_to_component = {
        (c.ecosystem.lower(), c.name.lower(), c.version): c for c in components
    }
    return purl_to_component, name_to_component


def _run_grype(
    grype_executable: str,
    sbom_path: Path,
    timeout: int,
) -> tuple[list[_RawMatch], bool, int]:
    """Run Grype against the SBOM. Returns (matches, success, exit_code).

    Exit code 1 means vulnerabilities were found — that is success, not failure.
    """
    result = run_tool(
        [grype_executable, f"sbom:{sbom_path}", "-o", "json"],
        timeout_seconds=timeout,
    )
    if result.returncode not in (0, 1):
        log.warning("Grype exited %d: %s", result.returncode, result.stderr.strip())
        return [], False, result.returncode

    try:
        return _parse_grype_output(result.stdout), True, result.returncode
    except Exception as exc:
        log.warning("Failed to parse Grype output: %s", exc)
        return [], False, result.returncode


def _run_osv(
    osv_executable: str,
    sbom_path: Path,
    timeout: int,
) -> tuple[list[_RawMatch], bool, int]:
    """Run OSV-Scanner against the SBOM. Returns (matches, success, exit_code).

    Command is "osv-scanner scan --sbom <path>" (osv-scanner >= 2.x; the bare --sbom
    flag without the "scan" subcommand was removed). Exit code 1 means vulnerabilities
    were found — that is success, not failure.
    """
    result = run_tool(
        [osv_executable, "scan", "--sbom", str(sbom_path), "--format", "json"],
        timeout_seconds=timeout,
    )
    if result.returncode not in (0, 1):
        log.warning("OSV-Scanner exited %d: %s", result.returncode, result.stderr.strip())
        return [], False, result.returncode

    try:
        return _parse_osv_output(result.stdout), True, result.returncode
    except Exception as exc:
        log.warning("Failed to parse OSV-Scanner output: %s", exc)
        return [], False, result.returncode


def _deduplicate_matches(
    grype_matches: list[_RawMatch],
    osv_matches: list[_RawMatch],
    purl_to_component: dict[str, Component],
    name_to_component: dict[tuple[str, str, str], Component],
) -> tuple[dict[tuple[uuid.UUID, str], _RawMatch], dict[tuple[uuid.UUID, str], Component]]:
    """Resolve each match to its Component and merge by (component_id, cve_id).

    Using component_id (not purl) as the dedup axis correctly handles OSV-Scanner,
    which omits PURLs — both tools still refer to the same underlying component. A
    match that can't be resolved to a known component is skipped (and logged), since
    there is no Component row to attach the resulting Finding to.
    """
    merged_matches: dict[tuple[uuid.UUID, str], _RawMatch] = {}
    merged_components: dict[tuple[uuid.UUID, str], Component] = {}

    for match in grype_matches:
        component = _find_component(match, purl_to_component, name_to_component)
        if component is None:
            log.warning("No stored component for purl %r — skipping %s", match.purl, match.cve_id)
            continue
        key = (component.id, match.cve_id)
        merged_matches[key] = match
        merged_components[key] = component

    for match in osv_matches:
        component = _find_component(match, purl_to_component, name_to_component)
        if component is None:
            log.warning(
                "No stored component for %r / %r — skipping %s",
                match.purl, match.pkg_name, match.cve_id,
            )
            continue
        key = (component.id, match.cve_id)
        if key in merged_matches:
            merged_matches[key].source = "grype+osv"
        else:
            merged_matches[key] = match
            merged_components[key] = component

    return merged_matches, merged_components


def _persist_findings(
    db: Session,
    snapshot_id: uuid.UUID,
    merged_matches: dict[tuple[uuid.UUID, str], _RawMatch],
    merged_components: dict[tuple[uuid.UUID, str], Component],
) -> int:
    """Write one Finding row per deduplicated match. Returns the count written."""
    written = 0
    for key, match in merged_matches.items():
        component = merged_components[key]
        db.add(Finding(
            component_id=component.id,
            snapshot_id=snapshot_id,
            cve_id=match.cve_id,
            cvss_score=match.cvss_score,
            cvss_vector=match.cvss_vector,
            severity=match.severity,
            source=match.source,
            description=match.description,
            fix_version=match.fix_version,
            reachability_status=ReachabilityStatus.NOT_ANALYZED,
            exploit_availability=ExploitAvailability.UNKNOWN,
            triage_status=TriageStatus.NOT_ANALYZED,
        ))
        written += 1
    return written


def _mark_cve_done(db: Session, snapshot_id: uuid.UUID) -> None:
    """Advance the snapshot checkpoint so the orchestrator knows Stage 2 completed."""
    snapshot = db.get(SBOMSnapshot, snapshot_id)
    snapshot.status = "CVE_DONE"
    db.flush()


# ---------------------------------------------------------------------------
# Component lookup helper
# ---------------------------------------------------------------------------


def _find_component(
    match: _RawMatch,
    purl_to_component: dict[str, Component],
    name_to_component: dict[tuple[str, str, str], Component],
) -> Component | None:
    """Resolve a _RawMatch to its stored Component, PURL-first then name-based."""
    if match.purl:
        return purl_to_component.get(match.purl)
    if match.pkg_name:
        # Maven uses "groupId:artifactId" in OSV output; Component.name stores only artifactId
        simple_name = match.pkg_name.split(":")[-1].lower()
        return name_to_component.get((match.pkg_ecosystem, simple_name, match.pkg_version))
    return None


# ---------------------------------------------------------------------------
# Output parsers (private)
# ---------------------------------------------------------------------------


def _parse_grype_output(stdout: str) -> list[_RawMatch]:
    """Parse Grype JSON → list of normalised matches."""
    if not stdout.strip():
        return []

    data = json.loads(stdout)
    matches: list[_RawMatch] = []

    for match in data.get("matches", []):
        vuln = match.get("vulnerability", {})
        artifact = match.get("artifact", {})

        purl = artifact.get("purl", "")
        cve_id = vuln.get("id", "")
        if not purl or not cve_id:
            continue

        severity = _GRYPE_SEVERITY.get(vuln.get("severity", "unknown").lower(), Severity.INFO)

        # Prefer CVSS v3.1 → v3.0 → v2 (sort descending by version string)
        cvss_score: float | None = None
        cvss_vector: str | None = None
        for cvss in sorted(
            vuln.get("cvss", []),
            key=lambda x: x.get("version", "0"),
            reverse=True,
        ):
            score = cvss.get("metrics", {}).get("baseScore")
            if score is not None:
                cvss_score = float(score)
                cvss_vector = cvss.get("vector")
                break

        fix_info = vuln.get("fix", {})
        fix_versions = fix_info.get("versions", [])
        fix_version = (
            fix_versions[0]
            if fix_versions and fix_info.get("state") == "fixed"
            else None
        )

        matches.append(_RawMatch(
            purl=purl,
            cve_id=cve_id,
            severity=severity,
            cvss_score=cvss_score,
            cvss_vector=cvss_vector,
            description=vuln.get("description"),
            fix_version=fix_version,
            source="grype",
        ))

    return matches


def _parse_osv_output(stdout: str) -> list[_RawMatch]:
    """Parse OSV-Scanner JSON → list of normalised matches.

    Format: packages[].groups[] with ids/aliases and a numeric max_severity.
    No PURL or CVSS vector is provided — components are matched by name instead
    (see _find_component). CVE aliases are preferred over GHSA primary IDs.
    """
    if not stdout.strip():
        return []

    data = json.loads(stdout)
    matches: list[_RawMatch] = []

    for result in data.get("results", []):
        for pkg in result.get("packages", []):
            pkg_info = pkg.get("package", {})
            pkg_name = pkg_info.get("name", "")
            pkg_version = pkg_info.get("version", "")
            pkg_ecosystem = pkg_info.get("ecosystem", "").lower()

            for group in pkg.get("groups", []):
                cve_id = group.get("ids", [""])[0]
                for alias in group.get("aliases", []):
                    if alias.startswith("CVE-"):
                        cve_id = alias
                        break
                if not cve_id:
                    continue

                max_sev = group.get("max_severity")
                cvss_score = float(max_sev) if max_sev else None
                severity = _score_to_severity(cvss_score or 0.0)

                matches.append(_RawMatch(
                    purl=pkg_info.get("purl", ""),
                    cve_id=cve_id,
                    severity=severity,
                    cvss_score=cvss_score,
                    cvss_vector=None,
                    description=None,
                    fix_version=None,
                    source="osv",
                    pkg_name=pkg_name,
                    pkg_ecosystem=pkg_ecosystem,
                    pkg_version=pkg_version,
                ))

    return matches
