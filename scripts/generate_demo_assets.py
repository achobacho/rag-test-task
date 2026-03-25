from pathlib import Path


SAMPLES = {
    "acme_analytics_msa_excerpt.pdf": [
        """MASTER SERVICES AGREEMENT
Execution Version

This Master Services Agreement ("Agreement") is entered into as of March 1, 2026
by and between Flat Rock Technology, Inc. ("Customer") and Acme Analytics, Inc.
("Provider").

1. Services.
Provider will implement and support the Acme Analytics reporting workspace described
in Order Form FR-2026-014. Provider will provide onboarding assistance, dashboard
configuration, and standard e-mail support during business hours.

2. Fees and Payment.
Customer will pay the fees set out in the Order Form. Invoices are due net thirty (30)
days from receipt. No late fee applies unless the parties agree otherwise in writing.

3. Term.
The initial term begins on March 1, 2026 and ends on February 28, 2027. This
Agreement does not auto-renew unless the parties sign a separate renewal order form.

4. Data Scope.
Provider will receive usage telemetry, project metadata, and configuration data only.
No customer personal data or employee personal data will be transferred under this
Agreement.

5. Termination.
Either party may terminate this Agreement for convenience on thirty (30) days' prior
written notice. Either party may terminate immediately for material breach if the breach
remains uncured for fifteen (15) days after notice.

Page 1 of 2
CONFIDENTIAL
""",
        """MASTER SERVICES AGREEMENT
Execution Version

6. Limitation of Liability.
Except for excluded claims expressly stated below, each party's aggregate liability
arising out of or related to this Agreement will not exceed the fees paid or payable by
Customer under this Agreement during the twelve (12) months preceding the event
giving rise to the claim.

7. Governing Law.
This Agreement is governed by the laws of the State of Delaware, without regard to
conflict-of-laws principles.

8. Key Commercial Notes.
- Counterparty: Acme Analytics, Inc.
- Contract type: Master Services Agreement
- Personal data handling: No
- DPA required: No, based on the service scope above

IN WITNESS WHEREOF, the parties have caused this Agreement to be executed by
their duly authorized representatives.

Flat Rock Technology, Inc.          Acme Analytics, Inc.
By: /s/ A. Buyer                    By: /s/ C. Vendor
Title: VP Operations                Title: COO

Page 2 of 2
CONFIDENTIAL
""",
    ],
    "northstream_vendor_agreement.pdf": [
        """SOFTWARE SERVICES AGREEMENT
Vendor Draft - Redline Resolved

This Software Services Agreement is entered into as of April 12, 2026 by and between
Flat Rock Technology, Inc. and Northstream Data Systems LLC ("Vendor").

1. Services.
Vendor will provide a hosted sourcing workflow application, implementation assistance,
single sign-on support, and routine maintenance for the subscription term.

2. Fees.
Subscription fees are payable annually in advance. Professional services are billed as
incurred. Payment terms are net thirty (30) days from invoice date.

3. Term and Renewal.
The initial term begins on April 12, 2026 and ends on April 11, 2027. The Agreement
does not auto-renew unless the parties sign a written renewal document.

4. Termination.
Customer may terminate for convenience upon thirty (30) days' written notice.

Page 1 of 2
""",
        """SOFTWARE SERVICES AGREEMENT
Vendor Draft - Redline Resolved

5. Liability Cap.
Except for each party's confidentiality obligations and willful misconduct, aggregate
liability under this Agreement will not exceed fees paid by Customer during the
twelve (12) months preceding the claim.

6. Governing Law.
This Agreement is governed by New York law.

7. Data Use.
Vendor will access configuration records and purchasing workflow metadata. The
current implementation does not require Vendor to process customer personal data.

8. Signature Summary.
- Counterparty: Northstream Data Systems LLC
- Contract type: Vendor agreement
- Apparent business risk from face of contract: Low

Accepted and agreed by authorized representatives of the parties.

Page 2 of 2
""",
    ],
    "riverlane_logistics_ocr_fragment.pdf": [
        """SERVICE AGREEMENT - OCR EXPORT
source file: signed_copy_scan_07.pdf
notice: text recovered from scan; spacing and line breaks may be imperfect

FLAT ROCK TECHNOLOGY, INC.   /   RIVERLANE LOGISTICS LTD.

Section 1 - Services
Supplier shall provide shipment coordination, route event monitoring, and user portal
access for Customer's operations personnel and designated contractor teams.

Section 2 - Data Handling
Supplier may receive employee names, work e-mail addresses, location updates,
driver contact records, and account credentials needed to support portal access.
The parties intend to finalize a privacy schedule "shortly after signature".

Section 3 - Term
The Service Term begins on or about 05/ /2026 (day not legible in source copy).
This Agreement renews automatically for follow-on service periods unless either
party objects before renewal.

-- footer from source copy --
page 1 / 2    scan quality: medium
""",
        """SERVICE AGREEMENT - OCR EXPORT
source file: signed_copy_scan_07.pdf

Section 4 - Termination
Either party may terminate for material breach. The convenience termination sentence
is cut off in the scanned copy and the notice period cannot be confirmed.

Section 5 - Liability
aggregate liability of supplier shall be limited as set out in Schedule 3...
[Schedule 3 not included in the received attachment]

Section 6 - Governing Law
This Agreement is governed by the laws of New York.

Operational notes captured by legal ops during intake:
- counterparty appears to be Riverlane Logistics Ltd.
- renewal language present, renewal duration not visible
- privacy addendum / DPA not attached
- signed scan quality makes two commercial fields unreadable

-- footer from source copy --
page 2 / 2    signature page omitted from attachment
""",
    ],
}


def escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_content_stream(text: str) -> bytes:
    lines = text.strip().splitlines()
    content_lines = ["BT", "/F1 11 Tf", "72 744 Td", "14 TL"]
    first = True
    for raw_line in lines:
        line = escape_pdf_text(raw_line)
        if first:
            content_lines.append(f"({line}) Tj")
            first = False
        else:
            content_lines.append(f"T* ({line}) Tj")
    content_lines.append("ET")
    return "\n".join(content_lines).encode("utf-8")


def write_pdf(path: Path, pages: list[str]) -> None:
    objects: list[bytes] = []
    objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj")

    kids = []
    font_object_id = 3
    next_object_id = 4
    page_objects: list[bytes] = []

    for page_text in pages:
        page_object_id = next_object_id
        content_object_id = next_object_id + 1
        next_object_id += 2
        kids.append(f"{page_object_id} 0 R")
        content_stream = build_content_stream(page_text)
        page_objects.append(
            (
                f"{page_object_id} 0 obj << /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_object_id} 0 R >> >> "
                f"/Contents {content_object_id} 0 R >> endobj"
            ).encode("utf-8")
        )
        page_objects.append(
            f"{content_object_id} 0 obj << /Length {len(content_stream)} >> stream\n".encode("utf-8")
            + content_stream
            + b"\nendstream endobj"
        )

    objects.append(
        f"2 0 obj << /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >> endobj".encode("utf-8")
    )
    objects.append(b"3 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj")
    objects.extend(page_objects)

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
        pdf.extend(b"\n")

    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("utf-8"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("utf-8"))
    pdf.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("utf-8")
    )
    path.write_bytes(pdf)


def main() -> None:
    target = Path("data/samples")
    target.mkdir(parents=True, exist_ok=True)
    for existing in target.glob("*.pdf"):
        existing.unlink()
    for filename, pages in SAMPLES.items():
        write_pdf(target / filename, pages)


if __name__ == "__main__":
    main()
