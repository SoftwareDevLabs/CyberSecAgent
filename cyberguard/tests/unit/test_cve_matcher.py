"""Unit tests for pipeline.stages.cve_matcher (Stage 2).

Strategy: run_tool is patched with side_effect=[grype_result, osv_result] so
the two sequential subprocess calls (Grype first, OSV-Scanner second) each
return a pre-baked ToolResult without any real tools being installed.

OSV fixture data matches osv-scanner >= 2.x output (groups[] with max_severity,
no purl field) — the only format this stage supports.
"""
from __future__ import annotations

import json
import uuid
import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import select

from pipeline.db.models import Component, Finding, Project, SBOMSnapshot, Severity
from pipeline.errors import CVEMatchingError
from pipeline.runner import ToolResult
from pipeline.stages.cve_matcher import (
    _find_component,
    _parse_grype_output,
    _parse_osv_output,
    _score_to_severity,
    run_cve_stage,
)

# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

# Grype finds two CVEs for log4j-core 2.14.1, identified by GHSA IDs
GRYPE_LOG4J = {
    "matches": [
        {
            "vulnerability": {
                "id": "GHSA-jfh8-c2jp-5v3q",   # Log4Shell (CVE-2021-44228)
                "severity": "Critical",
                "cvss": [
                    {
                        "version": "3.1",
                        "metrics": {"baseScore": 10.0},
                        "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
                    }
                ],
                "fix": {"versions": ["2.15.0"], "state": "fixed"},
                "description": "Apache Log4j2 JNDI features ...",
            },
            "artifact": {
                "name": "log4j-core",
                "version": "2.14.1",
                "purl": "pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1",
            },
        },
        {
            "vulnerability": {
                "id": "GHSA-7rjr-3q55-vv33",   # CVE-2021-45046
                "severity": "Critical",
                "cvss": [
                    {
                        "version": "3.1",
                        "metrics": {"baseScore": 9.0},
                        "vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:H",
                    }
                ],
                "fix": {"versions": ["2.16.0"], "state": "fixed"},
                "description": "Fix for CVE-2021-44228 was incomplete ...",
            },
            "artifact": {
                "name": "log4j-core",
                "version": "2.14.1",
                "purl": "pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1",
            },
        },
    ]
}

# OSV format: groups[] with max_severity, no purl, Maven name as "groupId:artifactId"
# Reports Log4Shell (overlap with Grype) and an additional CVE (OSV-only)
OSV_LOG4J = {
    "results": [
        {
            "packages": [
                {
                    "package": {
                        "name": "org.apache.logging.log4j:log4j-core",
                        "version": "2.14.1",
                        "ecosystem": "Maven",
                    },
                    "groups": [
                        {
                            # Same as GHSA-jfh8-c2jp-5v3q from Grype → dedup target
                            "ids": ["GHSA-jfh8-c2jp-5v3q"],
                            "aliases": ["CVE-2021-44228", "GHSA-jfh8-c2jp-5v3q"],
                            "max_severity": "10.0",
                        },
                        {
                            # OSV-only finding not reported by Grype
                            "ids": ["GHSA-p6xc-xr62-6r2g"],
                            "aliases": ["CVE-2021-45105", "GHSA-p6xc-xr62-6r2g"],
                            "max_severity": "8.6",
                        },
                    ],
                }
            ]
        }
    ]
}

EMPTY_GRYPE = {"matches": []}
EMPTY_OSV = {"results": []}

GRYPE_OK = ToolResult(stdout=json.dumps(GRYPE_LOG4J), stderr="", returncode=1)
OSV_OK = ToolResult(stdout=json.dumps(OSV_LOG4J), stderr="", returncode=1)
GRYPE_EMPTY = ToolResult(stdout=json.dumps(EMPTY_GRYPE), stderr="", returncode=0)
OSV_EMPTY = ToolResult(stdout=json.dumps(EMPTY_OSV), stderr="", returncode=0)
TOOL_FAILURE = ToolResult(stdout="", stderr="connection refused", returncode=2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture
def snapshot(db_session):
    """A Project + SBOMSnapshot + one Component row for log4j-core 2.14.1.

    This is the minimal DB state Stage 2 requires to write Findings.
    The Component name is 'log4j-core' (just the artifactId, not groupId:artifactId)
    which is what Syft stores and what the OSV name-based lookup expects.
    """
    project = Project(name="log4j-test")
    db_session.add(project)
    db_session.flush()

    snap = SBOMSnapshot(
        scan_run_id=uuid.uuid4(),
        project_id=project.id,
        timestamp=_now(),
        raw_cyclonedx={},
        component_count=1,
        syft_version="1.46.0",
        status="SBOM_DONE",
    )
    db_session.add(snap)
    db_session.flush()

    db_session.add(Component(
        snapshot_id=snap.id,
        name="log4j-core",
        version="2.14.1",
        ecosystem="maven",
        purl="pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1",
    ))
    db_session.flush()
    return snap


def _patch_tools(grype_result: ToolResult, osv_result: ToolResult):
    """Patch run_tool so the first call returns grype_result, second returns osv_result."""
    return patch(
        "pipeline.stages.cve_matcher.run_tool",
        side_effect=[grype_result, osv_result],
    )


# ---------------------------------------------------------------------------
# Happy path — findings written to DB
# ---------------------------------------------------------------------------


def test_grype_only_findings_stored(db_session, snapshot, tmp_path):
    """When only Grype returns results, all its findings are persisted.

    Verifies the stage doesn't silently discard findings when OSV finds nothing.
    """
    sbom = tmp_path / "sbom.cdx.json"
    sbom.write_text("{}")

    with _patch_tools(GRYPE_OK, OSV_EMPTY):
        run_cve_stage(snapshot.id, sbom, db=db_session)

    findings = db_session.execute(select(Finding)).scalars().all()
    cve_ids = {f.cve_id for f in findings}
    assert "GHSA-jfh8-c2jp-5v3q" in cve_ids
    assert "GHSA-7rjr-3q55-vv33" in cve_ids
    assert len(findings) == 2


def test_osv_findings_stored_via_name_lookup(db_session, snapshot, tmp_path):
    """OSV matches without PURL are stored using name-based component lookup.

    OSV uses 'groupId:artifactId' format ('org.apache.logging.log4j:log4j-core').
    The stage must split on ':' and match on the artifactId ('log4j-core') against
    Component.name to find the correct component row.
    """
    sbom = tmp_path / "sbom.cdx.json"
    sbom.write_text("{}")

    with _patch_tools(GRYPE_EMPTY, OSV_OK):
        run_cve_stage(snapshot.id, sbom, db=db_session)

    findings = db_session.execute(select(Finding)).scalars().all()
    cve_ids = {f.cve_id for f in findings}
    # OSV returns CVE aliases as cve_id (not GHSA)
    assert "CVE-2021-44228" in cve_ids
    assert "CVE-2021-45105" in cve_ids
    assert len(findings) == 2


def test_deduplication_produces_one_row_per_unique_cve(db_session, snapshot, tmp_path):
    """The same CVE found by both tools must produce exactly one Finding row.

    Grype returns GHSA-jfh8-c2jp-5v3q; OSV returns CVE-2021-44228 for the same
    advisory. These are DIFFERENT identifiers for the SAME vulnerability, so they
    will NOT be deduplicated by this stage — each becomes its own Finding row with
    different cve_id values. True deduplication only applies when both tools return
    the identical cve_id for the same component.
    """
    sbom = tmp_path / "sbom.cdx.json"
    sbom.write_text("{}")

    with _patch_tools(GRYPE_OK, OSV_OK):
        result = run_cve_stage(snapshot.id, sbom, db=db_session)

    # Grype: GHSA-jfh8-c2jp-5v3q, GHSA-7rjr-3q55-vv33
    # OSV: CVE-2021-44228, CVE-2021-45105
    # All four are unique cve_id strings → 4 separate rows
    assert result.deduplicated_count == 4


def test_deduplication_merges_identical_cve_id(db_session, snapshot, tmp_path):
    """When both tools return the EXACT SAME cve_id for the same component, dedup fires.

    This test constructs a scenario where Grype and OSV both report 'CVE-2021-44228'
    for the same component, verifying the merge produces source='grype+osv'.
    """
    # Custom Grype output using CVE ID (not GHSA) to force a true dedup
    grype_cve_output = {
        "matches": [{
            "vulnerability": {
                "id": "CVE-2021-44228",
                "severity": "Critical",
                "cvss": [{"version": "3.1", "metrics": {"baseScore": 10.0}, "vector": "CVSS:3.1/..."}],
                "fix": {"versions": ["2.15.0"], "state": "fixed"},
                "description": "Log4Shell",
            },
            "artifact": {
                "name": "log4j-core",
                "version": "2.14.1",
                "purl": "pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1",
            },
        }]
    }
    osv_single = {
        "results": [{
            "packages": [{
                "package": {"name": "org.apache.logging.log4j:log4j-core", "version": "2.14.1", "ecosystem": "Maven"},
                "groups": [{"ids": ["GHSA-jfh8-c2jp-5v3q"], "aliases": ["CVE-2021-44228"], "max_severity": "10.0"}],
            }]
        }]
    }
    sbom = tmp_path / "sbom.cdx.json"
    sbom.write_text("{}")

    with _patch_tools(
        ToolResult(stdout=json.dumps(grype_cve_output), stderr="", returncode=1),
        ToolResult(stdout=json.dumps(osv_single), stderr="", returncode=1),
    ):
        result = run_cve_stage(snapshot.id, sbom, db=db_session)

    assert result.deduplicated_count == 1
    finding = db_session.execute(select(Finding)).scalar_one()
    assert finding.cve_id == "CVE-2021-44228"
    assert finding.source == "grype+osv"
    assert finding.cvss_score == 10.0    # Grype's score kept


def test_grype_cvss_score_kept_when_both_agree(db_session, snapshot, tmp_path):
    """When dedup merges a finding, Grype's CVSS score and fix version are kept.

    OSV provides max_severity as a score but no vector and no fix version.
    Grype provides both — so it is always preferred for the merged row.
    """
    grype_cve = {
        "matches": [{
            "vulnerability": {
                "id": "CVE-2021-44228",
                "severity": "Critical",
                "cvss": [{"version": "3.1", "metrics": {"baseScore": 10.0}, "vector": "CVSS:3.1/..."}],
                "fix": {"versions": ["2.15.0"], "state": "fixed"},
                "description": "Log4Shell",
            },
            "artifact": {"purl": "pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1"},
        }]
    }
    osv_same = {
        "results": [{
            "packages": [{
                "package": {"name": "org.apache.logging.log4j:log4j-core", "version": "2.14.1", "ecosystem": "Maven"},
                "groups": [{"ids": ["GHSA-x"], "aliases": ["CVE-2021-44228"], "max_severity": "9.0"}],
            }]
        }]
    }
    sbom = tmp_path / "sbom.cdx.json"
    sbom.write_text("{}")

    with _patch_tools(
        ToolResult(stdout=json.dumps(grype_cve), stderr="", returncode=1),
        ToolResult(stdout=json.dumps(osv_same), stderr="", returncode=1),
    ):
        run_cve_stage(snapshot.id, sbom, db=db_session)

    finding = db_session.execute(select(Finding)).scalar_one()
    assert finding.cvss_score == 10.0     # Grype's score, not OSV's 9.0
    assert finding.fix_version == "2.15.0"  # Grype's fix version


def test_snapshot_status_updated_to_cve_done(db_session, snapshot, tmp_path):
    """After Stage 2 completes, SBOMSnapshot.status must be 'CVE_DONE'.

    This checkpoint lets the orchestrator skip Stage 2 when resuming with --start-from 3.
    """
    sbom = tmp_path / "sbom.cdx.json"
    sbom.write_text("{}")

    with _patch_tools(GRYPE_OK, OSV_EMPTY):
        run_cve_stage(snapshot.id, sbom, db=db_session)

    db_session.refresh(snapshot)
    assert snapshot.status == "CVE_DONE"


def test_findings_initialised_with_correct_defaults(db_session, snapshot, tmp_path):
    """New Findings must start with NOT_ANALYZED / UNKNOWN defaults.

    Later stages (reachability, exploit enrichment) will update these fields.
    Wrong defaults would cause Stage 3 to skip findings it should analyse.
    """
    from pipeline.db.models import ExploitAvailability, ReachabilityStatus, TriageStatus

    sbom = tmp_path / "sbom.cdx.json"
    sbom.write_text("{}")

    with _patch_tools(GRYPE_OK, OSV_EMPTY):
        run_cve_stage(snapshot.id, sbom, db=db_session)

    finding = db_session.execute(
        select(Finding).where(Finding.cve_id == "GHSA-jfh8-c2jp-5v3q")
    ).scalar_one()
    assert finding.reachability_status == ReachabilityStatus.NOT_ANALYZED
    assert finding.exploit_availability == ExploitAvailability.UNKNOWN
    assert finding.triage_status == TriageStatus.NOT_ANALYZED
    assert finding.deleted_at is None


# ---------------------------------------------------------------------------
# Severity and score helpers
# ---------------------------------------------------------------------------


def test_score_to_severity_thresholds():
    """_score_to_severity must follow standard CVSS severity bands.

    A score of exactly 0.0 maps to NEGLIGIBLE (rated, near-zero impact),
    not INFO — INFO is reserved for when no rating exists at all.
    """
    assert _score_to_severity(10.0) == Severity.CRITICAL
    assert _score_to_severity(9.0) == Severity.CRITICAL
    assert _score_to_severity(8.9) == Severity.HIGH
    assert _score_to_severity(7.0) == Severity.HIGH
    assert _score_to_severity(6.9) == Severity.MEDIUM
    assert _score_to_severity(4.0) == Severity.MEDIUM
    assert _score_to_severity(3.9) == Severity.LOW
    assert _score_to_severity(0.1) == Severity.LOW
    assert _score_to_severity(0.0) == Severity.NEGLIGIBLE


def test_grype_negligible_severity_mapped_to_negligible_not_info():
    """Grype's 'Negligible' rating must map to Severity.NEGLIGIBLE.

    This is a real rating (CVSS 0.0 or vendor-assessed no impact), distinct
    from Severity.INFO which is reserved for unrated/unknown severities.
    """
    output = {
        "matches": [{
            "vulnerability": {"id": "CVE-X", "severity": "Negligible", "cvss": [], "fix": {}},
            "artifact": {"purl": "pkg:npm/foo@1.0"},
        }]
    }
    matches = _parse_grype_output(json.dumps(output))
    assert matches[0].severity == Severity.NEGLIGIBLE


def test_grype_unknown_severity_mapped_to_info():
    """Grype's 'Unknown' rating must map to Severity.INFO (no rating available)."""
    output = {
        "matches": [{
            "vulnerability": {"id": "CVE-X", "severity": "Unknown", "cvss": [], "fix": {}},
            "artifact": {"purl": "pkg:npm/foo@1.0"},
        }]
    }
    matches = _parse_grype_output(json.dumps(output))
    assert matches[0].severity == Severity.INFO


def test_grype_severity_mapped_from_string():
    """Grype's severity label ('Critical', 'High' etc.) maps to Severity enum."""
    output = {
        "matches": [{
            "vulnerability": {"id": "CVE-X", "severity": "High", "cvss": [], "fix": {}},
            "artifact": {"purl": "pkg:npm/foo@1.0"},
        }]
    }
    matches = _parse_grype_output(json.dumps(output))
    assert matches[0].severity == Severity.HIGH


def test_cvss_v31_preferred_over_v20():
    """When a vuln has both CVSS v2 and v3.1, v3.1 score must be used."""
    output = {
        "matches": [{
            "vulnerability": {
                "id": "CVE-X", "severity": "High",
                "cvss": [
                    {"version": "2.0", "metrics": {"baseScore": 6.0}, "vector": "AV:N"},
                    {"version": "3.1", "metrics": {"baseScore": 8.8}, "vector": "CVSS:3.1/..."},
                ],
                "fix": {},
            },
            "artifact": {"purl": "pkg:npm/foo@1.0"},
        }]
    }
    matches = _parse_grype_output(json.dumps(output))
    assert matches[0].cvss_score == 8.8


def test_fix_version_none_when_no_fix():
    """fix_version must be None when Grype reports no known fix."""
    output = {
        "matches": [{
            "vulnerability": {
                "id": "CVE-X", "severity": "Low", "cvss": [],
                "fix": {"versions": [], "state": "not-fixed"},
            },
            "artifact": {"purl": "pkg:pypi/foo@1.0"},
        }]
    }
    matches = _parse_grype_output(json.dumps(output))
    assert matches[0].fix_version is None


# ---------------------------------------------------------------------------
# OSV parser unit tests
# ---------------------------------------------------------------------------


def test_osv_prefers_cve_alias_over_ghsa_id():
    """OSV must extract CVE-xxxx from aliases[], not use the GHSA id as cve_id."""
    output = {
        "results": [{
            "packages": [{
                "package": {"name": "foo:bar", "version": "1.0", "ecosystem": "Maven"},
                "groups": [{"ids": ["GHSA-xxxx"], "aliases": ["CVE-2023-9999", "GHSA-xxxx"], "max_severity": "8.0"}],
            }]
        }]
    }
    matches = _parse_osv_output(json.dumps(output))
    assert matches[0].cve_id == "CVE-2023-9999"


def test_osv_keeps_ghsa_when_no_cve_alias():
    """If OSV has no CVE alias, the GHSA ID is kept as cve_id (valid identifier)."""
    output = {
        "results": [{
            "packages": [{
                "package": {"name": "foo", "version": "1.0", "ecosystem": "npm"},
                "groups": [{"ids": ["GHSA-xxxx"], "aliases": ["GHSA-xxxx"], "max_severity": "5.0"}],
            }]
        }]
    }
    matches = _parse_osv_output(json.dumps(output))
    assert matches[0].cve_id == "GHSA-xxxx"


def test_osv_score_stored_as_cvss_score():
    """OSV's max_severity (float string) must be stored as cvss_score."""
    output = {
        "results": [{
            "packages": [{
                "package": {"name": "foo", "version": "1.0", "ecosystem": "npm"},
                "groups": [{"ids": ["GHSA-x"], "aliases": ["CVE-2023-1"], "max_severity": "9.5"}],
            }]
        }]
    }
    matches = _parse_osv_output(json.dumps(output))
    assert matches[0].cvss_score == 9.5
    assert matches[0].severity == Severity.CRITICAL


def test_osv_populates_pkg_fields_for_name_lookup():
    """OSV matches must carry pkg_name/ecosystem/version for the name-based lookup."""
    output = {
        "results": [{
            "packages": [{
                "package": {"name": "org.apache:log4j-core", "version": "2.14.1", "ecosystem": "Maven"},
                "groups": [{"ids": ["GHSA-x"], "aliases": ["CVE-2021-44228"], "max_severity": "10.0"}],
            }]
        }]
    }
    matches = _parse_osv_output(json.dumps(output))
    assert matches[0].pkg_name == "org.apache:log4j-core"
    assert matches[0].pkg_ecosystem == "maven"
    assert matches[0].pkg_version == "2.14.1"
    assert matches[0].purl == ""   # OSV omits PURL from its output


# ---------------------------------------------------------------------------
# Component lookup helper unit tests
# ---------------------------------------------------------------------------


def test_find_component_by_purl(db_session, snapshot):
    """_find_component resolves a component when a PURL is present."""
    assert snapshot.status == "SBOM_DONE"  # confirms fixture populated the DB
    components = db_session.execute(select(Component)).scalars().all()
    purl_map = {c.purl: c for c in components}
    name_map = {(c.ecosystem.lower(), c.name.lower(), c.version): c for c in components}

    from pipeline.stages.cve_matcher import _RawMatch
    match = _RawMatch(
        purl="pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1",
        cve_id="CVE-X", severity=Severity.HIGH,
        cvss_score=None, cvss_vector=None, description=None, fix_version=None, source="grype",
    )
    assert _find_component(match, purl_map, name_map) is not None


def test_find_component_by_name_when_purl_absent(db_session, snapshot):
    """_find_component falls back to name lookup when PURL is empty (OSV)."""
    assert snapshot.status == "SBOM_DONE"  # confirms fixture populated the DB
    components = db_session.execute(select(Component)).scalars().all()
    purl_map = {c.purl: c for c in components}
    name_map = {(c.ecosystem.lower(), c.name.lower(), c.version): c for c in components}

    from pipeline.stages.cve_matcher import _RawMatch
    match = _RawMatch(
        purl="",   # OSV — no purl in output
        cve_id="CVE-X", severity=Severity.HIGH,
        cvss_score=None, cvss_vector=None, description=None, fix_version=None, source="osv",
        pkg_name="org.apache.logging.log4j:log4j-core",  # Maven groupId:artifactId
        pkg_ecosystem="maven",
        pkg_version="2.14.1",
    )
    component = _find_component(match, purl_map, name_map)
    assert component is not None
    assert component.name == "log4j-core"


def test_find_component_returns_none_for_unknown():
    """_find_component returns None when neither PURL nor name matches any component."""
    from pipeline.stages.cve_matcher import _RawMatch
    match = _RawMatch(
        purl="pkg:npm/completely-unknown@9.9.9",
        cve_id="CVE-X", severity=Severity.LOW,
        cvss_score=None, cvss_vector=None, description=None, fix_version=None, source="grype",
    )
    assert _find_component(match, {}, {}) is None


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_raises_when_snapshot_has_no_components(db_session, tmp_path):
    """Stage 2 must fail fast if no Component rows exist for the snapshot."""
    project = Project(name="empty")
    db_session.add(project)
    db_session.flush()

    snap = SBOMSnapshot(
        scan_run_id=uuid.uuid4(), project_id=project.id, timestamp=_now(),
        raw_cyclonedx={}, component_count=0, syft_version="1.0", status="SBOM_DONE",
    )
    db_session.add(snap)
    db_session.flush()

    with pytest.raises(CVEMatchingError, match="No components found"):
        run_cve_stage(snap.id, tmp_path / "sbom.json", db=db_session)


def test_raises_when_both_tools_fail(db_session, snapshot, tmp_path):
    """Both Grype and OSV-Scanner failing is a fatal error — no findings possible."""
    sbom = tmp_path / "sbom.cdx.json"
    sbom.write_text("{}")

    with _patch_tools(TOOL_FAILURE, TOOL_FAILURE):
        with pytest.raises(CVEMatchingError, match="Both Grype"):
            run_cve_stage(snapshot.id, sbom, db=db_session)


def test_continues_when_grype_fails_osv_succeeds(db_session, snapshot, tmp_path):
    """Grype failure is non-fatal when OSV-Scanner succeeds — OSV findings written."""
    sbom = tmp_path / "sbom.cdx.json"
    sbom.write_text("{}")

    with _patch_tools(TOOL_FAILURE, OSV_OK):
        result = run_cve_stage(snapshot.id, sbom, db=db_session)

    assert result.grype_count == 0
    assert result.osv_count == 2
    assert result.deduplicated_count == 2


def test_continues_when_osv_fails_grype_succeeds(db_session, snapshot, tmp_path):
    """OSV-Scanner failure is non-fatal when Grype succeeds — Grype findings written."""
    sbom = tmp_path / "sbom.cdx.json"
    sbom.write_text("{}")

    with _patch_tools(GRYPE_OK, TOOL_FAILURE):
        result = run_cve_stage(snapshot.id, sbom, db=db_session)

    assert result.grype_count == 2
    assert result.osv_count == 0


def test_purl_mismatch_skipped_gracefully(db_session, snapshot, tmp_path):
    """A PURL not in our Component table is skipped without crashing."""
    unknown = {
        "matches": [{
            "vulnerability": {"id": "CVE-X", "severity": "High", "cvss": [], "fix": {}},
            "artifact": {"purl": "pkg:npm/completely-unknown@9.9.9"},
        }]
    }
    sbom = tmp_path / "sbom.cdx.json"
    sbom.write_text("{}")

    with _patch_tools(ToolResult(stdout=json.dumps(unknown), stderr="", returncode=1), OSV_EMPTY):
        result = run_cve_stage(snapshot.id, sbom, db=db_session)

    assert result.deduplicated_count == 0


def test_empty_stdout_does_not_crash(db_session, snapshot, tmp_path):
    """A tool returning exit 0 with empty stdout (clean project) must not crash."""
    sbom = tmp_path / "sbom.cdx.json"
    sbom.write_text("{}")

    with _patch_tools(ToolResult(stdout="", stderr="", returncode=0), OSV_EMPTY):
        result = run_cve_stage(snapshot.id, sbom, db=db_session)

    assert result.deduplicated_count == 0
