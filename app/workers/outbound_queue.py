import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import delete, select, update

from app.config import get_settings
from app.db import session_scope
from app.models.models import OutboundJob

logger = logging.getLogger(__name__)

BACKOFF_SECONDS = [60, 300, 1800, 7200, 43200, 86400]


def enqueue(url: str, payload: dict, external_id: str | None = None) -> int:
    with session_scope() as s:
        job = OutboundJob(
            url=url,
            payload=payload,
            external_id=external_id,
            max_attempts=len(BACKOFF_SECONDS) + 1,
        )
        s.add(job)
        s.flush()
        return job.id


def _now():
    return datetime.now(timezone.utc)


def _deliver_payload(url: str, payload: dict) -> tuple[bool, str | None, int | None]:
    try:
        r = httpx.post(url, json=payload, timeout=get_settings().http_timeout)
        if 200 <= r.status_code < 300:
            return True, None, r.status_code
        return False, f"HTTP {r.status_code}: {r.text[:300]}", r.status_code
    except Exception as e:
        return False, f"{type(e).__name__}: {e}", None


def process_due(limit: int = 20) -> int:
    with session_scope() as s:
        stmt = (
            select(
                OutboundJob.id,
                OutboundJob.url,
                OutboundJob.payload,
                OutboundJob.attempts,
                OutboundJob.max_attempts,
            )
            .where(OutboundJob.delivered_at.is_(None))
            .where(OutboundJob.next_attempt_at <= _now())
            .order_by(OutboundJob.next_attempt_at)
            .limit(limit)
        )
        jobs = s.execute(stmt).all()

    processed = 0
    for job_id, url, payload, attempts, max_attempts in jobs:
        locked = False
        with session_scope() as s:
            result = s.execute(
                update(OutboundJob)
                .where(OutboundJob.id == job_id)
                .where(OutboundJob.next_attempt_at <= _now())
                .where(OutboundJob.delivered_at.is_(None))
                .values(next_attempt_at=_now() + timedelta(seconds=30))
            )
            locked = result.rowcount == 1

        if not locked:
            continue

        ok, err, _status = _deliver_payload(url, payload)
        attempts += 1

        with session_scope() as s:
            job = s.get(OutboundJob, job_id)
            if job is None or job.delivered_at is not None:
                continue
            job.attempts = attempts
            if ok:
                job.delivered_at = _now()
                job.last_error = None
            else:
                job.last_error = err
                if attempts >= max_attempts:
                    job.next_attempt_at = _now() + timedelta(days=365)
                else:
                    delay = BACKOFF_SECONDS[min(attempts - 1, len(BACKOFF_SECONDS) - 1)]
                    job.next_attempt_at = _now() + timedelta(seconds=delay)
        processed += 1
    return processed


def cleanup_old_jobs(days: int = 30) -> int:
    cutoff = _now() - timedelta(days=days)
    with session_scope() as s:
        result = s.execute(
            delete(OutboundJob)
            .where(OutboundJob.delivered_at.is_(None))
            .where(OutboundJob.attempts >= OutboundJob.max_attempts)
            .where(OutboundJob.updated_at < cutoff)
        )
        return result.rowcount


async def run_worker_loop(stop_event=None) -> None:
    import asyncio

    cleanup_old_jobs()
    while True:
        if stop_event is not None and stop_event.is_set():
            return
        try:
            process_due()
        except Exception:
            logger.exception("worker loop: process_due failed")
        await asyncio.sleep(get_settings().worker_poll_seconds)


def run_worker_blocking() -> None:
    import time

    cleanup_old_jobs()
    while True:
        try:
            process_due()
        except Exception:
            logger.exception("worker loop: process_due failed")
        time.sleep(get_settings().worker_poll_seconds)
