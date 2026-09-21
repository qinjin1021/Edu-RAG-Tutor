"""联网搜索路由：为用户寻找电子版学习资料。"""

from fastapi import APIRouter, HTTPException, Query

from app.kb.websearch import search_web

router = APIRouter()

_VALID_TYPES = {"all", "pdf", "ppt", "doc"}


@router.get("/api/search")
def search(
    q: str = Query(..., min_length=1, description="搜索词"),
    file_type: str = Query("all", alias="type", description="资料类型过滤"),
):
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="搜索词不能为空")
    if file_type not in _VALID_TYPES:
        file_type = "all"
    try:
        results = search_web(q, file_type)
    except Exception:
        raise HTTPException(status_code=502, detail="搜索服务暂时不可用，请稍后再试")
    return {"results": results}
