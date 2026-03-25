# Contract Review Agent

An end-to-end interview project for the Flat Rock Technology Agentic AI Engineer task.

This app receives a contract-like attachment from email, extracts structured terms as JSON, retrieves relevant policy snippets from a vector store, and routes the case either to auto-approval or human review.

## Scenario

The chosen business workflow is contract intake and first-pass legal ops review.

Why this scenario fits the task well:

- It shows extraction quality on messy business documents.
- The RAG layer adds real value by validating terms against internal policy.
- Routing logic is meaningful because uncertain or risky contracts should not be auto-approved.
- It is much more interesting than the standard invoice pipeline the prompt explicitly asked to avoid.

## What The System Does

1. Accepts a file attachment from either:
   - a local demo upload form
   - a live Resend inbound webhook
2. Extracts contract terms into a strict JSON schema.
3. Queries a small vector-backed knowledge base of policy documents.
4. Runs a policy review step against the retrieved snippets.
5. Stores the result in SQLite and marks it as:
   - `approved`
   - `needs_review`
   - `failed`

## Project Structure

```text
app/
  main.py                FastAPI app and routes
  models.py              SQLite persistence model
  schemas.py             Pydantic schemas for extraction and review
  services/
    attachments.py       File storage and text extraction
    extraction.py        OpenAI structured extraction
    rag.py               Qdrant-backed knowledge retrieval
    review.py            OpenAI policy review over retrieved snippets
    resend_client.py     Resend webhook verification and attachment fetch
    pipeline.py          End-to-end orchestration and routing
data/
  kb/                    Internal policy source documents
  samples/               Demo PDF attachments
scripts/
  generate_demo_assets.py
```

## From Your Side

You only need to do three real setup tasks:

1. Rotate the OpenAI key you pasted in chat and create a fresh one.
2. Create a Resend account for inbound email testing.
3. Put the new secrets into a local `.env` file.

Do not paste secrets into chat again.

## Local Setup

1. Create a virtual environment.
2. Install dependencies.
3. Copy `.env.example` to `.env`.
4. Fill in your secrets.
5. Run the demo asset generator.
6. Start the app.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
python3 scripts/generate_demo_assets.py
uvicorn app.main:app --reload
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Required `.env` Values

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

RESEND_API_KEY=re_...
RESEND_WEBHOOK_SECRET=whsec_...
```

The storage and database paths already have sensible defaults in `.env.example`.

## Resend Setup

Recommended path for the interview: use Resend's managed receiving domain first. It is faster, avoids DNS work, and still demonstrates real inbound email.

### Step 1. Register

Create an account at [Resend](https://resend.com/).

### Step 2. Create a Resend API key

In the dashboard, create an API key and place it into `.env` as `RESEND_API_KEY`.

### Step 3. Get your receiving domain

In Resend:

1. Go to the **Emails** page.
2. Open the **Receiving** tab.
3. Open the menu and copy your managed `*.resend.app` receiving address/domain.

After that, any address at that domain can receive mail. Example:

```text
contracts@your-id.resend.app
```

### Step 4. Run this app locally

Start the FastAPI server:

```bash
uvicorn app.main:app --reload
```

### Step 5. Expose your local webhook with a tunnel

Use one of these:

- `ngrok http 8000`
- VS Code port forwarding
- Cloudflare Tunnel

You will get a public HTTPS URL like:

```text
https://example.ngrok.app
```

### Step 6. Add the Resend webhook

In Resend webhooks:

1. Click **Add Webhook**
2. Use this endpoint:

```text
https://your-public-url/webhooks/resend
```

3. Subscribe to the `email.received` event
4. Save the webhook
5. Copy the signing secret into `.env` as `RESEND_WEBHOOK_SECRET`

### Step 7. Send test emails

Email the demo contracts in `data/samples/` to your receiving address.

Suggested test subjects:

- `Approved Acme MSA`
- `Northstream vendor intake`
- `Riverlane OCR fragment`

## Demo Flow

You can test the pipeline in two ways:

### Local only

Use the upload form on the homepage and upload the sample PDFs from `data/samples/`.

### Full end-to-end

1. Email a sample PDF to your Resend receiving address.
2. Resend posts `email.received` to `/webhooks/resend`.
3. The app fetches the attachment from Resend.
4. The contract is extracted, reviewed, stored, and shown in the dashboard.

## Current Knowledge Base

The seeded policy docs include:

- approved counterparties
- contract review playbook
- security and privacy expectations
- vendor intake exceptions

These are intentionally small so the retrieval step is easy to inspect during the demo.

## Demo Attachments

The generator creates three PDFs:

- `acme_analytics_msa_excerpt.pdf`
- `northstream_vendor_agreement.pdf`
- `riverlane_logistics_ocr_fragment.pdf`

Expected outcomes:

- `acme_analytics_msa_excerpt.pdf` should route to `approved`
- `northstream_vendor_agreement.pdf` should route to `needs_review`
- `riverlane_logistics_ocr_fragment.pdf` should route to `needs_review`

Why these are the final demo files:

- `acme_analytics_msa_excerpt.pdf` is a realistic, fairly clean agreement excerpt for an approved counterparty.
- `northstream_vendor_agreement.pdf` is intentionally clean on its face, but should still route to review because the KB contains a vendor-intake exception for Northstream. This makes the RAG step visibly useful rather than decorative.
- `riverlane_logistics_ocr_fragment.pdf` mimics a real intake problem: a scanned or OCR-recovered contract fragment with missing commercial details, privacy implications, and an omitted schedule.

## Notes For The Interview Submission

For the final submission, include:

- the public GitHub repository
- this codebase
- any workflow export or setup screenshots if you use a tunnel or Resend configuration
- a short Loom/OBS video showing all three sample files being processed

The strongest demo sequence is:

1. Show the local dashboard.
2. Send three emails with different attachments.
3. Refresh the dashboard as each case appears.
4. Open one approved case and one review case.
5. Point out the extracted JSON, retrieved policy snippets, and routing decision.
