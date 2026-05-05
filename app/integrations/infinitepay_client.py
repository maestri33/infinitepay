import httpx

from app.config import get_settings


class InfinitePayError(Exception):
    def __init__(self, message: str, payload: dict | None = None, status_code: int | None = None):
        super().__init__(message)
        self.payload = payload
        self.status_code = status_code


def _client() -> httpx.Client:
    s = get_settings()
    return httpx.Client(base_url=s.infinitepay_base_url, timeout=s.http_timeout)


def create_checkout_link(payload: dict) -> dict:
    with _client() as c:
        r = c.post("/links", json=payload)
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}

        if r.status_code >= 400:
            raise InfinitePayError(
                f"HTTP {r.status_code} from InfinitePay", payload=data, status_code=r.status_code
            )
        if data.get("success") is False:
            raise InfinitePayError(
                "InfinitePay returned success=false", payload=data, status_code=r.status_code
            )
        if not (data.get("url") or data.get("checkout_url")):
            raise InfinitePayError(
                "InfinitePay response missing checkout URL", payload=data, status_code=r.status_code
            )
        return data


def payment_check(*, handle: str, order_nsu: str, transaction_nsu: str, slug: str) -> dict:
    with _client() as c:
        r = c.post(
            "/payment_check",
            json={
                "handle": handle,
                "order_nsu": order_nsu,
                "transaction_nsu": transaction_nsu,
                "slug": slug,
            },
        )
        if r.status_code >= 400:
            try:
                data = r.json()
            except Exception:
                data = {"raw": r.text}
            raise InfinitePayError(
                f"HTTP {r.status_code} from InfinitePay payment_check",
                payload=data,
                status_code=r.status_code,
            )
        try:
            return r.json()
        except Exception:
            return {"success": False, "raw": r.text, "status_code": r.status_code}
