import os
from pathlib import Path


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


BASE_DIR = Path(__file__).resolve().parent.parent
_load_dotenv()
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DATABASE_URL = f"sqlite:///{DATA_DIR / 'simulator.db'}"
SMTP_HOST = os.getenv("SIM_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SIM_SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SIM_SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SIM_SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SIM_SMTP_FROM", "")
SMTP_USE_TLS = os.getenv("SIM_SMTP_USE_TLS", "true").lower() == "true"
