# AICTE PS 26261 — Synthetic Test Dataset v1

Synthetic application data for the SIH 2026 prototype **AI-Powered Application Validation, Document
Authentication and Regulatory Compliance Verification**.

> **Everything here is fictional.** The state ("Sampurna Pradesh"), issuers (SPFES fire services,
> SPREG land registry, Sampurna Technical University, Kaveri Valley University, BPAC accreditation
> council), colleges and people are invented. Every document carries a *SYNTHETIC TEST DATA*
> watermark and footer. Rule values are illustrative, not actual AICTE norms.

## What's inside

```
applications/INSTxx/
    application.json        portal form data (category, programmes, declared values, file list)
    documents/*.pdf         fire_noc, land_deed, affiliation_letter, accreditation_certificate*,
                            faculty_list, affidavit       (*only where applicable)
    photos/*.jpg            computer_lab, classroom (procedural placeholders)
mock_sources/              what the "official sources" would return (serve these from mock APIs)
    aicte_records.json        previous-year approval, approved intake, TER payment (key: AICTE ID)
    fire_noc_registry.json    key: NOC number
    land_registry.json        key: deed number  (response: OK | PENDING)
    university_registry.json  STU available; KVU available=false -> "source unavailable"
    accreditation_registry.json
config/                    checklists, rules (json-logic), consistency checks, doc types, risk weights
labels/
    expected_findings.json        ground truth per institution: findings, risk band, verification status
    fields_ground_truth.json      every extractable field: value + bbox (PDF points, top-left origin)
    verification_ground_truth.json
    manifest.json                 every file with sha256
tools/                     generator (generate.py) + checks (verify.py) to extend or regenerate
```

Bounding boxes are in **PDF points (1/72 inch), origin top-left, A4 = 595.28 x 841.89**. To draw
on a page rendered at `dpi`, multiply by `dpi / 72`. Boxes on scanned documents are approximate
(scan rotation up to 0.9°).

## The 10 applications and what is planted

| ID | Expected risk | Scenario |
|---|---|---|
| INST01 | Low | Clean application. Control case: everything valid and verifiable. |
| INST02 | Low | Clean intake-increase application with valid accreditation. Control case. |
| INST03 | High | Fire NOC genuinely EXPIRED (valid till 2026-03-31). Registry confirms expiry. |
| INST04 | High | Fire NOC TAMPERED: 'Valid till' edited 31-03-2026 -> 31-03-2028 on a scanned image (ELA-detectable), PDF producer = Adobe Photoshop. QR + registry still say 2026. |
| INST05 | High | LAND MISMATCH: sale deed says 2.0 acres, affidavit claims 3.5 acres. 2.0 also fails the minimum-land rule. Land registry verification returns PENDING. |
| INST06 | High | MISSING accreditation certificate for an intake increase; FACULTY SHORTAGE (8 faculty for 240 intake); no previous-year record in AICTE system. |
| INST07 | Medium | DUPLICATE lab photo (INST02's photo, resized + brightened). 3 faculty members (same Faculty ID, name, DOB) also claimed by INST08 in the same academic year. |
| INST08 | Medium | Shares the same 3 faculty members with INST07 (entity-graph case). |
| INST09 | High | REUSED Fire NOC: carries INST01's NOC number with INST09's name typed in (producer = Microsoft Word). QR + registry point to INST01 -> MISMATCH; entity graph shows the NOC number in 2 applications. |
| INST10 | Medium | RECORD MISMATCH: form claims existing intake 240, AICTE record says 120. Affiliation from KVU whose verification API is UNAVAILABLE. Accreditation certificate is a blurry scan with unreadable QR -> MANUAL REVIEW. |

## Which document is digital and which is scanned

- **Digital (text layer present, read with PyMuPDF):** fire_noc (except INST04), affiliation_letter,
  accreditation_certificate (except INST10), faculty_list.
- **Scanned (image only, needs OCR):** land_deed, affidavit, INST04 fire_noc (tampered),
  INST10 accreditation (deliberately blurry).

## Signals verified to work (tools/verify.py)

- Text layer on digital PDFs; Tesseract reads scanned deeds/affidavits (e.g. "2.00 acres" vs "3.50 acres").
- QR codes decode with OpenCV `QRCodeDetector` (try 150/200/300 dpi); INST10's is unreadable.
  QR payload format: `MOCKVERIFY|ISSUER|DOC_TYPE|NUMBER|HOLDER=INSTxx|VALID_TILL=...|SIG=...`
- **ELA** (re-save at JPEG quality 75, compare): INST04 "Valid Till" patch ≈ 17 vs ≈ 8 for untouched fields.
- PDF metadata: INST04 producer `Adobe Photoshop 25.1`; INST09 `Microsoft Word 2019`; genuine SPFES
  certificates use `SPFES e-Certificate Portal v3.2`.
- **pHash** (64-bit DCT): INST02 vs INST07 lab photo distance 2; every other pair ≥ 10. Use threshold ≤ 6.
- Entity graph: exactly 3 faculty shared (INST07 ↔ INST08); 'Rajesh Sharma' in INST01 and INST05 are
  **different people** (different ID + DOB) — must NOT be flagged.

## Tip

The photos are drawn placeholders, good for duplicate detection but not for object detection. For the
demo video, replace them with real photos of your own college's labs and classrooms (keep the same file
names), then copy one of them into a second college with a light crop to recreate the duplicate case.

Regenerate: `python tools/generate.py <out_dir>` then `python tools/verify.py <out_dir>`
(needs reportlab, pillow, numpy, opencv-python, img2pdf, pypdf, pytesseract + poppler `pdftoppm`).
