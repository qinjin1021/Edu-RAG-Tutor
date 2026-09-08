"""Embedding 模型懒加载与文本向量化。"""

from app.config import get_embedding_model_path

# 模型单例，首次调用时才加载（开发模式首次下载约 100MB，避免拖慢启动）
_model = None


def get_model():
    """懒加载 sentence-transformers 模型单例（打包模式加载内置模型）。"""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(get_embedding_model_path())
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量文本转向量。"""
    vectors = get_model().encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


def embed_query(text: str) -> list[float]:
    """单条查询文本转向量。"""
    return embed_texts([text])[0]
