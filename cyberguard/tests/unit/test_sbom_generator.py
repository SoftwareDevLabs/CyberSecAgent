"""Unit tests for pipeline.stages.sbom_generator (Stage 1)."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import select

from pipeline.db.models import Component, Project, SBOMSnapshot
from pipeline.errors import SBOMGenerationError
from pipeline.runner import ToolResult
from pipeline.stages.sbom_generator import (
    _ecosystem_from_purl,
    _extract_syft_version,
    run_sbom_stage,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Minimal CycloneDX 1.5 JSON that mimics real Syft output for a log4j project.
LOG4J_CYCLONEDX = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.5",
    "metadata": {
        "timestamp": "2026-06-27T10:00:00Z",
        "tools": {
            "components": [
                {"name": "syft", "version": "1.4.1"},
            ]
        },
    },
    "components": [
        {
            "name": "log4j-core",
            "version": "2.14.1",
            "purl": "pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1",
            "cpe": "cpe:2.3:a:apache:log4j:2.14.1:*:*:*:*:*:*:*",
            "type": "library",
        },
        {
            "name": "log4j-api",
            "version": "2.14.1",
            "purl": "pkg:maven/org.apache.logging.log4j/log4j-api@2.14.1",
            "type": "library",
        },
    ],
}

# CycloneDX 1.4-style tools list (older Syft versions)
LOG4J_CYCLONEDX_V14_TOOLS = {
    **LOG4J_CYCLONEDX,
    "metadata": {
        "timestamp": "2026-06-27T10:00:00Z",
        "tools": [{"name": "syft", "version": "1.2.0"}],
    },
}


@pytest.fixture
def project(db_session):
    p = Project(name="log4j-test", version="2.14.1")
    db_session.add(p)
    db_session.flush()
    return p


def _write_sbom(tmp_path: Path, scan_run_id: uuid.UUID, data: dict) -> None:
    """Pre-write the fake CycloneDX file that the mocked Syft would produce."""
    (tmp_path / f"{scan_run_id}.cdx.json").write_text(json.dumps(data))


def _mock_syft_success(monkeypatch=None):
    """Return a context manager that patches run_tool with a successful no-op."""
    return patch(
        "pipeline.stages.sbom_generator.run_tool",
        return_value=ToolResult(stdout="", stderr="", returncode=0),
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_creates_snapshot_row(db_session, project, tmp_path):
    scan_run_id = uuid.uuid4()
    _write_sbom(tmp_path, scan_run_id, LOG4J_CYCLONEDX)

    with _mock_syft_success():
        result = run_sbom_stage(
            project.id, tmp_path, scan_run_id,
            db=db_session, output_dir=tmp_path,
        )

    snapshot = db_session.get(SBOMSnapshot, result.snapshot_id)
    assert snapshot is not None
    assert snapshot.scan_run_id == scan_run_id
    assert snapshot.project_id == project.id
    assert snapshot.component_count == 2
    assert snapshot.syft_version == "1.4.1"
    assert snapshot.status == "SBOM_DONE"


def test_creates_component_rows(db_session, project, tmp_path):
    scan_run_id = uuid.uuid4()
    _write_sbom(tmp_path, scan_run_id, LOG4J_CYCLONEDX)

    with _mock_syft_success():
        result = run_sbom_stage(
            project.id, tmp_path, scan_run_id,
            db=db_session, output_dir=tmp_path,
        )

    components = db_session.execute(
        select(Component).where(Component.snapshot_id == result.snapshot_id)
    ).scalars().all()

    assert len(components) == 2
    purls = {c.purl for c in components}
    assert "pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1" in purls
    assert "pkg:maven/org.apache.logging.log4j/log4j-api@2.14.1" in purls


def test_component_ecosystem_extracted_from_purl(db_session, project, tmp_path):
    scan_run_id = uuid.uuid4()
    _write_sbom(tmp_path, scan_run_id, LOG4J_CYCLONEDX)

    with _mock_syft_success():
        result = run_sbom_stage(
            project.id, tmp_path, scan_run_id,
            db=db_session, output_dir=tmp_path,
        )

    components = db_session.execute(
        select(Component).where(Component.snapshot_id == result.snapshot_id)
    ).scalars().all()
    assert all(c.ecosystem == "maven" for c in components)


def test_component_cpe_stored_when_present(db_session, project, tmp_path):
    scan_run_id = uuid.uuid4()
    _write_sbom(tmp_path, scan_run_id, LOG4J_CYCLONEDX)

    with _mock_syft_success():
        result = run_sbom_stage(
            project.id, tmp_path, scan_run_id,
            db=db_session, output_dir=tmp_path,
        )

    core = db_session.execute(
        select(Component).where(Component.name == "log4j-core")
    ).scalar_one()
    assert core.cpe == "cpe:2.3:a:apache:log4j:2.14.1:*:*:*:*:*:*:*"


def test_result_fields(db_session, project, tmp_path):
    scan_run_id = uuid.uuid4()
    _write_sbom(tmp_path, scan_run_id, LOG4J_CYCLONEDX)

    with _mock_syft_success():
        result = run_sbom_stage(
            project.id, tmp_path, scan_run_id,
            db=db_session, output_dir=tmp_path,
        )

    assert result.scan_run_id == scan_run_id
    assert result.component_count == 2
    assert result.syft_version == "1.4.1"
    assert result.raw_path == tmp_path / f"{scan_run_id}.cdx.json"


def test_syft_version_extracted_from_cyclonedx_14_tools_list(db_session, project, tmp_path):
    """CycloneDX 1.4 stores tools as a list, not a dict — both formats must work."""
    scan_run_id = uuid.uuid4()
    _write_sbom(tmp_path, scan_run_id, LOG4J_CYCLONEDX_V14_TOOLS)

    with _mock_syft_success():
        result = run_sbom_stage(
            project.id, tmp_path, scan_run_id,
            db=db_session, output_dir=tmp_path,
        )

    assert result.syft_version == "1.2.0"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_raises_if_project_not_found(db_session, tmp_path):
    with pytest.raises(SBOMGenerationError, match="not found"):
        run_sbom_stage(
            uuid.uuid4(), tmp_path, uuid.uuid4(),
            db=db_session, output_dir=tmp_path,
        )


def test_raises_if_syft_exits_nonzero(db_session, project, tmp_path):
    with patch(
        "pipeline.stages.sbom_generator.run_tool",
        return_value=ToolResult(stdout="", stderr="permission denied", returncode=1),
    ):
        with pytest.raises(SBOMGenerationError, match="Syft exited with code 1"):
            run_sbom_stage(
                project.id, tmp_path, uuid.uuid4(),
                db=db_session, output_dir=tmp_path,
            )


def test_raises_if_syft_writes_no_output_file(db_session, project, tmp_path):
    # Mock returns success but writes nothing to disk
    with patch(
        "pipeline.stages.sbom_generator.run_tool",
        return_value=ToolResult(stdout="", stderr="", returncode=0),
    ):
        with pytest.raises(SBOMGenerationError, match="produced no output file"):
            run_sbom_stage(
                project.id, tmp_path, uuid.uuid4(),
                db=db_session, output_dir=tmp_path,
            )


def test_raises_if_syft_writes_invalid_json(db_session, project, tmp_path):
    scan_run_id = uuid.uuid4()
    (tmp_path / f"{scan_run_id}.cdx.json").write_text("not json {{{")

    with _mock_syft_success():
        with pytest.raises(SBOMGenerationError, match="not valid JSON"):
            run_sbom_stage(
                project.id, tmp_path, scan_run_id,
                db=db_session, output_dir=tmp_path,
            )


def test_raises_if_zero_components(db_session, project, tmp_path):
    scan_run_id = uuid.uuid4()
    empty_sbom = {**LOG4J_CYCLONEDX, "components": []}
    _write_sbom(tmp_path, scan_run_id, empty_sbom)

    with _mock_syft_success():
        with pytest.raises(SBOMGenerationError, match="zero components"):
            run_sbom_stage(
                project.id, tmp_path, scan_run_id,
                db=db_session, output_dir=tmp_path,
            )


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("purl,expected", [
    ("pkg:maven/org.apache/log4j@2.14.1", "maven"),
    ("pkg:npm/lodash@4.17.21", "npm"),
    ("pkg:pypi/requests@2.28.0", "pypi"),
    ("pkg:alpine/openssl@1.0.1", "alpine"),
    ("pkg:generic/zlib@1.2.11", "generic"),
    ("", "generic"),
    ("not-a-purl", "generic"),
])
def test_ecosystem_from_purl(purl, expected):
    assert _ecosystem_from_purl(purl) == expected


def test_extract_syft_version_missing_metadata():
    assert _extract_syft_version({}) == "unknown"


def test_extract_syft_version_tools_without_syft():
    raw = {"metadata": {"tools": {"components": [{"name": "grype", "version": "1.0"}]}}}
    assert _extract_syft_version(raw) == "unknown"
