# PS 26261 Prototype — Build Guide for Antigravity

Goal: a **working prototype good enough to record a 4-minute demo video** for the SIH idea submission.
Not production. Every shortcut below is deliberate and listed in "Prototype vs production" so you can
explain it honestly to judges and upgrade it after selection.

---

## 0. How to use this guide

1. Create an empty folder `aicte-validator/`, open it in Antigravity.
2. Unzip `aicte_synthetic_dataset_v1.zip` into `aicte-validator/data/` and copy this file to
   `aicte-validator/BUILD_GUIDE.md`.
3. Paste the prompts in **section 6** to the agent **one at a time, in order**. After each prompt, run
   the acceptance check written under it before moving on. If it fails, paste the error back to the
   agent — don't move ahead with a broken step.
4. Always start a prompt with: *"Read BUILD_GUIDE.md sections 2–5 first."* (already included below).

Time estimate: backend prompts 1–6 ≈ 2–3 days, frontend prompts 7–10 ≈ 2–3 days, demo 1 day.

---

## 1. Scope for the submission prototype

**Build (real, working):**
- Seeded queue of 10 applications + live upload of one more during the video
- Document classification, text extraction (text layer + OCR), field extraction with bounding boxes
- Checklist completeness, expiry, cross-document consistency, AICTE record check
- Configurable rules engine (YAML, editable from admin UI, re-run instantly)
- Forensics: ELA tamper hotspot, PDF metadata anomaly, pHash duplicate photos
- Mock source verification (QR + registries) with all 6 statuses
- Cross-application entity graph (faculty, NOC no., deed no., photos)
- Risk triage queue (High/Medium/Low with breakdown) + "estimated hours saved"
- Officer review actions (accept / dismiss / request evidence / escalate)
- One-click inspection brief PDF
- Hash-chained audit log with "verify chain" button
- Evaluation page comparing results with `data/labels/`

**Skip for now (say "designed for, planned after selection"):**
Celery/Redis queue, PostgreSQL, MinIO + encryption at rest, real DigiLocker/AICTE APIs, YOLO object
detection, LayoutLM fine-tuning, multi-user deployment, email/SMS alerts.

---

## 2. Tech stack (prototype)

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.11, **FastAPI**, **SQLModel + SQLite** | One process, zero setup |
| Background work | FastAPI `BackgroundTasks` | Good enough instead of Celery |
| PDF | **PyMuPDF** (`fitz`) | Text layer with word boxes; render pages to images |
| OCR (scanned) | **rapidocr-onnxruntime** (pip only, works on Windows); fallback `pytesseract` | Returns text + boxes |
| QR | **opencv-python** `QRCodeDetector` | Try 150/200/300 dpi |
| Forensics | Pillow (ELA), **imagehash** (pHash), `pypdf` metadata | Light, explainable |
| Matching | **rapidfuzz** | Fuzzy names |
| Rules | **json-logic** evaluator (`json-logic-qubit` or a 60-line own evaluator) on `data/config/rules.yaml` | Configurable |
| Brief PDF | **reportlab** | Inspection brief |
| Frontend | **React + Vite + TypeScript + Tailwind + shadcn/ui** | Fast, clean |
| PDF viewer | **react-pdf** (pdf.js) + absolutely positioned highlight boxes | Red boxes on evidence |
| Graph | **@xyflow/react** (React Flow) | Entity graph |
| Charts | **Recharts** | Management view |

Run: `uvicorn app.main:app --reload --port 8000` and `npm run dev` (port 5173).

---

## 3. Repository layout

```
aicte-validator/
  BUILD_GUIDE.md
  data/                         <- the dataset zip, unchanged
    applications/INST01..INST10/
    mock_sources/  config/  labels/  tools/
  backend/
    app/
      main.py                   FastAPI app, CORS, routers, startup seeding
      db.py  models.py          SQLModel tables (section 4)
      config.py                 paths, loads data/config/*.yaml
      pipeline/
        run.py                  orchestrates stages for one application
        classify.py             doc type from keywords
        extract.py              text + OCR + fields + bboxes
        qr.py
        checks.py               checklist, expiry, consistency, records
        rules.py                json-logic rules
        forensics.py            ELA, metadata, pHash
        verify.py               calls mock sources -> 6 statuses
        entities.py             cross-application entity graph
        risk.py                 triage score + breakdown
      services/
        audit.py                hash chain
        brief.py                inspection brief PDF
        evaluate.py             compare with data/labels
      mock/
        router.py               /mock/* endpoints serving data/mock_sources
      api/
        applications.py findings.py reviews.py rules.py audit.py entities.py stats.py
    storage/                    uploaded files, ELA heatmaps, briefs (gitignored)
    requirements.txt
  frontend/
    src/pages/  src/components/  src/api/
```

---

## 4. Data contracts (keep these exact — frontend depends on them)

### 4.1 Tables

- `Application(id, application_no, institution_id, institution_name, aicte_id, category, academic_year, submitted_on, status, risk_score, risk_band, risk_breakdown_json, folder, created_at)`
  - `status`: `processing | validated | under_review | evidence_requested | escalated | closed`
- `Document(id, application_id, doc_type, file_path, sha256, scanned bool, page_count, producer, creation_date, mod_date, ocr_confidence)`
- `ExtractedField(id, document_id, name, value, page, bbox_json, confidence)`
- `Finding(id, application_id, document_id nullable, code, severity, title, message, rule_id nullable, evidence_json, confidence, status, created_at)`
  - `severity`: `critical | warning | info`; `status`: `open | accepted | dismissed | evidence_requested | escalated`
- `Verification(id, document_id, source, reference, status, details_json, checked_at)`
  - `status`: `verified | mismatch | expired | pending | source_unavailable | manual_review`
- `Entity(id, entity_type, key, display)` + `EntityOccurrence(id, entity_id, application_id, document_id, academic_year, bbox_json)`
- `Review(id, finding_id, reviewer, decision, comment, created_at)`
- `AuditLog(id, ts, actor, action, entity_type, entity_id, payload_json, prev_hash, hash)`
- `RuleSet(id, version, yaml_text, active, created_at)`

### 4.2 Finding codes (use exactly these)

`MISSING_DOC, EXPIRED_DOC, CROSS_DOC_MISMATCH, RULE_FAIL, RECORD_MISMATCH, NO_PREVIOUS_RECORD,
TAMPER_SUSPECTED, METADATA_ANOMALY, QR_MISMATCH, DUPLICATE_IMAGE, ENTITY_REUSE, SOURCE_MISMATCH,
SOURCE_EXPIRED, SOURCE_UNAVAILABLE, VERIFICATION_PENDING, MANUAL_REVIEW, LOW_OCR_CONFIDENCE`

### 4.3 `evidence_json` shape

```json
{
  "items": [
    {"document_id": 12, "doc_type": "land_deed", "page": 1, "bbox": [x0, y0, x1, y1],
     "field": "land_area_acres", "value": "2.00"},
    {"document_id": 15, "doc_type": "affidavit", "page": 1, "bbox": [x0, y0, x1, y1],
     "field": "land_area_acres", "value": "3.50"}
  ],
  "expected": "equal values", "method": "cross-document compare",
  "related_applications": [], "heatmap_url": null,
  "explanation": "Land area differs between deed (2.00 acres) and affidavit (3.50 acres)"
}
```
**bbox = PDF points, origin top-left** (same as `data/labels`). Frontend scales by `renderedWidth / 595.28`.

### 4.4 API endpoints

```
POST /api/applications/upload            multipart: application_json + files[]  -> {id}
POST /api/applications/{id}/run          re-run pipeline
GET  /api/applications?sort=risk         queue rows: id, no, institution, category, status, risk_band, risk_score, counts{critical,warning,info}
GET  /api/applications/{id}              application + documents + fields + findings + verifications + risk_breakdown
GET  /api/documents/{id}/file            the PDF/JPG
GET  /api/documents/{id}/ela.png         ELA heatmap (scanned docs)
POST /api/findings/{id}/review           {decision: accept|dismiss|request_evidence|escalate, comment}
GET  /api/entities/graph?application_id= nodes/edges for React Flow
GET  /api/applications/{id}/brief.pdf    inspection brief
GET  /api/rules                          active rules YAML + version
PUT  /api/rules                          new YAML -> new version -> re-run all -> returns changed counts
GET  /api/audit?entity_id=               log rows
GET  /api/audit/verify                   {ok: bool, broken_at: id|null}
GET  /api/stats                          totals, by band, hours saved, verification status counts
GET  /api/evaluate                       metrics vs data/labels
GET  /mock/fire-noc/{noc_no}  /mock/land/{deed_no}  /mock/university/{code}/{letter_no}
GET  /mock/accreditation/{cert_no}  /mock/aicte/{aicte_id}
```
Note: numbers contain `/` — pass them URL-encoded or as `?no=` query params.

---

## 5. Rules of thumb for the agent

- Never call a result "fake" or "forged". Use "suspected", "indicator", "needs verification".
- Every finding must have `message` + at least one evidence item or a clear reason why none.
- The pipeline must be **idempotent**: re-running replaces that application's findings.
- Log an `AuditLog` row for: upload, each pipeline stage, each source call, each finding, each review,
  each rules change.
- Read thresholds from `data/config/*.yaml`, never hard-code them.
- Pipeline stage order: **extract → checks → rules → forensics → verify → entities → risk**
  (entities need verification results; risk needs everything).
- Keep functions small and pure where possible so they can be unit-tested against `data/labels`.

---

## 6. Prompts (paste one at a time)

### Prompt 1 — Backend scaffold, models, seeding

> Read BUILD_GUIDE.md sections 2–5 first. Create the `backend/` FastAPI project exactly as in section 3
> with SQLModel + SQLite (`backend/storage/app.db`). Implement all tables from section 4.1, `config.py`
> that loads every YAML in `data/config/`, and `services/audit.py` with a SHA-256 hash chain
> (`hash = sha256(prev_hash + ts + actor + action + entity_type + entity_id + payload_json)`).
> Add `mock/router.py` serving `data/mock_sources/*.json` at the `/mock/*` endpoints in 4.4:
> land registry entries with `response: PENDING` return HTTP 202 `{status:"pending"}`; university `KVU`
> has `available:false` so return HTTP 503. On startup, if the DB is empty, create one `Application` +
> `Document` rows for each folder in `data/applications/` (read `application.json`, sha256 every file,
> read PDF metadata with pypdf) — but do not run the pipeline yet. Add `GET /api/applications` and
> `GET /api/applications/{id}`. Write `requirements.txt` and a README with run commands.

**Check:** `GET /api/applications` returns 10 rows; `GET /mock/fire-noc?no=SPFES/NOC/2025/5476` returns INST01's record; `/mock/university/KVU/...` returns 503.

### Prompt 2 — Classification, text, OCR, field extraction, QR

> Implement `pipeline/classify.py`, `extract.py`, `qr.py`. For each PDF: open with PyMuPDF; if the page
> has a text layer use `page.get_text("words")` (boxes are already in points, top-left origin);
> otherwise render at 200 dpi and OCR with rapidocr-onnxruntime (fallback pytesseract), converting
> pixel boxes to points (`* 72 / dpi`) and recording the mean OCR confidence on the Document.
> Classify by `classify_keywords` in `data/config/doc_types.yaml`. Extract each field by finding its
> `label` on the page and taking the words to the right on the same line (apply `regex` if given;
> parse `date` dd-mm-yyyy to ISO; parse numbers removing commas and units). Store value, page, bbox
> (union of the value words), confidence. For faculty_list parse every row with the `rows.regex`
> into a list (faculty_id, name, dob) stored as one ExtractedField `rows` with JSON value.
> QR: render at 150, 200, 300 dpi and use OpenCV `QRCodeDetector().detectAndDecode`; parse the
> `MOCKVERIFY|...` payload into a dict and store as ExtractedField `qr`. If no QR found on a doc type
> that should have one, store `qr = null`. Create `pipeline/run.py` that runs these stages for one
> application, then add `POST /api/applications/{id}/run` and run all 10 on startup in background.
> Create `services/evaluate.py` with `extraction_accuracy()` comparing values to
> `data/labels/fields_ground_truth.json` and expose `GET /api/evaluate`.

**Check:** `GET /api/evaluate` shows field accuracy ≥ 85%; INST05 deed `land_area_acres = 2.0`, affidavit `3.5`; INST10 accreditation `qr = null`.

### Prompt 3 — Checklist, expiry, consistency, records, rules engine

> Implement `pipeline/checks.py` and `pipeline/rules.py` using `checklists.yaml`, `consistency.yaml`,
> `rules.yaml`. Produce Findings with the codes in 4.2 and evidence in the 4.3 shape (bbox from
> ExtractedField). Checks: (1) required docs for the category → `MISSING_DOC`; (2) `validity` docs whose
> date < `session_start` → `EXPIRED_DOC`; (3) every `cross_document` group → `CROSS_DOC_MISMATCH` with
> one evidence item per source; (4) records vs `/mock/aicte` → `RECORD_MISMATCH`,
> `NO_PREVIOUS_RECORD`; (5) rules: build the context described in rules.yaml, evaluate json-logic,
> fill `{placeholders}` in `message`, create `RULE_FAIL` with `rule_id`. Store the active rules YAML
> in `RuleSet` (version from the file). Add `GET/PUT /api/rules`; PUT saves a new version, re-runs
> all applications, writes an audit row and returns how many findings changed per application.

**Check:** INST06 → MISSING_DOC (accreditation) + RULE_FAIL R-FAC-001 + R-ACC-001; INST05 → CROSS_DOC_MISMATCH land + RULE_FAIL R-LAND-001; INST03 → EXPIRED_DOC; INST10 → RECORD_MISMATCH; INST01/INST02 have no critical findings. Changing `min_land_acres` to 1.5 via PUT removes INST05's R-LAND-001.

### Prompt 4 — Forensics and entity graph

> Implement `pipeline/forensics.py`: (a) **ELA** for scanned PDFs: extract the embedded page JPEG
> (PyMuPDF `extract_image`), re-save at quality 75, absolute difference, save an amplified heatmap PNG
> to `storage/ela/{document_id}.png`; for each extracted field compute mean ELA inside its bbox and
> compare to the median of the other fields on that page; if ratio > 1.6 create `TAMPER_SUSPECTED`
> (warning if 1.6–2.0, critical if > 2.0) with the field bbox, ratio as confidence and `heatmap_url`.
> (b) **Metadata**: if a document whose issuer is an external authority (fire_noc, land_deed,
> affiliation_letter, accreditation_certificate) has producer containing Photoshop/GIMP/Word/Canva, or
> ModDate more than 365 days after its issue_date → `METADATA_ANOMALY`. (c) **pHash** with imagehash on
> every photo across all applications; distance ≤ 6 → `DUPLICATE_IMAGE` on both (warning on the later
> submission, info on the earlier) with `related_applications`. Then implement `pipeline/entities.py`
> per `consistency.yaml > entities`: build Entity/EntityOccurrence for faculty (from rows), fire_noc_no,
> deed_no, survey_no, photo hash; any entity in ≥ 2 applications of the same academic year →
> `ENTITY_REUSE` on each. Severity: for fire_noc_no/deed_no, the application whose document the source
> **verified** is the genuine holder → `info`; every other application → `critical`. Faculty and
> survey_no → `warning`. Faculty must match faculty_id AND dob — never name only. Photo entities appear
> in the graph but do **not** create ENTITY_REUSE (DUPLICATE_IMAGE already covers them). Run this stage
> after verification (Prompt 5) — until then, treat all as `critical`. Add
> `GET /api/entities/graph?application_id=` returning React Flow nodes (applications + entities) and edges.

**Check:** INST04 → TAMPER_SUSPECTED on valid_till + METADATA_ANOMALY (Photoshop); INST09 → METADATA_ANOMALY (Word); INST07 ↔ INST02 DUPLICATE_IMAGE; INST07 ↔ INST08 ENTITY_REUSE (3 faculty); INST09 ↔ INST01 ENTITY_REUSE (NOC no.); **no** ENTITY_REUSE for 'Rajesh Sharma' (INST01/INST05).

### Prompt 5 — Source verification (6 statuses)

> Implement `pipeline/verify.py`. For each document type with `verify` in doc_types.yaml call the mock
> endpoint using the extracted key field (with a 3-second timeout). Compare returned values with the
> printed values and with the QR payload. Status logic: 503/timeout → `source_unavailable`; 202 →
> `pending`; not found or holder_institution_id ≠ this application, or any compared field differs →
> `mismatch`; registry valid_till < session_start → `expired`; QR missing on a QR doc AND OCR confidence
> low → `manual_review`; else `verified`. Save a `Verification` row with source, reference, status,
> details (what was compared, both values) and timestamp; also create findings `SOURCE_MISMATCH`,
> `SOURCE_EXPIRED`, `SOURCE_UNAVAILABLE` (info), `VERIFICATION_PENDING` (info), `MANUAL_REVIEW`,
> `QR_MISMATCH` (QR value ≠ printed value). Write one audit row per source call.

**Check:** statuses equal `data/labels/verification_ground_truth.json` for all 10 applications (add this to `/api/evaluate` as `verification_accuracy`).

### Prompt 6 — Risk triage, reviews, inspection brief, stats

> Implement `pipeline/risk.py` using `data/config/risk.yaml`: score = sum of points, band by thresholds,
> store `risk_breakdown_json` as a list of `{reason, points, finding_id}`; `source_unavailable` and
> `pending` add 0. Run it as the last stage. Add `POST /api/findings/{id}/review` (updates finding
> status, application status `under_review`/`evidence_requested`/`escalated`, writes Review + audit).
> Add `services/brief.py`: a 1–2 page reportlab PDF for physical inspection — header (institution,
> AICTE ID, category, risk band), table of open critical/warning findings with reasons, page crops of
> the evidence with red boxes drawn, questions for the inspection team generated from finding codes,
> previous-year vs current deltas (from /mock/aicte), a "map pin" line with the district, and the text
> "Advisory findings for verification — not a determination." Serve at
> `GET /api/applications/{id}/brief.pdf`. Add `GET /api/stats` (counts by band and verification status,
> documents auto-cleared, hours saved per risk.yaml formula with the assumption text), `GET /api/audit`,
> `GET /api/audit/verify`. Finish `/api/evaluate` with: extraction accuracy, finding recall vs
> `expected_findings.json` (match on code + doc_type), false positives, verification accuracy,
> risk-band accuracy, average pipeline seconds per application.

**Check:** risk bands match `expected_findings.json` (INST01/02 Low, 07/08/10 Medium, others High); brief PDF opens; `/api/audit/verify` → ok; manually editing one audit row in SQLite makes it return `broken_at`.

### Prompt 7 — Frontend scaffold, triage queue, management view

> Create `frontend/` with React + Vite + TypeScript + Tailwind + shadcn/ui, a typed API client for
> section 4.4, and a left sidebar with role switcher (Institution / Scrutiny Officer / Admin — no real
> auth, just a dropdown stored in localStorage). Pages: **Triage queue** (default for officer): table
> sorted by risk with coloured band badge, score, counts of critical/warning/info, status, category;
> clicking a row opens the application. Hovering the band shows the risk breakdown. **Overview**
> (management): KPI cards (applications, high-risk, documents auto-cleared, estimated hours saved with
> the assumption in small text), bar chart of applications by band, bar chart of verification statuses.
> Use a calm government-portal look: white background, navy primary, red/amber/green only for severity.
> Put a footer on every page: "AI findings are advisory. Final decisions rest with competent AICTE
> authorities."

### Prompt 8 — Application detail with evidence highlights

> Build the **Application detail** page: header (institution, AICTE ID, category, band + score, status,
> buttons "Re-run checks" and "Download inspection brief"). Left: findings list grouped by severity,
> each card shows code, title, message, confidence and review buttons (Accept / Dismiss / Request
> evidence / Escalate with a comment box). Right: document viewer with react-pdf; tabs per document;
> selecting a finding opens the right document/page and draws **red boxes** for its evidence bboxes
> (scale = rendered width / 595.28) and scrolls to them; for CROSS_DOC_MISMATCH show the two documents
> side by side with both boxes. For TAMPER_SUSPECTED add a toggle "Show ELA heatmap" overlaying
> `/api/documents/{id}/ela.png`. Below the viewer: **Verification** table (document, source, status chip
> using the 6 statuses with distinct colours, details, timestamp) and **Checklist** (required docs with
> present/missing ticks).

### Prompt 9 — Entity graph, admin rules, audit, upload

> Add an **Entity graph** tab on the application page using @xyflow/react: application nodes (coloured
> by band), entity nodes (faculty, NOC no., deed, photo) and edges; clicking an entity shows every
> application and document where it appears, with thumbnails for photos. Add **Admin → Rules**: show
> each rule (id, title, severity, params) with editable params and a YAML editor tab; "Save & re-run"
> calls PUT /api/rules and shows a toast like "R-LAND-001 changed: 1 application affected". Add
> **Audit log** page: table of rows, filter by application, "Verify chain" button showing a green
> "Chain intact" or red "Chain broken at #id". Add **Institution → New application** page: form with
> category, programmes, declared values and file upload by document type; submit calls
> /api/applications/upload, then shows live pipeline progress (poll every second) and links to the
> result.

### Prompt 10 — Evaluation page, polish, demo data

> Add **Evaluation** page showing `/api/evaluate` metrics as cards and a per-application table of
> expected vs found findings (green = found, red = missed, grey = extra). Add empty/loading/error
> states everywhere, consistent date formatting (dd-mm-yyyy), and a `scripts/reset_demo.py` that
> deletes the DB and storage and re-seeds the 10 applications. Make `GET /api/applications` hide
> INST04 when an env var `DEMO_LIVE_UPLOAD=1` is set, so INST04 can be uploaded live in the video.

---

## 7. Demo video script (≈ 4 minutes)

| Time | Screen | Say |
|---|---|---|
| 0:00 | Title slide | Problem in one line: manual scrutiny of thousands of EoA applications, missing/expired/altered documents, slow issuer confirmation. |
| 0:20 | Overview page | 10 synthetic applications already processed; KPIs; hours saved (estimate, assumption shown). |
| 0:40 | Triage queue | Officers start with High risk; hover to show why. |
| 1:00 | Institution → upload INST04 | Live pipeline progress. |
| 1:30 | INST04 detail | Red box on "Valid Till", ELA heatmap toggle, Photoshop metadata, QR says 2026, registry says expired → **mismatch**. Stress "suspected, for verification". |
| 2:10 | INST05 | Side-by-side deed 2.00 vs affidavit 3.50 acres; rule R-LAND-001. |
| 2:30 | INST07 → Entity graph | Same lab photo as INST02; 3 faculty shared with INST08. Mention name-only matches are not flagged. |
| 2:55 | INST10 | Statuses: source unavailable (KVU), manual review (blurry scan), record mismatch. |
| 3:10 | Admin → Rules | Change min land 2.5 → 1.5, re-run, INST05 rule finding disappears: "no code change". |
| 3:25 | Review + brief | Officer escalates INST04, downloads inspection brief PDF. |
| 3:40 | Audit log | Every step logged; "Verify chain" → intact. |
| 3:50 | Evaluation page | Extraction accuracy, finding recall, verification accuracy on the synthetic set. |
| 4:00 | Close | Human-in-the-loop, explainable, configurable; production path after selection. |

Recording tips: 1080p, browser zoom 110%, hide bookmarks bar, run `reset_demo.py` before each take,
record narration separately if your room is noisy.

---

## 8. Prototype vs production (put this on the feasibility slide)

| Prototype now | After selection |
|---|---|
| SQLite, local files | PostgreSQL + MinIO with AES-256 at rest |
| FastAPI BackgroundTasks | Celery + Redis workers, horizontal scaling |
| Mock registries from JSON | DigiLocker / API Setu / issuer APIs under authorised access |
| Keyword + label-anchor extraction | LayoutLMv3 / Donut for unseen layouts |
| ELA + metadata + pHash | + CNN tamper localisation, signature validation (pyHanko) |
| Role dropdown | SSO/JWT with RBAC, access logs, PII masking |
| Placeholder photos | YOLOv8 infrastructure checks on real campus photos |

---

## 9. Troubleshooting

- **QR not decoding:** try more DPIs and grayscale; don't crop before detection.
- **OCR misses a value on scans:** render at 250–300 dpi; widen the "same line" tolerance to ±6 points.
- **Boxes misaligned in the viewer:** you are mixing pixel and point units, or using bottom-left origin.
- **pHash flags unrelated photos:** threshold must be ≤ 6 (dataset: duplicate = 2, nearest unrelated = 10).
- **ELA flags clean scans:** compare fields against each other on the same page, not against blank paper.
- **Rapidocr install fails on Windows:** use Python 3.11; or install Tesseract and set `pytesseract.pytesseract.tesseract_cmd`.
