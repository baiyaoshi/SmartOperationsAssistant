from fastapi import APIRouter



router = APIRouter(tags=["health"])


@router.get("/api/v1/health")
async def health():
    return{"status":"ok","message":"服务运行中"}