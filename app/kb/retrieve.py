"""知识库相似度检索与集合管理。"""

from typing import Optional

import chromadb

from app.config import get_paths, get_settings
from app.kb.embeddings import embed_query


def _collection_name(session_id: int) -> str:
    return f"kb_{session_id}"


def _client() -> chromadb.api.ClientAPI:
    return chromadb.PersistentClient(path=get_paths()["chroma_dir"])


def retrieve(session_id: int, query: str, top_k: Optional[int] = None) -> list[str]:
    """检索与 query 最相似的文本块，按距离升序；任何异常返回空列表。"""
    try:
        client = _client()
        name = _collection_name(session_id)
        if name not in [c.name for c in client.list_collections()]:
            return []
        collection = client.get_collection(name)
        count = collection.count()
        if count == 0:
            return []
        k = min(top_k or get_settings().top_k, count)
        result = collection.query(query_embeddings=[embed_query(query)], n_results=k)
        documents = result.get("documents") or []
        return list(documents[0]) if documents else []
    except Exception:
        return []


def delete_collection(session_id: int) -> None:
    """删除会话对应的知识库集合（不存在则忽略）。"""
    client = _client()
    name = _collection_name(session_id)
    if name in [c.name for c in client.list_collections()]:
        client.delete_collection(name)
