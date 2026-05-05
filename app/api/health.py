from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/ready")
def ready():
    return {"ok": True}
