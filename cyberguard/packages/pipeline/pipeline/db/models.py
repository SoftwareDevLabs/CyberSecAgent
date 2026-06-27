from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enum types
# ---------------------------------------------------------------------------


class Severity(str, enum.Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ReachabilityStatus(str, enum.Enum):
    NOT_ANALYZED = "NOT_ANALYZED"
    REACHABLE = "REACHABLE"
    NOT_REACHABLE = "NOT_REACHABLE"
    UNCERTAIN = "UNCERTAIN"


class ExploitAvailability(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    NO_KNOWN_EXPLOIT = "NO_KNOWN_EXPLOIT"
    POC_EXISTS = "POC_EXISTS"
    WEAPONIZED = "WEAPONIZED"


class TriageStatus(str, enum.Enum):
    NOT_ANALYZED = "NOT_ANALYZED"
    TRIAGED_ACCEPTED = "TRIAGED_ACCEPTED"
    TRIAGED_FP = "TRIAGED_FP"
    TRIAGED_DEFERRED = "TRIAGED_DEFERRED"


# ---------------------------------------------------------------------------
# Core pipeline tables
# ---------------------------------------------------------------------------


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    repo_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    sbom_snapshots: Mapped[list[SBOMSnapshot]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class SBOMSnapshot(Base):
    __tablename__ = "sbom_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_run_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), nullable=False, unique=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_cyclonedx: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    component_count: Mapped[int] = mapped_column(Integer, nullable=False)
    syft_version: Mapped[str] = mapped_column(String(32), nullable=False)
    # Pipeline checkpoint: PENDING→SBOM_DONE→CVE_DONE→REACH_DONE→EXPLOIT_DONE→COMPLETE
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")

    project: Mapped[Project] = relationship(back_populates="sbom_snapshots")
    components: Mapped[list[Component]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )
    findings: Mapped[list[Finding]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )


class Component(Base):
    __tablename__ = "components"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        ForeignKey("sbom_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    ecosystem: Mapped[str] = mapped_column(String(64), nullable=False)
    purl: Mapped[str] = mapped_column(Text, nullable=False)
    cpe: Mapped[str | None] = mapped_column(Text)

    snapshot: Mapped[SBOMSnapshot] = relationship(back_populates="components")
    findings: Mapped[list[Finding]] = relationship(
        back_populates="component", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("snapshot_id", "purl", name="uq_component_snapshot_purl"),
        Index("ix_component_ecosystem_name_version", "ecosystem", "name", "version"),
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    component_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Denormalized FK for fast per-scan queries (avoids join through components)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        ForeignKey("sbom_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    cve_id: Mapped[str] = mapped_column(String(32), nullable=False)
    cvss_score: Mapped[float | None] = mapped_column(Numeric(4, 1))
    cvss_vector: Mapped[str | None] = mapped_column(String(128))
    severity: Mapped[Severity] = mapped_column(sa.Enum(Severity), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # grype | osv | grype+osv
    description: Mapped[str | None] = mapped_column(Text)
    fix_version: Mapped[str | None] = mapped_column(String(128))

    reachability_status: Mapped[ReachabilityStatus] = mapped_column(
        sa.Enum(ReachabilityStatus),
        nullable=False,
        default=ReachabilityStatus.NOT_ANALYZED,
    )
    reachability_rationale: Mapped[str | None] = mapped_column(Text)
    reachability_agent_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    exploit_availability: Mapped[ExploitAvailability] = mapped_column(
        sa.Enum(ExploitAvailability),
        nullable=False,
        default=ExploitAvailability.UNKNOWN,
    )
    exploit_details: Mapped[str | None] = mapped_column(Text)

    triage_status: Mapped[TriageStatus] = mapped_column(
        sa.Enum(TriageStatus),
        nullable=False,
        default=TriageStatus.NOT_ANALYZED,
    )
    # Soft delete — never hard-delete findings that have TriageHistory rows
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    component: Mapped[Component] = relationship(back_populates="findings")
    snapshot: Mapped[SBOMSnapshot] = relationship(back_populates="findings")
    triage_history: Mapped[list[TriageHistory]] = relationship(
        back_populates="finding"
    )

    __table_args__ = (
        # One finding per (component, CVE) — deduplication happens before insert
        UniqueConstraint("component_id", "cve_id", name="uq_finding_component_cve"),
        Index("ix_finding_snapshot_severity", "snapshot_id", "severity"),
        Index("ix_finding_snapshot_reachability", "snapshot_id", "reachability_status"),
    )


class TriageHistory(Base):
    __tablename__ = "triage_history"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # ON DELETE RESTRICT — database refuses to delete a Finding with triage history,
    # protecting the ISO 21434 audit trail from accidental cascade deletion.
    finding_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        ForeignKey("findings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    old_status: Mapped[TriageStatus] = mapped_column(
        sa.Enum(TriageStatus), nullable=False
    )
    new_status: Mapped[TriageStatus] = mapped_column(
        sa.Enum(TriageStatus), nullable=False
    )
    rationale: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    finding: Mapped[Finding] = relationship(back_populates="triage_history")


# ---------------------------------------------------------------------------
# Exploit feed tables (populated by cyberguard db refresh-exploit-feeds)
# ---------------------------------------------------------------------------


class ExploitDbEntry(Base):
    __tablename__ = "exploit_db_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Exploit-DB's own ID
    # CVE IDs stored as JSON array: ["CVE-2021-44228", "CVE-2021-45046"]
    cve_ids: Mapped[list[str]] = mapped_column(sa.JSON, nullable=False, default=list)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    exploit_type: Mapped[str | None] = mapped_column(String(32))  # remote|local|dos|webapps
    platform: Mapped[str | None] = mapped_column(String(64))
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(Date)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class KevEntry(Base):
    __tablename__ = "kev_entries"

    cve_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    vendor_project: Mapped[str | None] = mapped_column(Text)
    product: Mapped[str | None] = mapped_column(Text)
    vulnerability_name: Mapped[str | None] = mapped_column(Text)
    date_added: Mapped[datetime | None] = mapped_column(Date)
    known_ransomware: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
