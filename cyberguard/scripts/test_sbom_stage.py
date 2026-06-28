"""
Smoke-test Stage 1 (SBOM generation) against a real test fixture using the
actual Syft binary. Run this after 'make install-tools' to verify the stage
works end-to-end.

Usage (from cyberguard/ directory):
    uv run python scripts/test_sbom_stage.py
    uv run python scripts/test_sbom_stage.py --fixture openssl
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test Stage 1 SBOM generation")
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
        default=str(ROOT / "cyberguard-reports" / "sbom-smoke-test"),
        help="Directory to write the SBOM file",
    )
    args = parser.parse_args()

    source_path = FIXTURES / args.fixture
    if not source_path.exists():
        print(f"ERROR: fixture not found at {source_path}", file=sys.stderr)
        sys.exit(1)

    # Lazy import so this script only needs the workspace installed
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker

    from pipeline.db.models import Base, Component, Project
    from pipeline.db.session import make_engine
    from pipeline.stages.sbom_generator import run_sbom_stage

    engine = make_engine(args.db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    scan_run_id = uuid.uuid4()
    output_dir = Path(args.output_dir)

    with Session() as db:
        # Create a throwaway project for this smoke test
        project = Project(
            name=f"smoke-test-{args.fixture}",
            version="test",
            repo_path=str(source_path),
        )
        db.add(project)
        db.flush()

        print(f"\n── Stage 1: SBOM generation ──")
        print(f"  Fixture  : {source_path}")
        print(f"  Scan ID  : {scan_run_id}")
        print(f"  Database : {args.db_url}")
        print()

        result = run_sbom_stage(
            project.id,
            source_path,
            scan_run_id,
            db=db,
            output_dir=output_dir,
        )
        db.commit()

    print(f"✓ SBOM generated successfully")
    print(f"  Components found : {result.component_count}")
    print(f"  Syft version     : {result.syft_version}")
    print(f"  Snapshot ID      : {result.snapshot_id}")
    print(f"  SBOM file        : {result.raw_path}")
    print()

    # Show what was stored
    with Session() as db:
        components = db.execute(
            sa.select(Component).where(Component.snapshot_id == result.snapshot_id)
        ).scalars().all()
        print(f"Components written to database ({len(components)} rows):")
        for c in components:
            print(f"  {c.ecosystem:10s}  {c.name}@{c.version}")
            if c.cpe:
                print(f"             CPE: {c.cpe}")


if __name__ == "__main__":
    main()
