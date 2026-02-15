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

# RedisVL index names
EXPLICIT_INDEX: str = "explicit_signals"
IMPLICIT_INDEX: str = "implicit_signals"

# ── Agent Configuration ──────────────────────────────────────────────────

# Agent seed phrases (deterministic address generation)
DISRUPTION_DETECTOR_SEED: str = os.getenv(
    "DISRUPTION_DETECTOR_SEED", "rewind-disruption-detector-seed-v1"
)
SCHEDULER_KERNEL_SEED: str = os.getenv(
    "SCHEDULER_KERNEL_SEED", "rewind-scheduler-kernel-seed-v1"
)

# Agent addresses (auto-generated from seeds, override for production)
SCHEDULER_KERNEL_ADDRESS: str = os.getenv("SCHEDULER_KERNEL_ADDRESS", "")
PROFILER_AGENT_ADDRESS: str = os.getenv("PROFILER_AGENT_ADDRESS", "")
ENERGY_MONITOR_ADDRESS: str = os.getenv("ENERGY_MONITOR_ADDRESS", "")

# Scheduling engine defaults
TASK_BUCKET_COUNT: int = int(os.getenv("TASK_BUCKET_COUNT", "16"))
DEFAULT_AVAILABLE_HOURS: int = int(os.getenv("DEFAULT_AVAILABLE_HOURS", "8"))
DEFAULT_ENERGY_LEVEL: int = int(os.getenv("DEFAULT_ENERGY_LEVEL", "3"))
