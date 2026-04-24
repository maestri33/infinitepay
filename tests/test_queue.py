def test_process_due_marks_delivered(monkeypatch):
    from infinitepay.core import queue
    from infinitepay.db.models import OutboundJob
    from infinitepay.db.session import init_db, session_scope
    from sqlalchemy import select

    init_db()
    queue.enqueue(
        "https://backend.test/hook/pedido-1/",
        {"external_id": "pedido-1", "paid": True},
        external_id="pedido-1",
    )

    calls = []

    def fake_deliver(url, payload):
        calls.append((url, payload))
        return True, None, 200

    monkeypatch.setattr(queue, "_deliver_payload", fake_deliver)

    assert queue.process_due() == 1
    assert calls == [("https://backend.test/hook/pedido-1/", {"external_id": "pedido-1", "paid": True})]

    with session_scope() as s:
        job = s.execute(select(OutboundJob)).scalar_one()
        assert job.attempts == 1
        assert job.delivered_at is not None
        assert job.last_error is None
