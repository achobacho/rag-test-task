import json
from dataclasses import dataclass

import httpx
from svix.webhooks import Webhook, WebhookVerificationError

from app.config import Settings


@dataclass
class ResendDownloadedAttachment:
    filename: str
    content_type: str | None
    content: bytes


class ResendClient:
    def __init__(self, settings: Settings):
        if settings.resend_api_key is None:
            raise RuntimeError("RESEND_API_KEY is not configured.")
        self.settings = settings
        self.base_url = settings.resend_base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
            "User-Agent": "contract-review-agent/0.1",
        }

    def verify_webhook(self, raw_payload: bytes, headers: dict[str, str]) -> dict:
        if self.settings.resend_webhook_secret is None:
            return json.loads(raw_payload.decode("utf-8"))
        secret = self.settings.resend_webhook_secret.get_secret_value()
        try:
            return Webhook(secret).verify(raw_payload, headers)
        except WebhookVerificationError as exc:
            raise RuntimeError("Invalid Resend webhook signature.") from exc

    def get_received_email(self, email_id: str) -> dict:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{self.base_url}/emails/receiving/{email_id}", headers=self.headers)
            self._raise_for_status(response)
            return response.json()

    def get_attachment_info(self, email_id: str, attachment_id: str) -> dict:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{self.base_url}/emails/receiving/{email_id}/attachments/{attachment_id}",
                headers=self.headers,
            )
            self._raise_for_status(response)
            return response.json()

    def download_processable_attachments(self, email_id: str, email_payload: dict) -> list[ResendDownloadedAttachment]:
        processable: list[ResendDownloadedAttachment] = []
        attachments = email_payload.get("attachments", [])
        for attachment in attachments:
            disposition = attachment.get("content_disposition")
            if disposition == "inline":
                continue
            info = self.get_attachment_info(email_id=email_id, attachment_id=attachment["id"])
            download_url = info["download_url"]
            with httpx.Client(timeout=30.0) as client:
                response = client.get(download_url, headers={"User-Agent": "contract-review-agent/0.1"})
                response.raise_for_status()
                processable.append(
                    ResendDownloadedAttachment(
                        filename=info["filename"],
                        content_type=info.get("content_type"),
                        content=response.content,
                    )
                )
        return processable

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code in {401, 403}:
            raise RuntimeError(
                "Resend rejected the API request. Check that RESEND_API_KEY is the current Resend API key "
                "and that it was created with full_access permissions, then restart the app."
            )
        response.raise_for_status()
