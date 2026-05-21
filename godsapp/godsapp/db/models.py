"""SQLAlchemy 2.x declarative models for GodsApp.

Severities and statuses use TEXT (not Enum) for portability between SQLite
and PostgreSQL without requiring custom enum migrations.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    target: Mapped[Optional[str]] = mapped_column(String(255))
    color: Mapped[str] = mapped_column(String(16), default="cream")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    scans: Mapped[list["Scan"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    tool: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(
        String(16), default="queued", index=True
    )  # queued | running | completed | failed | cancelled
    exit_code: Mapped[Optional[int]] = mapped_column(Integer)
    stdout: Mapped[Optional[str]] = mapped_column(Text)
    stderr: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    workspace: Mapped[Workspace] = relationship(back_populates="scans")
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(16), default="info", index=True
    )  # info | low | medium | high | critical
    host: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    port: Mapped[Optional[int]] = mapped_column(Integer)
    protocol: Mapped[Optional[str]] = mapped_column(String(16))
    service: Mapped[Optional[str]] = mapped_column(String(64))
    description: Mapped[Optional[str]] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    # Findings Manager fields
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    cvss_score: Mapped[Optional[float]] = mapped_column(Float)
    cve_ids: Mapped[Optional[str]] = mapped_column(String(255))
    mitre_technique: Mapped[Optional[str]] = mapped_column(String(64))
    tags: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    scan: Mapped[Scan] = relationship(back_populates="findings")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scan_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("scans.id", ondelete="SET NULL"), index=True
    )
    workspace_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    scan: Mapped[Optional[Scan]] = relationship(back_populates="evidence")
    custody: Mapped[list["CustodyChain"]] = relationship(
        back_populates="evidence", cascade="all, delete-orphan"
    )


class CustodyChain(Base):
    __tablename__ = "custody_chain"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    evidence_id: Mapped[str] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), index=True
    )
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    sha256_at_time: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    evidence: Mapped[Evidence] = relationship(back_populates="custody")


class FindingLink(Base):
    """Bidirectional link between two findings (dedup-merge, exploit chain, etc.).

    `kind` is free-form: "duplicate" | "chain" | "related" | "supersedes" | ...
    `a_id` and `b_id` are ordered so (a, b) is unique; callers should put the
    smaller UUID string first to avoid storing both (a→b) and (b→a).
    """
    __tablename__ = "finding_links"
    __table_args__ = (
        UniqueConstraint("a_id", "b_id", "kind", name="uq_finding_links_ab_kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    a_id: Mapped[str] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), index=True
    )
    b_id: Mapped[str] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32), default="related", index=True)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Plugin(Base):
    __tablename__ = "plugins"
    __table_args__ = (UniqueConstraint("module", name="uq_plugins_module"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    module: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="0.0.0")
    enabled: Mapped[bool] = mapped_column(default=True)
    manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    installed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    cron: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    actor: Mapped[str] = mapped_column(String(120), default="local-user")
    event: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target: Mapped[Optional[str]] = mapped_column(String(255))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )
