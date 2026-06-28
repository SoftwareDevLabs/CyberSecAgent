from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from pipeline.db.models import Component, Project, SBOMSnapshot
from pipeline.errors import SBOMGenerationError
from pipeline.runner import run_tool


@dataclass
class SBOMResult:
    snapshot_id: uuid.UUID
    scan_run_id: uuid.UUID
    component_count: int
    syft_version: str
    raw_path: Path


def run_sbom_stage(
    project_id: uuid.UUID,
    source_path: Path,
    scan_run_id: uuid.UUID,
    *,
    db: Session,
    output_dir: Path,
    syft_executable: str = "syft",
    timeout: int = 300,
) -> SBOMResult:
    """Stage 1: invoke Syft to produce a CycloneDX SBOM, persist snapshot + components to DB.

    The orchestrator commits the session after this returns.
    """
    project = db.get(Project, project_id)
    if project is None:
        raise SBOMGenerationError(f"Project {project_id} not found in database")

    output_dir.mkdir(parents=True, exist_ok=True)
    sbom_path = output_dir / f"{scan_run_id}.cdx.json"

    result = run_tool(
        [syft_executable, str(source_path), "-o", f"cyclonedx-json={sbom_path}"],
        timeout_seconds=timeout,
    )
    if result.returncode != 0:
        raise SBOMGenerationError(
            f"Syft exited with code {result.returncode}: {result.stderr.strip()}"
        )

    if not sbom_path.exists():
        raise SBOMGenerationError(
            f"Syft exited 0 but produced no output file at {sbom_path}"
        )

    try:
        raw = json.loads(sbom_path.read_text())
    except json.JSONDecodeError as exc:
        raise SBOMGenerationError(f"Syft output is not valid JSON: {exc}") from exc

    components_data = raw.get("components", [])
    if not components_data:
        raise SBOMGenerationError(
            f"Syft found zero components in {source_path} — verify the source path is correct"
        )

    syft_version = _extract_syft_version(raw)

    snapshot = SBOMSnapshot(
        scan_run_id=scan_run_id,
        project_id=project_id,
        timestamp=datetime.now(timezone.utc),
        raw_cyclonedx=raw,
        component_count=len(components_data),
        syft_version=syft_version,
        status="PENDING",
    )
    db.add(snapshot)
    db.flush()  # materialise snapshot.id for Component FKs without committing

    for item in components_data:
        purl = item.get("purl", "")
        if not purl:
            # Construct a minimal PURL so the column stays non-null
            purl = f"pkg:generic/{item.get('name', 'unknown')}@{item.get('version', '0.0.0')}"

        db.add(Component(
            snapshot_id=snapshot.id,
            name=item.get("name", ""),
            version=item.get("version", "0.0.0"),
            ecosystem=_ecosystem_from_purl(purl),
            purl=purl,
            cpe=item.get("cpe"),
        ))

    snapshot.status = "SBOM_DONE"

    return SBOMResult(
        snapshot_id=snapshot.id,
        scan_run_id=scan_run_id,
        component_count=len(components_data),
        syft_version=syft_version,
        raw_path=sbom_path,
    )


def _ecosystem_from_purl(purl: str) -> str:
    """'pkg:maven/org.apache/foo@1.0' → 'maven'"""
    if not purl.startswith("pkg:"):
        return "generic"
    try:
        return purl[4:].split("/")[0].lower()
    except (IndexError, AttributeError):
        return "generic"


def _extract_syft_version(raw: dict) -> str:
    """Read Syft version from CycloneDX metadata.tools (handles 1.4 and 1.5 formats)."""
    try:
        tools = raw.get("metadata", {}).get("tools", {})
        # CycloneDX 1.5+: tools is {"components": [...]}
        if isinstance(tools, dict):
            for comp in tools.get("components", []):
                if comp.get("name", "").lower() == "syft":
                    return comp.get("version", "unknown")
        # CycloneDX 1.4: tools is a list
        if isinstance(tools, list):
            for tool in tools:
                if tool.get("name", "").lower() == "syft":
                    return tool.get("version", "unknown")
    except (KeyError, AttributeError, TypeError):
        pass
    return "unknown"
