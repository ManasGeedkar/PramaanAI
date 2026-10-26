# PramaanAI (`aicte-validator`)
AICTE Automated Approval & Document Scrutiny System.

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

## Run the demo

### 1. Backend
```bash
cd backend && uvicorn app.main:app --reload --port 8000
```
API Documentation & Swagger UI: `http://localhost:8000/docs`

### 2. Frontend
```bash
cd frontend && npm install && npm run dev
```
Portal Interface: `http://localhost:5173`

