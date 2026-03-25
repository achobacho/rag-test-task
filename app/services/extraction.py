from openai import OpenAI

from app.config import Settings
from app.schemas import ContractExtraction


EXTRACTION_SYSTEM_PROMPT = """
You are a careful legal operations extraction assistant.

You will receive raw contract text. Extract only what is supported by the text.
If a field is unclear, return null or use the "unclear" enum and explain it in ambiguity_notes.
Do not invent contract terms.
Be conservative with confidence scores.
Only include ambiguity_notes for material uncertainties that could affect routing or policy review.
Do not list benign absences, optional commercial terms, or non-required clauses as ambiguities.
If the contract does not auto-renew, auto_renewal_term_months should be null and should not be listed as missing.
If the contract does not involve personal data, references_dpa should be false and should not be listed as missing or ambiguous.
""".strip()


class ContractExtractor:
    def __init__(self, settings: Settings):
        if settings.openai_api_key is None:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key.get_secret_value())

    def extract(self, document_text: str, attachment_name: str) -> ContractExtraction:
        if not document_text.strip():
            raise ValueError("No readable text could be extracted from the attachment.")

        response = self.client.responses.parse(
            model=self.settings.openai_model,
            input=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Attachment name: {attachment_name}\n\n"
                        "Extract the contract into the schema.\n\n"
                        f"Document text:\n{document_text}"
                    ),
                },
            ],
            text_format=ContractExtraction,
        )
        return response.output_parsed
