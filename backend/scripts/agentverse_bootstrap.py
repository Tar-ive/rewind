#!/usr/bin/env python3
"""
agentverse_bootstrap.py
========================

Automates Agentverse setup for the Rewind agents:

1. Instantiates each uAgent factory to derive deterministic agent IDs.
2. Updates .env with the addresses so cross-agent messaging works.
3. Optionally prints a JSON blob that can be piped into other tooling.

The script does **not** run the agents. Use the Fetch.ai `aea` CLI (see repo docs)
to launch/deploy them with `mailbox=<AGENTVERSE_API_KEY>` once the addresses are
written to the environment file.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict

from dotenv import load_dotenv

# Ensure backend modules are importable
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

try:
    from src.agents import factory  # type: ignore  # pylint: disable=wrong-import-position
except ModuleNotFoundError as exc:  # pragma: no cover - import guard
    missing = exc.name
    raise SystemExit(
        f"Failed to import project modules ({missing!r} missing). "
        "Install backend dependencies first, e.g. `pip install -e backend` "
        "from the repo root."
    ) from exc


@dataclass(frozen=True)
class AgentSpec:
    env_key: str
    factory_fn: Callable[[], "factory.Agent"]
    description: str


AGENT_SPECS: tuple[AgentSpec, ...] = (
    AgentSpec(
        env_key="CONTEXT_SENTINEL_ADDRESS",
        factory_fn=factory.create_context_sentinel,
        description="Context Sentinel",
    ),
    AgentSpec(
        env_key="DISRUPTION_DETECTOR_ADDRESS",
        factory_fn=factory.create_disruption_detector,
        description="Disruption Detector",
    ),
    AgentSpec(
        env_key="SCHEDULER_KERNEL_ADDRESS",
        factory_fn=factory.create_scheduler_kernel,
        description="Scheduler Kernel",
    ),
    AgentSpec(
        env_key="ENERGY_MONITOR_ADDRESS",
        factory_fn=factory.create_energy_monitor,
        description="Energy Monitor",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Derive agent addresses and update the .env file."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=REPO_ROOT / ".env",
        help="Path to the .env file to update (default: repo root .env).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and print addresses without writing to .env.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the address map as JSON for downstream scripts.",
    )
    parser.add_argument(
        "--check-cli",
        action="store_true",
        help="Also verify that the Fetch.ai `aea` CLI is installed.",
    )
    return parser.parse_args()


def ensure_cli_available() -> None:
    if shutil.which("aea") is None:
        raise SystemExit(
            "aea CLI not found on PATH. Install it per Fetch.ai docs "
            "before attempting to deploy agents."
        )


def compute_addresses() -> Dict[str, str]:
    addresses: Dict[str, str] = {}
    for spec in AGENT_SPECS:
        agent = spec.factory_fn()
        addresses[spec.env_key] = agent.address
    return addresses


def update_env_file(path: Path, updates: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines: list[str] = []
    if path.exists():
        existing_lines = path.read_text().splitlines()

    processed_keys = set()
    new_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            new_lines.append(line)
            continue
        key, _ = line.split("=", 1)
        key = key.strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            processed_keys.add(key)
        else:
            new_lines.append(line)

    for key, value in updates.items():
        if key not in processed_keys:
            new_lines.append(f"{key}={value}")

    path.write_text("\n".join(new_lines) + "\n")


def main() -> None:
    args = parse_args()
    env_path = args.env_file.resolve()

    load_dotenv(dotenv_path=env_path, override=False)

    if args.check_cli:
        ensure_cli_available()

    addresses = compute_addresses()

    print("Derived Agentverse addresses:")
    for spec in AGENT_SPECS:
        addr = addresses[spec.env_key]
        print(f"  {spec.description:<20} {spec.env_key} = {addr}")

    if args.json:
        print(json.dumps(addresses, indent=2))

    if args.dry_run:
        print("Dry run requested; .env not modified.")
        return

    update_env_file(env_path, addresses)
    print(f"Updated {env_path} with {len(addresses)} agent address(es).")
    print(
        "Next: use the `aea run`/`aea launch` commands (with mailbox set to "
        "your AGENTVERSE_API_KEY) to bring each agent online."
    )


if __name__ == "__main__":
    main()
