from __future__ import annotations

from sqlalchemy.orm import Session

from infinitepay.db.models import WebhookLog


def log_event(
    sess: Session,
    *,
    direction: str,
    kind: str,
    payload: dict,
    response: dict | None = None,
    status_code: int | None = None,
    external_id: str | None = None,
) -> WebhookLog:
    entry = WebhookLog(
        direction=direction,
        kind=kind,
        payload=payload or {},
        response=response,
        status_code=status_code,
        external_id=external_id,
    )
    sess.add(entry)
    sess.flush()
    return entry
