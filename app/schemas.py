from typing import Literal

from pydantic import BaseModel, Field


DocumentType = Literal["msa", "nda", "sow", "vendor_agreement", "service_agreement", "other"]
LiabilityCapType = Literal["fees_paid_last_12_months", "fixed_amount", "unlimited", "unclear", "not_found"]
RoutingStatus = Literal["approved", "needs_review", "failed"]
CheckStatus = Literal["pass", "warning", "fail", "unknown"]
RiskLevel = Literal["low", "medium", "high"]


class EmailEnvelope(BaseModel):
    source: str
    email_id: str | None = None
    sender: str | None = None
    recipient: str | None = None
    subject: str | None = None


class ContractExtraction(BaseModel):
    document_type: DocumentType
    counterparty_name: str | None = None
    effective_date: str | None = None
    expiration_date: str | None = None
    governing_law: str | None = None
    auto_renews: bool | None = None
    auto_renewal_term_months: int | None = None
    termination_notice_days: int | None = None
    liability_cap_type: LiabilityCapType = "not_found"
    liability_cap_summary: str | None = None
    payment_terms_summary: str | None = None
    handles_personal_data: bool | None = None
    references_dpa: bool | None = None
    key_obligations: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    ambiguity_notes: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class KnowledgeSnippet(BaseModel):
    doc_id: str
    title: str
    snippet: str
    score: float


class PolicyCheck(BaseModel):
    rule_id: str
    title: str
    status: CheckStatus
    risk_level: RiskLevel
    rationale: str
    source_doc_ids: list[str] = Field(default_factory=list)


class PolicyReview(BaseModel):
    summary: str
    checks: list[PolicyCheck] = Field(default_factory=list)
    overall_risk: RiskLevel
    recommended_status: Literal["approved", "needs_review"]
    confidence: float = Field(ge=0, le=1)


class RoutingDecision(BaseModel):
    status: RoutingStatus
    reasons: list[str] = Field(default_factory=list)
    review_priority: Literal["none", "normal", "high"] = "none"
    human_action: str


class ProcessedCase(BaseModel):
    case_id: str
    envelope: EmailEnvelope
    extraction: ContractExtraction | None = None
    knowledge_matches: list[KnowledgeSnippet] = Field(default_factory=list)
    review: PolicyReview | None = None
    routing: RoutingDecision
    stored_path: str

