import json

import openai
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import CaseRecord
from app.schemas import EmailEnvelope, ProcessedCase, RoutingDecision
from app.services.attachments import store_attachment
from app.services.extraction import ContractExtractor
from app.services.rag import KnowledgeBase
from app.services.resend_client import ResendClient
from app.services.review import PolicyReviewer


def _route_case(extraction, review) -> RoutingDecision:
    reasons: list[str] = []
    hard_fail = any(check.status == "fail" for check in review.checks)
    uncertain = any(check.status in {"warning", "unknown"} for check in review.checks)
    relevant_missing_fields = []
    for field in extraction.missing_fields:
        if field == "auto_renewal_term_months" and extraction.auto_renews is False:
            continue
        if field == "references_dpa" and extraction.handles_personal_data is False:
            continue
        relevant_missing_fields.append(field)

    if relevant_missing_fields:
        reasons.append(f"Missing fields: {', '.join(relevant_missing_fields)}")
    if extraction.ambiguity_notes:
        reasons.append(f"Ambiguities noted: {', '.join(extraction.ambiguity_notes)}")
    if hard_fail:
        reasons.append("One or more policy checks failed.")
    if uncertain:
        reasons.append("At least one policy check was uncertain or warning-level.")
    if extraction.confidence < 0.8:
        reasons.append("Extraction confidence is below the auto-approval threshold.")
    if review.confidence < 0.8:
        reasons.append("Policy review confidence is below the auto-approval threshold.")

    if reasons:
        priority = "high" if hard_fail or review.overall_risk == "high" else "normal"
        return RoutingDecision(
            status="needs_review",
            reasons=reasons,
            review_priority=priority,
            human_action="Review extracted terms, confirm policy issues, and decide whether to approve or renegotiate.",
        )

    return RoutingDecision(
        status="approved",
        reasons=["Contract matched the current policy snippets with no unresolved issues."],
        review_priority="none",
        human_action="No manual review required.",
    )


def _calculate_case_confidence(extraction, review) -> float:
    score = min(extraction.confidence, review.confidence)

    for field in extraction.missing_fields:
        if field == "auto_renewal_term_months" and extraction.auto_renews is False:
            continue
        if field == "references_dpa" and extraction.handles_personal_data is False:
            continue
        score -= 0.08

    score -= min(len(extraction.ambiguity_notes), 3) * 0.06

    for check in review.checks:
        if check.status == "fail":
            score -= 0.22
        elif check.status == "warning":
            score -= 0.12
        elif check.status == "unknown":
            score -= 0.08

    if review.overall_risk == "medium":
        score -= 0.06
    elif review.overall_risk == "high":
        score -= 0.14

    return max(0.05, min(0.99, round(score, 2)))


class ContractPipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.extractor = ContractExtractor(settings)
        self.knowledge_base = KnowledgeBase(settings)
        self.reviewer = PolicyReviewer(settings)
        self.resend = ResendClient(settings) if settings.resend_api_key is not None else None

    def process_bytes(
        self,
        db: Session,
        envelope: EmailEnvelope,
        filename: str,
        content: bytes,
        content_type: str | None,
    ) -> ProcessedCase:
        stored = store_attachment(
            storage_dir=self.settings.storage_path,
            content=content,
            filename=filename,
            content_type=content_type,
        )

        def save_failed_case(message: str) -> ProcessedCase:
            record = CaseRecord(
                source=envelope.source,
                source_email_id=envelope.email_id,
                sender=envelope.sender,
                recipient=envelope.recipient,
                subject=envelope.subject,
                attachment_name=filename,
                attachment_type=content_type,
                stored_path=str(stored.stored_path),
                status="failed",
                confidence=0.0,
                error_message=message,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return ProcessedCase(
                case_id=record.id,
                envelope=envelope,
                routing=RoutingDecision(
                    status="failed",
                    reasons=[message],
                    review_priority="high",
                    human_action="Inspect the error, fix the external dependency, and retry the attachment.",
                ),
                stored_path=str(stored.stored_path),
            )

        if not stored.text_content.strip():
            return save_failed_case(
                "The attachment could be downloaded, but no readable text could be extracted."
            )
        try:
            extraction = self.extractor.extract(document_text=stored.text_content, attachment_name=filename)
            snippets = self.knowledge_base.search(extraction)
            review = self.reviewer.review(extraction, snippets)
            routing = _route_case(extraction, review)
            case_confidence = _calculate_case_confidence(extraction, review)

            record = CaseRecord(
                source=envelope.source,
                source_email_id=envelope.email_id,
                sender=envelope.sender,
                recipient=envelope.recipient,
                subject=envelope.subject,
                attachment_name=filename,
                attachment_type=content_type,
                stored_path=str(stored.stored_path),
                status=routing.status,
                confidence=case_confidence,
                extracted_json=json.dumps(extraction.model_dump()),
                rag_json=json.dumps([snippet.model_dump() for snippet in snippets]),
                review_json=json.dumps(review.model_dump()),
                routing_json=json.dumps(routing.model_dump()),
            )
            db.add(record)
            db.commit()
            db.refresh(record)

            return ProcessedCase(
                case_id=record.id,
                envelope=envelope,
                extraction=extraction,
                knowledge_matches=snippets,
                review=review,
                routing=routing,
                stored_path=str(stored.stored_path),
            )
        except openai.RateLimitError as exc:
            message = (
                "OpenAI returned insufficient_quota. Add API credits or increase the project spend limit, "
                "then retry this attachment."
            )
            if "rate limit" in str(exc).lower():
                message = "OpenAI rate limit was hit. Wait briefly and retry the attachment."
            return save_failed_case(message)
        except openai.APIError as exc:
            return save_failed_case(f"OpenAI API error: {exc}")
        except Exception as exc:
            return save_failed_case(f"Processing failed: {exc}")

    def process_resend_email(self, db: Session, email_id: str, envelope: EmailEnvelope) -> list[ProcessedCase]:
        if self.resend is None:
            raise RuntimeError("RESEND_API_KEY is not configured.")
        email_payload = self.resend.get_received_email(email_id)
        attachments = self.resend.download_processable_attachments(email_id=email_id, email_payload=email_payload)
        if not attachments:
            record = CaseRecord(
                source=envelope.source,
                source_email_id=email_id,
                sender=envelope.sender,
                recipient=envelope.recipient,
                subject=envelope.subject,
                attachment_name="(none)",
                attachment_type=None,
                stored_path="",
                status="failed",
                confidence=0.0,
                error_message="The email contained no processable non-inline attachments.",
            )
            db.add(record)
            db.commit()
            return []

        cases: list[ProcessedCase] = []
        for attachment in attachments:
            cases.append(
                self.process_bytes(
                    db=db,
                    envelope=envelope,
                    filename=attachment.filename,
                    content=attachment.content,
                    content_type=attachment.content_type,
                )
            )
        return cases
