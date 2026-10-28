import os
from pathlib import Path
from typing import Any, Dict
import yaml

# Base directory paths
APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = DATA_DIR / "config"
MOCK_SOURCES_DIR = DATA_DIR / "mock_sources"
APPLICATIONS_DIR = DATA_DIR / "applications"
LABELS_DIR = DATA_DIR / "labels"

STORAGE_DIR = BACKEND_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
(STORAGE_DIR / "ela").mkdir(parents=True, exist_ok=True)
(STORAGE_DIR / "briefs").mkdir(parents=True, exist_ok=True)
(STORAGE_DIR / "uploads").mkdir(parents=True, exist_ok=True)
(STORAGE_DIR / "ocr_cache").mkdir(parents=True, exist_ok=True)
(STORAGE_DIR / "cache").mkdir(parents=True, exist_ok=True)

DB_PATH = STORAGE_DIR / "app.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

def load_yaml(file_path: Path) -> Dict[str, Any]:
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

class ConfigRegistry:
    def __init__(self):
        self.reload()

    def reload(self):
        self.APPLICATIONS_DIR = APPLICATIONS_DIR
        self.CONFIG_DIR = CONFIG_DIR
        self.DATA_DIR = DATA_DIR
        self.STORAGE_DIR = STORAGE_DIR
        self.checklists = load_yaml(CONFIG_DIR / "checklists.yaml")
        self.consistency = load_yaml(CONFIG_DIR / "consistency.yaml")
        self.doc_types = load_yaml(CONFIG_DIR / "doc_types.yaml")
        self.risk = load_yaml(CONFIG_DIR / "risk.yaml")
        self.rules = load_yaml(CONFIG_DIR / "rules.yaml")

    def raw_rules_yaml(self) -> str:
        rules_path = CONFIG_DIR / "rules.yaml"
        if rules_path.exists():
            with open(rules_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

settings = ConfigRegistry()
