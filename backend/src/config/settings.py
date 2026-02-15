"""Application-wide configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Redis
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

# Embedding model
EMBEDDING_MODEL: str = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
EMBEDDING_DIM: int = 384  # all-MiniLM-L6-v2 output dimension

# Data directory containing the raw JSON/CSV/MD files
DATA_DIR: Path = Path(
    os.getenv("DATA_DIR", str(Path(__file__).resolve().parent.parent.parent / "data"))
)

# File names inside DATA_DIR
LINKEDIN_FILE: str = "response_1762641602700.json"
TWITTER_FILE: str = "XPostExporter_saksham_adh_2025-11-08_16-19_20.csv"
GITHUB_FILE: str = "github_data.md"
CERTS_FILE: str = "Certifications.csv"
RESUME_FILE: str = "Saksham_CV.docx.md"
DAILY_GOALS_DIR: str = "daily_goals"
REFLECTIONS_DIR: str = "reflections"

# RedisVL index names
EXPLICIT_INDEX: str = "explicit_signals"
IMPLICIT_INDEX: str = "implicit_signals"

# ── Agent Configuration ──────────────────────────────────────────────────

# Agent seed phrases (deterministic address generation)
CONTEXT_SENTINEL_SEED: str = os.getenv(
    "CONTEXT_SENTINEL_SEED", "rewind-context-sentinel-seed-v1"
)
DISRUPTION_DETECTOR_SEED: str = os.getenv(
    "DISRUPTION_DETECTOR_SEED", "rewind-disruption-detector-seed-v1"
)
SCHEDULER_KERNEL_SEED: str = os.getenv(
    "SCHEDULER_KERNEL_SEED", "rewind-scheduler-kernel-seed-v1"
)
ENERGY_MONITOR_SEED: str = os.getenv(
    "ENERGY_MONITOR_SEED", "rewind-energy-monitor-seed-v1"
)
GHOST_WORKER_SEED: str = os.getenv(
    "GHOST_WORKER_SEED", "rewind-ghost-worker-seed-v1"
)
PROFILER_AGENT_SEED: str = os.getenv(
    "PROFILER_AGENT_SEED", "rewind-profiler-agent-seed-v1"
)

# Agent addresses (auto-generated from seeds, override for production)
DISRUPTION_DETECTOR_ADDRESS: str = os.getenv("DISRUPTION_DETECTOR_ADDRESS", "")
SCHEDULER_KERNEL_ADDRESS: str = os.getenv("SCHEDULER_KERNEL_ADDRESS", "")
PROFILER_AGENT_ADDRESS: str = os.getenv("PROFILER_AGENT_ADDRESS", "")
ENERGY_MONITOR_ADDRESS: str = os.getenv("ENERGY_MONITOR_ADDRESS", "")
GHOST_WORKER_ADDRESS: str = os.getenv("GHOST_WORKER_ADDRESS", "")

# Scheduling engine defaults
TASK_BUCKET_COUNT: int = int(os.getenv("TASK_BUCKET_COUNT", "16"))
DEFAULT_AVAILABLE_HOURS: int = int(os.getenv("DEFAULT_AVAILABLE_HOURS", "8"))
DEFAULT_ENERGY_LEVEL: int = int(os.getenv("DEFAULT_ENERGY_LEVEL", "3"))

# ── Composio Configuration ──────────────────────────────────────────────

COMPOSIO_API_KEY: str = os.getenv("COMPOSIO_API_KEY", "")
COMPOSIO_USER_ID: str = os.getenv("USER_ID", "rewind-user-001")

# Auth Config IDs for Composio tool groups (from Composio dashboard)
GOOGLE_CALENDAR_AUTH_CONFIG_ID: str = os.getenv("GOOGLE_CALENDAR_AUTH_CONFIG_ID", "")
GMAIL_AUTH_CONFIG_ID: str = os.getenv("GMAIL_AUTH_CONFIG_ID", "")
SLACK_AUTH_CONFIG_ID: str = os.getenv("SLACK_AUTH_CONFIG_ID", "")
LINKEDIN_AUTH_CONFIG_ID: str = os.getenv("LINKEDIN_AUTH_CONFIG_ID", "")
COMPOSIO_CALLBACK_URL: str = os.getenv("COMPOSIO_CALLBACK_URL", "http://localhost:3000/auth/callback")

# ── Context Sentinel Polling ────────────────────────────────────────────

SENTINEL_POLL_INTERVAL: int = int(os.getenv("SENTINEL_POLL_INTERVAL", "60"))
CALENDAR_LOOKAHEAD_HOURS: int = int(os.getenv("CALENDAR_LOOKAHEAD_HOURS", "24"))
GMAIL_LOOKBACK_HOURS: int = int(os.getenv("GMAIL_LOOKBACK_HOURS", "2"))

# ── Profiler Configuration ────────────────────────────────────────────────

PROFILER_SLIDING_WINDOW_DAYS: int = int(os.getenv("PROFILER_SLIDING_WINDOW_DAYS", "14"))
PROFILER_DECAY_FACTOR: float = float(os.getenv("PROFILER_DECAY_FACTOR", "0.85"))
PROFILER_RECOMPUTE_INTERVAL: int = int(os.getenv("PROFILER_RECOMPUTE_INTERVAL", "1800"))  # 30 min
PROFILER_DRIFT_THRESHOLD: float = float(os.getenv("PROFILER_DRIFT_THRESHOLD", "0.15"))

# ── Agent Deployment ─────────────────────────────────────────────────────

# Set to "agentverse" to deploy on Agentverse (uses mailbox, no local endpoint).
# Set to "local" (default) for local dev with localhost endpoints.
AGENT_DEPLOY_MODE: str = os.getenv("AGENT_DEPLOY_MODE", "local")
AGENT_ENDPOINT_BASE: str = os.getenv("AGENT_ENDPOINT_BASE", "http://localhost")

# ── Server Configuration ─────────────────────────────────────────────────

SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
