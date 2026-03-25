import json
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, init_db
from app.models import CaseRecord
from app.schemas import EmailEnvelope
from app.services.pipeline import ContractPipeline


settings = get_settings()
app = FastAPI(title=settings.app_name)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")


@app.on_event("startup")
def startup() -> None:
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    settings.knowledge_path.mkdir(parents=True, exist_ok=True)
    settings.samples_path.mkdir(parents=True, exist_ok=True)
    init_db()


def get_pipeline() -> ContractPipeline:
    return ContractPipeline(settings)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    cases = db.scalars(select(CaseRecord).order_by(desc(CaseRecord.created_at)).limit(25)).all()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "cases": cases,
            "openai_configured": settings.openai_api_key is not None,
            "resend_configured": settings.resend_api_key is not None,
        },
    )


@app.get("/cases/{case_id}", response_class=HTMLResponse)
def case_detail(case_id: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    case = db.get(CaseRecord, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return templates.TemplateResponse(request, "case_detail.html", {"request": request, "case": case})


@app.post("/demo/process")
async def demo_process(
    db: Session = Depends(get_db),
    sender: str = Form(default="demo@local.test"),
    recipient: str = Form(default="contracts@local.test"),
    subject: str = Form(default="Demo contract review"),
    file: UploadFile = File(...),
) -> RedirectResponse:
    if settings.openai_api_key is None:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY is not configured.")

    content = await file.read()
    pipeline = get_pipeline()
    processed = pipeline.process_bytes(
        db=db,
        envelope=EmailEnvelope(
            source="demo_upload",
            sender=sender,
            recipient=recipient,
            subject=subject,
        ),
        filename=file.filename or "attachment",
        content=content,
        content_type=file.content_type,
    )
    return RedirectResponse(url=f"/cases/{processed.case_id}", status_code=303)


@app.post("/webhooks/resend")
async def resend_webhook(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    if settings.resend_api_key is None:
        raise HTTPException(status_code=400, detail="RESEND_API_KEY is not configured.")
    pipeline = get_pipeline()
    if pipeline.resend is None:
        raise HTTPException(status_code=400, detail="RESEND_API_KEY is not configured.")

    raw_payload = await request.body()
    headers = {key: value for key, value in request.headers.items()}
    event = pipeline.resend.verify_webhook(raw_payload=raw_payload, headers=headers)
    if event.get("type") != "email.received":
        return JSONResponse({"ignored": True, "reason": "Unsupported event type."})

    data = event["data"]
    envelope = EmailEnvelope(
        source="resend_webhook",
        email_id=data["email_id"],
        sender=data.get("from"),
        recipient=", ".join(data.get("to", [])),
        subject=data.get("subject"),
    )
    try:
        processed_cases = pipeline.process_resend_email(db=db, email_id=data["email_id"], envelope=envelope)
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse({"processed_case_ids": [case.case_id for case in processed_cases]})


@app.get("/api/cases/{case_id}")
def case_api(case_id: str, db: Session = Depends(get_db)) -> JSONResponse:
    case = db.get(CaseRecord, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    payload = {
        "id": case.id,
        "status": case.status,
        "source": case.source,
        "attachment_name": case.attachment_name,
        "sender": case.sender,
        "recipient": case.recipient,
        "subject": case.subject,
        "confidence": case.confidence,
        "extraction": json.loads(case.extracted_json) if case.extracted_json else None,
        "knowledge_matches": json.loads(case.rag_json) if case.rag_json else [],
        "review": json.loads(case.review_json) if case.review_json else None,
        "routing": json.loads(case.routing_json) if case.routing_json else None,
        "error_message": case.error_message,
    }
    return JSONResponse(payload)
