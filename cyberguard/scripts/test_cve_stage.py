"""
Smoke-test Stage 2 (CVE matching) using the real Grype and OSV-Scanner binaries.

Runs Stage 1 first to produce a fresh SBOM, then feeds it into Stage 2.
Both stages write to the dev SQLite database so you can inspect the rows.

Usage (from cyberguard/ directory):
    uv run python scripts/test_cve_stage.py
    uv run python scripts/test_cve_stage.py --fixture openssl
    uv run python scripts/test_cve_stage.py --skip-stage1  # reuse last SBOM

Prerequisites:
    brew install syft grype osv-scanner
    OR: bash scripts/install-tools.sh
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test Stage 2 CVE matching")
    parser.add_argument(
        "--fixture",
        default="log4j",
        choices=["log4j", "openssl"],
        help="Which test fixture to scan (default: log4j)",
    )
    parser.add_argument(
        "--db-url",
        default="sqlite:///./cyberguard-dev.db",
        help="SQLAlchemy database URL",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "cyberguard-reports" / "cve-smoke-test"),
        help="Directory to write the SBOM file",
    )
    parser.add_argument(
        "--skip-stage1",
        action="store_true",
        help="Reuse the most recent SBOM snapshot from the DB instead of scanning again",
    )
    args = parser.parse_args()

    # Verify external tools are available before touching the DB
    _check_tool("grype")
    _check_tool("osv-scanner")
    if not args.skip_stage1:
        _check_tool("syft")

    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker

    from pipeline.db.models import Base, Component, Finding, Project, SBOMSnapshot
    from pipeline.db.session import make_engine
    from pipeline.stages.sbom_generator import run_sbom_stage
    from pipeline.stages.cve_matcher import run_cve_stage

    engine = make_engine(args.db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    output_dir = Path(args.output_dir)
    source_path = FIXTURES / args.fixture

    # ── Stage 1: generate SBOM (or reuse existing) ──────────────────────────
    if args.skip_stage1:
        with Session() as db:
            snap = db.execute(
                sa.select(SBOMSnapshot)
                .order_by(SBOMSnapshot.timestamp.desc())
            ).scalar()
            if snap is None:
                print("ERROR: no existing snapshots in DB. Run without --skip-stage1 first.")
                sys.exit(1)
            snapshot_id = snap.id
            scan_run_id = snap.scan_run_id
            # Reconstruct the SBOM path from the scan_run_id
            sbom_path = output_dir / f"{scan_run_id}.cdx.json"
            if not sbom_path.exists():
                print(f"ERROR: expected SBOM file not found at {sbom_path}")
                print("Run without --skip-stage1 to regenerate it.")
                sys.exit(1)

        print(f"\n── Reusing existing snapshot ──")
        print(f"  Snapshot ID : {snapshot_id}")
        print(f"  SBOM file   : {sbom_path}")
    else:
        if not source_path.exists():
            print(f"ERROR: fixture not found at {source_path}", file=sys.stderr)
            sys.exit(1)

        scan_run_id = uuid.uuid4()
        with Session() as db:
            project = Project(
                name=f"cve-smoke-{args.fixture}",
                version="test",
                repo_path=str(source_path),
            )
            db.add(project)
            db.flush()

            print(f"\n── Stage 1: SBOM generation ──")
            print(f"  Fixture : {source_path}")
            print(f"  Scan ID : {scan_run_id}")

            stage1 = run_sbom_stage(
                project.id,
                source_path,
                scan_run_id,
                db=db,
                output_dir=output_dir,
            )
            db.commit()

        snapshot_id = stage1.snapshot_id
        sbom_path = stage1.raw_path
        print(f"  ✓ {stage1.component_count} components found (Syft {stage1.syft_version})")
        print(f"  ✓ SBOM written to {sbom_path}")

    # ── Stage 2: CVE matching ────────────────────────────────────────────────
    print(f"\n── Stage 2: CVE matching ──")
    print(f"  Running Grype ...    ", end="", flush=True)

    with Session() as db:
        result = run_cve_stage(
            snapshot_id,
            sbom_path,
            db=db,
        )
        db.commit()

    print(f"done")
    print()
    print(f"  Grype matches      : {result.grype_count}")
    print(f"  OSV-Scanner matches: {result.osv_count}")
    print(f"  Deduplicated total : {result.deduplicated_count}")

    # ── Display findings ─────────────────────────────────────────────────────
    with Session() as db:
        findings = db.execute(
            sa.select(Finding, Component)
            .join(Component, Finding.component_id == Component.id)
            .where(Finding.snapshot_id == snapshot_id)
            .order_by(Finding.cvss_score.desc().nulls_last())
        ).all()

    if not findings:
        print("\n  No findings — the fixture appears clean.")
        return

    print(f"\n{'─' * 90}")
    print(f"  {'CVE ID':<20}  {'SEVERITY':<10}  {'CVSS':>5}  {'SOURCE':<12}  {'COMPONENT':<25}  FIX")
    print(f"{'─' * 90}")

    for finding, component in findings:
        cvss = f"{finding.cvss_score:.1f}" if finding.cvss_score else "  —  "
        fix = finding.fix_version or "—"
        comp = f"{component.name}@{component.version}"
        print(
            f"  {finding.cve_id:<20}  "
            f"{finding.severity.value:<10}  "
            f"{cvss:>5}  "
            f"{finding.source:<12}  "
            f"{comp:<25}  "
            f"{fix}"
        )

    print(f"{'─' * 90}")

    # Highlight critical findings
    critical = [f for f, _ in findings if f.severity.value == "CRITICAL"]
    if critical:
        print(f"\n  ⚠  {len(critical)} CRITICAL finding(s) require immediate attention.")

    print(f"\nAll findings written to database.")
    print(f"Inspect with:")
    print(f"  sqlite3 cyberguard-dev.db \"SELECT cve_id, severity, cvss_score, source, fix_version FROM findings;\"")


def _check_tool(name: str) -> None:
    """Exit with a clear message if a required external tool is not on PATH."""
    import shutil
    if shutil.which(name) is None:
        print(f"ERROR: '{name}' not found on PATH.")
        print(f"Install it with:  brew install {name}")
        print(f"Or run:           bash scripts/install-tools.sh")
        sys.exit(1)


if __name__ == "__main__":
    main()
