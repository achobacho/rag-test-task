import json

from openai import OpenAI

from app.config import Settings
from app.schemas import ContractExtraction, KnowledgeSnippet, PolicyReview


REVIEW_SYSTEM_PROMPT = """
You are a contract policy review assistant.

Use only the retrieved knowledge snippets as policy evidence.
Do not invent company policy that is not present in the snippets.
If the snippets are not sufficient, mark the relevant checks as unknown or warning.
Be conservative and route ambiguous cases to needs_review.
""".strip()


class PolicyReviewer:
    def __init__(self, settings: Settings):
        if settings.openai_api_key is None:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key.get_secret_value())

    def review(self, extraction: ContractExtraction, snippets: list[KnowledgeSnippet]) -> PolicyReview:
        snippet_text = "\n\n".join(
            f"[{snippet.doc_id}] {snippet.title}\n{snippet.snippet}" for snippet in snippets
        )
        response = self.client.responses.parse(
            model=self.settings.openai_model,
            input=[
                {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Evaluate this extracted contract against the retrieved policy snippets.\n\n"
                        f"Extracted contract JSON:\n{json.dumps(extraction.model_dump(), indent=2)}\n\n"
                        f"Retrieved snippets:\n{snippet_text}"
                    ),
                },
            ],
            text_format=PolicyReview,
        )
        return response.output_parsed

