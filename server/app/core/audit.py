"""Helpers for recording transactional audit events."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def create_audit_log(
    db: Session,
    *,
    category: str,
    action: str,
    status: str,
    message: str,
    event_id: str | None = None,
    worker_id: int | None = None,
    gate_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Add an audit row to the caller's current database transaction."""

    row = AuditLog(
        category=category,
        action=action,
        status=status,
        message=message,
        event_id=event_id,
        worker_id=worker_id,
        gate_id=gate_id,
        metadata_json=json.dumps(
            metadata or {}, separators=(",", ":"), sort_keys=True, default=str
        ),
    )
    db.add(row)
    return row
