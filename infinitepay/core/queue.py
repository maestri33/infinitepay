"""SQLite-backed outbound webhook queue with exponential backoff."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from infinitepay.db.models import OutboundJob
from infinitepay.db.session import session_scope
from infinitepay.settings import settings

BACKOFF_SECONDS = [60, 300, 1800, 7200, 43200, 86400]  # 1m, 5m, 30m, 2h, 12h, 24h


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


def _deliver(job: OutboundJob) -> tuple[bool, str | None, int | None]:
    try:
        r = httpx.post(job.url, json=job.payload, timeout=settings.http_timeout)
        if 200 <= r.status_code < 300:
            return True, None, r.status_code
        return False, f"HTTP {r.status_code}: {r.text[:300]}", r.status_code
    except Exception as e:
        return False, f"{type(e).__name__}: {e}", None


def process_due(limit: int = 20) -> int:
    """Process due jobs. Returns number processed."""
    processed = 0
    with session_scope() as s:
        stmt = (
            select(OutboundJob)
            .where(OutboundJob.delivered_at.is_(None))
            .where(OutboundJob.next_attempt_at <= _now())
            .order_by(OutboundJob.next_attempt_at)
            .limit(limit)
        )
        jobs = s.execute(stmt).scalars().all()
        for job in jobs:
            ok, err, _status = _deliver(job)
            job.attempts += 1
            if ok:
                job.delivered_at = _now()
                job.last_error = None
            else:
                job.last_error = err
                if job.attempts >= job.max_attempts:
                    # stays undelivered; won't be retried
                    job.next_attempt_at = _now() + timedelta(days=365)
                else:
                    delay = BACKOFF_SECONDS[min(job.attempts - 1, len(BACKOFF_SECONDS) - 1)]
                    job.next_attempt_at = _now() + timedelta(seconds=delay)
            processed += 1
    return processed


async def run_worker_loop(stop_event=None) -> None:
    import asyncio
    while True:
        if stop_event is not None and stop_event.is_set():
            return
        try:
            process_due()
        except Exception:
            pass
        await asyncio.sleep(settings.worker_poll_seconds)


def run_worker_blocking() -> None:
    import time
    while True:
        try:
            process_due()
        except Exception:
            pass
        time.sleep(settings.worker_poll_seconds)
