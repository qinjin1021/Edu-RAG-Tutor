"""聊天 SSE 流式路由。"""

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.tutor import socratic

router = APIRouter()


class ChatBody(BaseModel):
    session_id: int
    content: str


@router.post("/api/chat")
def chat(body: ChatBody):
    def gen():
        for event in socratic.handle_chat(body.session_id, body.content):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
