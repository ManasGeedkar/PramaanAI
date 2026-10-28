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

### 1. Reset Demo Environment

Before recording or testing, reset the database and seed the applications. Set `DEMO_LIVE_UPLOAD=1` to omit INST04 so it can be uploaded live in the video. The script preserves `storage/ocr_cache` and `storage/cache` for sub-second re-runs.

**From repository root or `backend/`:**
```bash
# PowerShell (Windows)
$env:DEMO_LIVE_UPLOAD="1"; python scripts/reset_demo.py

# Bash (Linux/macOS)
DEMO_LIVE_UPLOAD=1 python scripts/reset_demo.py
```
*(To seed all 10 applications including INST04, omit `DEMO_LIVE_UPLOAD` or set it to `0`)*

### 2. Start Backend API
```bash
cd backend && uvicorn app.main:app --reload --port 8000
```
API Documentation & Swagger UI: `http://localhost:8000/docs`

> [!NOTE]
> Port `8000` also serves the production SPA from `frontend/dist`. It reflects the last `npm run build`. Whenever you modify frontend code, run `scripts/build_frontend.ps1` (or `scripts/build_frontend.sh`) to rebuild the bundle before accessing `:8000`.

### 3. Start Frontend Development Server
```bash
cd frontend && npm install && npm run dev
```
Interactive Portal Interface (Hot Module Reloading): `http://localhost:5173`

### 4. Build Production Frontend
To compile the static frontend served directly by the backend on `:8000`:
```bash
# PowerShell
.\scripts\build_frontend.ps1

# Bash
./scripts/build_frontend.sh
```

## Deploy on Render

PramaanAI can be deployed as a single Docker web service on Render's free plan (512 MB RAM):

1. **New** → **Web Service**
2. **Connect GitHub repo**
3. **Runtime**: `Docker`
4. **Root Directory**: *(leave empty)*
5. **Instance Type**: `Free`
6. **Health check path**: `/health`
7. Click **Create Web Service**

> [!NOTE]
> Free tier instances sleep after 15 minutes of inactivity and spin up automatically on the next incoming request.


