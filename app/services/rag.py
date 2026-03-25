import uuid
from pathlib import Path

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from app.config import Settings
from app.schemas import ContractExtraction, KnowledgeSnippet


class KnowledgeBase:
    collection_name = "contract_policy"

    def __init__(self, settings: Settings):
        if settings.openai_api_key is None:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key.get_secret_value())
        self.qdrant = QdrantClient(path=str(settings.qdrant_storage_path))
        settings.qdrant_storage_path.mkdir(parents=True, exist_ok=True)

    def _load_chunks(self) -> list[dict]:
        chunks: list[dict] = []
        for path in sorted(self.settings.knowledge_path.glob("*.md")):
            text = path.read_text(encoding="utf-8").strip()
            parts = [part.strip() for part in text.split("\n\n") if part.strip()]
            for index, part in enumerate(parts, start=1):
                chunks.append(
                    {
                        "doc_id": f"{path.stem}#{index}",
                        "title": path.stem.replace("_", " ").title(),
                        "content": part,
                    }
                )
        return chunks

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(model=self.settings.openai_embedding_model, input=texts)
        return [item.embedding for item in response.data]

    def ensure_index(self) -> None:
        chunks = self._load_chunks()
        if not chunks:
            return

        should_seed = False
        try:
            info = self.qdrant.get_collection(self.collection_name)
            points_count = getattr(info, "points_count", None)
            indexed_vectors = points_count or 0
            should_seed = indexed_vectors < len(chunks)
        except Exception:
            should_seed = True

        if should_seed:
            embeddings = self._embed_texts([chunk["content"] for chunk in chunks])
            try:
                self.qdrant.get_collection(self.collection_name)
            except Exception:
                self.qdrant.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=len(embeddings[0]), distance=Distance.COSINE),
                )
            points = []
            for chunk, embedding in zip(chunks, embeddings, strict=True):
                point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk["doc_id"]))
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "doc_id": chunk["doc_id"],
                            "title": chunk["title"],
                            "content": chunk["content"],
                        },
                    )
                )
            self.qdrant.upsert(collection_name=self.collection_name, points=points)

    def _build_query(self, extraction: ContractExtraction) -> str:
        terms = [
            extraction.counterparty_name or "",
            extraction.document_type,
            extraction.governing_law or "",
            extraction.liability_cap_type,
            extraction.liability_cap_summary or "",
            extraction.payment_terms_summary or "",
            "auto renewal",
            "limitation of liability",
            "fees paid last 12 months",
            "termination notice",
            "personal data",
            "data processing addendum",
            "approved counterparty",
        ]
        return " ".join(term for term in terms if term)

    def search(self, extraction: ContractExtraction, limit: int = 5) -> list[KnowledgeSnippet]:
        self.ensure_index()
        query = self._build_query(extraction)
        embedding = self._embed_texts([query])[0]
        response = self.qdrant.query_points(
            collection_name=self.collection_name,
            query=embedding,
            limit=limit,
            with_payload=True,
        )
        results = response.points
        snippets: list[KnowledgeSnippet] = []
        for result in results:
            payload = result.payload or {}
            snippets.append(
                KnowledgeSnippet(
                    doc_id=str(payload.get("doc_id", "")),
                    title=str(payload.get("title", "Knowledge Base")),
                    snippet=str(payload.get("content", "")),
                    score=float(result.score),
                )
            )
        return snippets
