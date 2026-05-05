class DomainError(Exception):
    def __init__(self, message: str, code: int = 400, extra: dict | None = None):
        super().__init__(message)
        self.code = code
        self.extra = extra or {}


class NotFound(DomainError):  # noqa: N818
    def __init__(self, message: str, extra: dict | None = None):
        super().__init__(message, code=404, extra=extra)


class Conflict(DomainError):  # noqa: N818
    def __init__(self, message: str, extra: dict | None = None):
        super().__init__(message, code=409, extra=extra)


class ValidationError(DomainError):
    def __init__(self, message: str):
        super().__init__(message, code=422)


class IntegrationError(DomainError):
    def __init__(self, message: str, extra: dict | None = None):
        super().__init__(message, code=502, extra=extra)
