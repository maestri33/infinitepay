from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings
from app.exceptions import ValidationError


def _fernet() -> Fernet:
    return Fernet(get_settings().webhook_encryption_key.encode())


def encrypt_external_id(external_id: str) -> str:
    return _fernet().encrypt(external_id.encode()).decode()


def decrypt_external_id(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        raise ValidationError("external_id inválido ou token expirado") from None
