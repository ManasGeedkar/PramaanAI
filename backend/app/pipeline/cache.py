import json
from pathlib import Path
from typing import Optional, Any
from app.config import STORAGE_DIR

CACHE_DIR = STORAGE_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def get_cached(sha256: Optional[str], category: str) -> Optional[Any]:
    """Retrieves cached json data by document sha256 and category."""
    if not sha256:
        return None
    cache_file = CACHE_DIR / f"{sha256}_{category}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def set_cached(sha256: Optional[str], category: str, data: Any) -> None:
    """Stores json data in cache keyed by document sha256 and category."""
    if not sha256:
        return
    cache_file = CACHE_DIR / f"{sha256}_{category}.json"
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass
