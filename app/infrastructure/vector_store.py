from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from chromadb.config import Settings as ChromaSettings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.vectorstores import VectorStoreRetriever

from app.core.settings import settings


@lru_cache(maxsize=1)
def _embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=settings.embed_model,
        encode_kwargs={"normalize_embeddings": True},
    )


import chromadb

@lru_cache(maxsize=32)
def _chroma_for_repo(repo_id: str) -> Chroma:
    client = chromadb.PersistentClient(path=settings.chroma_dir)
    return Chroma(
        client=client,
        collection_name=f"reporover_{repo_id}",
        embedding_function=_embeddings(),
    )


@dataclass(frozen=True)
class VectorStore:
    """LangChain Chroma wrapper for ingest-time upserts"""

    _chroma: Chroma

    @classmethod
    def from_settings(cls, repo_id: str) -> "VectorStore":
        return cls(_chroma=_chroma_for_repo(repo_id))

    def upsert_documents(self, ids: list[str], docs: list[str], metadatas: list[dict]) -> None:
        if not ids:
            return
        self._chroma.add_texts(texts=docs, metadatas=metadatas, ids=ids)

    def as_retriever(self, top_k: int) -> VectorStoreRetriever:
        return self._chroma.as_retriever(search_kwargs={"k": top_k})

    def get_documents_by_qns(self, qns: list[str]) -> list[str]:
        if not qns:
            return []
        try:
            results = self._chroma.get(where={"qualified_name": {"$in": qns}})
            return results.get("documents", []) or []
        except Exception:
            return []
