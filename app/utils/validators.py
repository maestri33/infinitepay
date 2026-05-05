import ipaddress
import re
import socket
from urllib.parse import urlparse

from email_validator import EmailNotValidError, validate_email

from app.exceptions import ValidationError


def normalize_handle(value: str) -> str:
    if not value:
        raise ValidationError("handle vazio")
    v = value.strip().lstrip("$")
    if not re.fullmatch(r"[A-Za-z0-9_\-\.]{2,64}", v):
        raise ValidationError(f"handle inválido: {value!r}")
    return v


def normalize_price(value) -> int:
    if value is None:
        raise ValidationError("price (centavos) é obrigatório")
    try:
        v = int(value)
    except (TypeError, ValueError) as e:
        raise ValidationError(f"price deve ser inteiro em centavos: {value!r}") from e
    if v <= 0:
        raise ValidationError("price deve ser > 0 (centavos)")
    return v


def normalize_quantity(value) -> int:
    if value is None:
        return 1
    try:
        v = int(value)
    except (TypeError, ValueError) as e:
        raise ValidationError(f"quantity inválida: {value!r}") from e
    if v <= 0:
        raise ValidationError("quantity deve ser > 0")
    return v


def normalize_description(value: str) -> str:
    v = (value or "").strip()
    if not v:
        raise ValidationError("description vazio")
    if len(v) > 255:
        raise ValidationError("description > 255 chars")
    return v


_URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)

_PRIVATE_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
]


def _is_private_host(hostname: str) -> bool:
    host = hostname.strip("[]")
    try:
        addr = ipaddress.ip_address(host)
        return addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_unspecified
    except ValueError:
        pass
    if host.lower() in ("localhost", "metadata.google.internal"):
        return True
    try:
        resolved = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _family, _type, _proto, _canon, addr in resolved:
            ip = addr[0]
            try:
                a = ipaddress.ip_address(ip)
                if a.is_loopback or a.is_private or a.is_link_local or a.is_unspecified:
                    return True
            except ValueError:
                pass
    except (socket.gaierror, OSError):
        pass
    return False


def normalize_url(value: str, field: str, allow_private: bool = False) -> str:
    v = (value or "").strip()
    if not v:
        raise ValidationError(f"{field} vazio")
    if not _URL_RE.match(v):
        raise ValidationError(f"{field} deve ser http(s): {value!r}")
    v = v.rstrip("/")
    if not allow_private:
        hostname = urlparse(v).hostname
        if hostname and _is_private_host(hostname):
            raise ValidationError(
                f"{field}: URL com hostname/IP privado ou loopback nao permitido: {hostname!r}"
            )
    return v


def normalize_email(value: str) -> str:
    try:
        info = validate_email(value, check_deliverability=False)
    except EmailNotValidError as e:
        raise ValidationError(f"email inválido: {e}") from e
    return info.normalized.lower()


def normalize_phone(value: str) -> str:
    v = re.sub(r"[^\d+]", "", value or "")
    if not v:
        raise ValidationError("phone_number vazio")
    if not v.startswith("+"):
        digits = re.sub(r"\D", "", v)
        if len(digits) in (10, 11):
            v = "+55" + digits
        else:
            raise ValidationError(f"phone_number inválido: {value!r}")
    if not re.fullmatch(r"\+\d{10,15}", v):
        raise ValidationError(f"phone_number inválido: {value!r}")
    return v


def normalize_cep(value: str) -> str:
    v = re.sub(r"\D", "", value or "")
    if len(v) != 8:
        raise ValidationError(f"CEP inválido (deve ter 8 dígitos): {value!r}")
    return v


def normalize_name(value: str) -> str:
    v = (value or "").strip()
    if len(v) < 2:
        raise ValidationError("name muito curto")
    return v


def normalize_external_id(value: str) -> str:
    v = (value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_\-\.]{1,128}", v):
        raise ValidationError(f"external_id inválido: {value!r}")
    return v


def normalize_customer(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("customer deve ser objeto")
    return {
        "name": normalize_name(data.get("name", "")),
        "email": normalize_email(data.get("email", "")),
        "phone_number": normalize_phone(data.get("phone_number", "")),
    }


def normalize_address(data: dict | None) -> dict | None:
    if data in (None, {}):
        return None
    if not isinstance(data, dict):
        raise ValidationError("address deve ser objeto")
    out = {
        "cep": normalize_cep(data.get("cep", "")),
        "street": (data.get("street") or "").strip(),
        "neighborhood": (data.get("neighborhood") or "").strip(),
        "number": str(data.get("number") or "").strip(),
    }
    complement = (data.get("complement") or "").strip()
    if complement:
        out["complement"] = complement
    for f in ("street", "neighborhood", "number"):
        if not out[f]:
            raise ValidationError(f"address.{f} é obrigatório")
    return out


def normalize_item(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("item deve ser objeto")
    return {
        "quantity": normalize_quantity(data.get("quantity", 1)),
        "price": normalize_price(data.get("price")),
        "description": normalize_description(data.get("description", "")),
    }


def normalize_items(value) -> list[dict]:
    if not isinstance(value, list) or not value:
        raise ValidationError("items deve ser lista não-vazia")
    return [normalize_item(it) for it in value]
