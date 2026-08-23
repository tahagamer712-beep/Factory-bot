import os
from pathlib import Path

def _load_env_file(path: Path):
    """Minimal .env loader (replaces python-dotenv - zero pip dependency).
    Supports KEY=VALUE lines, '#' comments, blank lines, and optional
    quotes around the value. Existing environment variables always win,
    matching python-dotenv's default (load_dotenv() doesn't override
    already-set vars)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

_load_env_file(Path.home() / "factory" / ".env")

BASE_DIR = Path.home() / "factory"
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = BASE_DIR / "backups"
LOGS_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = DATA_DIR / "factory.db"
LOG_FILE = LOGS_DIR / "factory.log"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
LONG_POLL_TIMEOUT = int(os.getenv("LONG_POLL_TIMEOUT", "30"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
DEFAULT_RATE_LIMIT = int(os.getenv("DEFAULT_RATE_LIMIT", "30"))
MESSAGE_RETENTION_DAYS = int(os.getenv("MESSAGE_RETENTION_DAYS", "7"))
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "7"))
JOB_RETENTION_DAYS = int(os.getenv("JOB_RETENTION_DAYS", "1"))
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))
MEMORY_THRESHOLD_MB = int(os.getenv("MEMORY_THRESHOLD_MB", "300"))

# The master "factory" bot - the one users message to create their own
# bots (send it a token, get a new bot registered and polling live). Set
# FACTORY_BOT_TOKEN in .env to enable it. bot_id is just the numeric
# prefix of any Telegram bot token, before the ':'.
FACTORY_BOT_TOKEN = os.getenv("FACTORY_BOT_TOKEN", "").strip()
FACTORY_BOT_ID = int(FACTORY_BOT_TOKEN.split(":")[0]) if ":" in FACTORY_BOT_TOKEN else None

# Telegram user ID allowed to access the factory-level admin panel.  The
# master bot ID remains the implicit owner for backwards compatibility, while
# this setting lets the human operator manage the factory from their account.
_factory_admin_id = os.getenv("FACTORY_ADMIN_ID", "").strip()
FACTORY_ADMIN_ID = int(_factory_admin_id) if _factory_admin_id.isdigit() else None
