#!/usr/bin/env python3
"""
scripts/reset_demo.py
Reset script for demo video recording:
- Deletes the SQLite DB, reviews, audit logs, and generated briefs.
- Preserves storage/ocr_cache/ and storage/cache/ so OCR and ELA re-runs take seconds, not minutes.
- When DEMO_LIVE_UPLOAD=1, skips seeding INST04 entirely so it can be uploaded live in the video without duplication.
- Re-seeds the remaining applications and executes the pipeline synchronously.
"""

import os
import sys
import shutil
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add backend directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from sqlmodel import Session, select, text
from app.db import engine, init_db
from app.config import STORAGE_DIR
from app.models import (
    Application, Document, ExtractedField, Finding,
    Verification, Entity, EntityOccurrence, Review,
    AuditLog, RuleSet
)
from app.seed import seed_database_if_empty
from app.pipeline.run import run_pipeline


def reset_storage():
    """
    Cleans generated briefs, upload directories, and temporary test crops.
    Preserves storage/ocr_cache and storage/cache.
    """
    briefs_dir = STORAGE_DIR / "briefs"
    if briefs_dir.exists():
        shutil.rmtree(briefs_dir, ignore_errors=True)
    briefs_dir.mkdir(parents=True, exist_ok=True)

    uploads_dir = STORAGE_DIR / "uploads"
    if uploads_dir.exists():
        shutil.rmtree(uploads_dir, ignore_errors=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    ela_dir = STORAGE_DIR / "ela"
    if ela_dir.exists():
        shutil.rmtree(ela_dir, ignore_errors=True)
    ela_dir.mkdir(parents=True, exist_ok=True)

    # Clean stray PNGs in storage root
    for p in STORAGE_DIR.glob("*.png"):
        try:
            p.unlink()
        except Exception:
            pass

    print("[OK] Storage cleaned (preserved storage/ocr_cache and storage/cache)")


def reset_database():
    """
    Clears all tables or deletes the SQLite database file if not locked.
    """
    db_file = STORAGE_DIR / "app.db"
    
    # Try deleting file if possible, or truncate tables
    truncated = False
    try:
        if db_file.exists():
            with Session(engine) as session:
                for table in [
                    "review", "finding", "verification", "extractedfield",
                    "entityoccurrence", "entity", "document", "auditlog",
                    "ruleset", "application"
                ]:
                    try:
                        session.exec(text(f"DELETE FROM {table}"))
                    except Exception:
                        pass
                session.commit()
                try:
                    session.exec(text("VACUUM"))
                    session.commit()
                except Exception:
                    pass
                truncated = True
    except Exception as e:
        print(f"Notice during table truncate: {e}")

    if not truncated and db_file.exists():
        try:
            db_file.unlink()
            print("[OK] SQLite app.db removed")
        except Exception as e:
            print(f"Notice deleting app.db directly: {e}")

    # Re-initialize table schemas
    init_db()
    print("[OK] Database schema re-initialized")


def reseed_and_run():
    demo_live_mode = os.environ.get("DEMO_LIVE_UPLOAD") == "1"
    print(f"\n--- Reseeding Database (DEMO_LIVE_UPLOAD={'1 (INST04 skipped)' if demo_live_mode else '0 (All 10 seeded)'}) ---")

    with Session(engine) as session:
        seed_database_if_empty(session, force=True)
        apps = session.exec(select(Application).order_by(Application.id)).all()
        print(f"[OK] Seeded {len(apps)} applications:")
        for a in apps:
            print(f"   • {a.institution_id}: {a.application_no} ({a.category})")

        print("\n--- Executing Scrutiny Pipeline (Cached OCR) ---")
        for a in apps:
            t0 = run_pipeline(a.id, session)
            session.refresh(a)
            print(f"   [OK] [{a.institution_id}] Risk: {a.risk_band} ({a.risk_score} pts) | Findings: {len(a.findings or [])}")

    print("\n[OK] Demo reset complete! Everything is seeded, cached, and ready for recording.")


def main():
    print("=" * 65)
    print(" PramaanAI Demo Environment Reset")
    print("=" * 65)
    reset_storage()
    reset_database()
    reseed_and_run()


if __name__ == "__main__":
    main()
