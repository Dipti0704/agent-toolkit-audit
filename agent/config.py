import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
VERIFICATION_DIR = ROOT / "verification"

COMPOSIO_API_KEY = os.environ.get("COMPOSIO_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
RESEARCH_MODEL = os.environ.get("RESEARCH_MODEL", "gpt-5.4-nano")
MAX_CONCURRENCY = int(os.environ.get("MAX_CONCURRENCY", "8"))

APPS_SEED_PATH = DATA_DIR / "apps_seed.json"
PASS1_PATH = DATA_DIR / "pass1.json"
PASS2_PATH = DATA_DIR / "pass2.json"
FINAL_PATH = DATA_DIR / "final.json"
PATTERNS_PATH = DATA_DIR / "patterns.json"
VERIFICATION_REPORT_PATH = VERIFICATION_DIR / "accuracy_report.json"
HUMAN_SAMPLE_PATH = VERIFICATION_DIR / "human_sample.json"
