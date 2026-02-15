#!/usr/bin/env python3
"""Launch the FastAPI server and all 6 Rewind agents in one process.

Usage:
    # From the backend/ directory with the venv activated:
    python scripts/run_all.py

    # Or from the repo root:
    python backend/scripts/run_all.py

Each agent runs on its own port via uAgents' built-in asyncio loop.
The FastAPI server runs via uvicorn in a separate thread.

Ports:
    8000  FastAPI server  (REST + WebSocket)
    8001  Disruption Detector
    8002  Scheduler Kernel
    8003  Energy Monitor
    8004  Context Sentinel
    8005  GhostWorker
    8006  Profiler Agent
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import signal
import sys
import time
from pathlib import Path

# Ensure backend/ is on sys.path so `from src.…` imports work
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)-22s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_all")


# ── Process targets ──────────────────────────────────────────────────────

def _run_server():
    """Run the FastAPI server via uvicorn."""
    import uvicorn
    uvicorn.run(
        "src.server:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False,
    )


def _run_agent(factory_name: str, port: int):
    """Import and run a single agent from the factory."""
    from src.agents.factory import (
        create_context_sentinel,
        create_disruption_detector,
        create_energy_monitor,
        create_ghost_worker,
        create_profiler_agent,
        create_scheduler_kernel,
    )

    factories = {
        "context_sentinel": create_context_sentinel,
        "disruption_detector": create_disruption_detector,
        "scheduler_kernel": create_scheduler_kernel,
        "energy_monitor": create_energy_monitor,
        "ghost_worker": create_ghost_worker,
        "profiler_agent": create_profiler_agent,
    }

    factory_fn = factories[factory_name]
    agent = factory_fn(port=port)
    logger.info("Starting %s on port %d (address: %s)", factory_name, port, agent.address)
    agent.run()


# ── Agent definitions ────────────────────────────────────────────────────

AGENTS = [
    ("disruption_detector", 8001),
    ("scheduler_kernel",    8002),
    ("energy_monitor",      8003),
    ("context_sentinel",    8004),
    ("ghost_worker",        8005),
    ("profiler_agent",      8006),
]


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("  REWIND — The Intelligent Life Scheduler")
    logger.info("=" * 60)
    logger.info("")
    logger.info("  FastAPI server  →  http://localhost:8000")
    logger.info("  WebSocket       →  ws://localhost:8000/ws")
    logger.info("")
    for name, port in AGENTS:
        logger.info("  %-22s →  port %d", name, port)
    logger.info("")
    logger.info("  Press Ctrl+C to stop all processes")
    logger.info("=" * 60)

    processes: list[multiprocessing.Process] = []

    # Start FastAPI server
    p = multiprocessing.Process(target=_run_server, name="fastapi-server", daemon=True)
    p.start()
    processes.append(p)
    logger.info("FastAPI server started (pid %d)", p.pid)

    # Give the server a moment to bind its port
    time.sleep(1)

    # Start all agents
    for name, port in AGENTS:
        p = multiprocessing.Process(
            target=_run_agent,
            args=(name, port),
            name=f"agent-{name}",
            daemon=True,
        )
        p.start()
        processes.append(p)
        logger.info("Agent %s started (pid %d, port %d)", name, p.pid, port)
        time.sleep(0.3)  # slight stagger to avoid port collisions

    logger.info("")
    logger.info("All %d processes running. Waiting...", len(processes))

    # Wait for Ctrl+C
    def _shutdown(signum, frame):
        logger.info("")
        logger.info("Shutting down all processes...")
        for proc in processes:
            if proc.is_alive():
                proc.terminate()
        for proc in processes:
            proc.join(timeout=5)
            if proc.is_alive():
                proc.kill()
        logger.info("All processes stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Keep main process alive — restart any crashed children
    while True:
        for proc in processes:
            if not proc.is_alive():
                logger.warning("Process %s (pid %d) exited with code %s", proc.name, proc.pid, proc.exitcode)
        time.sleep(5)


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)
    main()
