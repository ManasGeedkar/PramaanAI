# PramaanAI Backend (`aicte-validator`)

FastAPI backend for AICTE Document & Approval Scrutiny System.

## Features (Prompt 1)
- **FastAPI application** with SQLite + SQLModel persistent storage (`backend/storage/app.db`)
- **Data models**: Application, Document, ExtractedField, Finding, Verification, Entity, EntityOccurrence, Review, AuditLog, RuleSet
- **YAML Configuration Registry**: Dynamic loading from `data/config/*.yaml`
- **SHA-256 Hash Chained Audit Log**: Tamper-evident logging and verification service
- **Mock Source Verification Endpoints**:
  - `GET /mock/fire-noc/{noc_no}` / `GET /mock/fire-noc?no=...`
  - `GET /mock/land/{deed_no}` / `GET /mock/land?no=...` (returns HTTP 202 on PENDING)
  - `GET /mock/university/{code}/{letter_no}` / `GET /mock/university/{code}?no=...` (returns HTTP 503 for unavailable university KVU)
  - `GET /mock/accreditation/{cert_no}` / `GET /mock/accreditation?no=...`
  - `GET /mock/aicte/{aicte_id}` / `GET /mock/aicte?no=...`
- **Application Endpoints**:
  - `GET /api/applications?sort=risk`
  - `GET /api/applications/{id}`
- **Automated Seeding**: Auto-seeds 10 sample applications (`INST01` to `INST10`) and all documents/photos on empty startup.

## Pipeline Architecture & Execution Stages

The scrutiny pipeline executes stages in the exact order:
```
extract → quality → checks → rules → forensics → verify → entities → risk
```

1. **`extract`**: Text layer word boxes + OCR (rapidocr-onnxruntime), field anchors, table rows, and QR payload decoding.
2. **`quality`**: Document scan quality assessment (Laplacian blur, DPI, contrast, brightness) and low OCR confidence detection.
3. **`checks`**: Mandatory document checklist completeness, validity/expiry dates, cross-document group consistency, and historical AICTE records.
4. **`rules`**: Json-logic compliance rule evaluation against institutional norms and quotas.
5. **`forensics`**: Error Level Analysis (ELA) tamper heatmap detection, PDF metadata tampering indicators, and pHash duplicate photo matching.
6. **`verify`**: Mock registry and QR source verification returning 6 standardized statuses (`verified`, `mismatch`, `expired`, `pending`, `source_unavailable`, `manual_review`).
7. **`entities`**: Cross-application entity graph mapping (faculty, NOC, deed, survey) and single-pass bi-directional cross-application reuse refreshing.
8. **`risk`**: Explainable risk triage scoring, risk banding (`High`, `Medium`, `Low`), and point breakdown per institutional risk configuration.

## Setup & Running

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the development server
From the `backend` directory:
```bash
uvicorn app.main:app --reload --port 8000
```

Interactive API documentation will be available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
