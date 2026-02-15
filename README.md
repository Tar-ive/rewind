# Rewind — AI-Powered Agentic Scheduling Engine

Rewind is a multi-agent system that autonomously manages your schedule using an OS-inspired three-tier scheduling engine. It monitors your Google Calendar, Gmail, and Slack in real-time, detects disruptions, rebalances your day, and can even draft and send emails or messages on your behalf — all while learning your behavioral patterns and energy levels.

Built with [Fetch.ai uAgents](https://uagents.fetch.ai/docs), [Composio](https://composio.dev), and [ElevenLabs](https://elevenlabs.io) voice AI.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                       │
│  Dashboard · Calendar · Integrations · Profile · Voice Agent    │
│                    ↕ WebSocket + REST API                       │
├─────────────────────────────────────────────────────────────────┤
│                   FastAPI Server (port 8000)                    │
│          REST endpoints · WebSocket manager · Redis             │
├─────────────────────────────────────────────────────────────────┤
│                    uAgents Framework (Fetch.ai)                 │
│                                                                 │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────┐  │
│  │   Context     │───▶│   Disruption     │───▶│  Scheduler   │  │
│  │   Sentinel    │    │   Detector       │    │  Kernel      │  │
│  │  (port 8004)  │    │  (port 8001)     │    │ (port 8002)  │  │
│  └──────────────┘    └──────────────────┘    └──────┬───────┘  │
│         ▲                     ▲                     │          │
│         │              ┌──────┴───────┐             ▼          │
│  ┌──────┴───────┐      │   Profiler   │      ┌────────────┐   │
│  │   Composio    │      │   Agent      │      │ GhostWorker│   │
│  │  (Gmail, Cal, │      └──────────────┘      │ (autonomous│   │
│  │  Slack, etc.) │                             │  execution)│   │
│  └──────────────┘      ┌──────────────┐       └────────────┘   │
│                        │   Energy      │                        │
│                        │   Monitor     │                        │
│                        └──────────────┘                         │
│                        ┌──────────────┐                         │
│                        │   Reminder    │                         │
│                        │   Agent       │                         │
│                        └──────────────┘                         │
├─────────────────────────────────────────────────────────────────┤
│              Three-Tier Scheduling Engine                       │
│     LTS (daily plan) → MTS (disruption recovery) → STS (MLFQ)  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agents

### Context Sentinel
Polls Google Calendar, Gmail, and Slack via Composio every 60 seconds. Detects context changes (meetings ending early, new emails, schedule conflicts) and emits `ContextChangeEvent` messages downstream.

### Disruption Detector
Classifies context changes by severity (minor/major/critical). Calculates freed or lost minutes from schedule changes. Queries the Profiler Agent for user patterns to improve classification. Emits `DisruptionEvent` to the Scheduler Kernel.

### Scheduler Kernel
The brain of Rewind. Orchestrates the three-tier scheduling engine:
- **LTS** — Daily planning: pulls tasks from backlog into today's schedule
- **MTS** — Disruption recovery: swaps tasks between active schedule and backlog
- **STS** — Real-time execution ordering via MLFQ with energy constraints

Auto-delegates P3 (low priority) tasks to GhostWorker when energy is low.

### Profiler Agent
Learns implicit behavioral patterns from task completion logs, schedule adherence, and external data (LinkedIn, GitHub, daily reflections). Outputs a `UserProfile` with peak hours, average task durations, energy curve, adherence score, distraction patterns, and estimation bias. Categorizes users into archetypes: Compounding Builder, Reliable Operator, Emerging Talent, or At Risk.

### Energy Monitor
Infers energy level (1-5) from behavioral signals: circadian baseline (time-of-day), task completion velocity, and user-reported energy (with 2-hour decay). Caches in Redis for real-time scheduling decisions.

### GhostWorker
Autonomously executes delegated tasks — email replies, Slack messages, LinkedIn posts, appointment cancellations. Drafts are created for user approval before execution. Uses Composio for delivery. Supports FET micropayments via Fetch.ai Payment Protocol.

### Reminder Agent
LLM-powered proactive notifications via Claude. Evaluates schedule context every 120 seconds and generates contextual reminders (upcoming tasks, check-ins, transitions). Respects snooze periods and cooldowns.

---

## Three-Tier Scheduling Engine

Inspired by Linux OS process scheduling:

| Tier | Trigger | Purpose | Algorithm |
|------|---------|---------|-----------|
| **LTS** | Daily / on-demand | Admit tasks from backlog to active schedule | Weighted scoring (deadline urgency 45%, priority 30%, peak hours 15%, SJF duration 15%) + bin-packing |
| **MTS** | Every disruption | Swap tasks between active and backlog | SWAP-IN (freed time) / SWAP-OUT (lost time) with energy-aware filtering |
| **STS** | Continuous | Order active tasks for execution | 4-level MLFQ (P0-P3), deadline urgency sorting, energy constraints, auto-delegation |

---

## Features

- **Real-time schedule adaptation** — Calendar changes trigger automatic rebalancing
- **Energy-aware scheduling** — Never assigns high-load tasks when energy is low
- **Autonomous task execution** — GhostWorker drafts emails, Slack messages, and more
- **Voice interface** — ElevenLabs conversational AI for hands-free task management
- **Behavioral profiling** — Learns your patterns over a 14-day sliding window
- **Task creation** — Dashboard form, voice commands, or API
- **Google Calendar sync** — New tasks automatically create calendar events
- **WebSocket real-time updates** — Dashboard updates instantly on any change
- **OAuth integrations** — Gmail, Google Calendar, Slack, LinkedIn via Composio
- **Draft review** — Approve, edit, or reject GhostWorker drafts before they're sent

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| Backend | FastAPI, Python 3.11+, uvicorn |
| Agents | Fetch.ai uAgents framework |
| Integrations | Composio SDK (Gmail, Google Calendar, Slack, LinkedIn) |
| Voice | ElevenLabs Conversational AI + LiveKit WebRTC |
| LLM | Anthropic Claude (Reminder Agent reasoning) |
| Database | Redis (task storage, state caching, vector indexes) |
| Charts | Recharts (profile visualizations) |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Redis server
- API keys: Composio, ElevenLabs, Anthropic

### 1. Install

```bash
git clone https://github.com/your-org/rewind.git
cd rewind

# Backend
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Frontend
cd frontend
npm install
```

### 2. Configure

Create `.env` in the project root:

```env
# Redis
REDIS_URL=redis://localhost:6379

# Composio
COMPOSIO_API_KEY=
COMPOSIO_USER_ID=rewind-user-001
GOOGLE_CALENDAR_AUTH_CONFIG_ID=
GMAIL_AUTH_CONFIG_ID=
SLACK_AUTH_CONFIG_ID=
LINKEDIN_AUTH_CONFIG_ID=
COMPOSIO_CALLBACK_URL=http://localhost:3000/auth/callback

# ElevenLabs
ELEVENLABS_API_KEY=
ELEVENLABS_AGENT_ID=

# Anthropic
ANTHROPIC_API_KEY=

# Deployment: "local" or "agentverse"
AGENT_DEPLOY_MODE=local
AGENT_ENDPOINT_BASE=http://localhost
```

### 3. Run

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Backend
source .venv/bin/activate && cd backend
python -m uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload

# Terminal 3: Agents
source .venv/bin/activate && cd backend
python -m src.agents.factory

# Terminal 4: Frontend
cd frontend && npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Deploying to Agentverse

All agents are pre-configured for [Agentverse](https://agentverse.ai) deployment via the mailbox pattern.

### 1. Set deployment mode

```env
AGENT_DEPLOY_MODE=agentverse
```

### 2. Run agents with mailbox

```bash
source .venv/bin/activate && cd backend
python -m src.agents.factory
```

Each agent prints a link to the **Local Agent Inspector**.

### 3. Connect to Agentverse

For each agent:
1. Open the Inspector URL printed in the terminal
2. Click **Connect** → select **Mailbox**
3. The agent is now registered and can receive messages while offline

### 4. Update agent addresses

After registration, update `.env` with the permanent Agentverse addresses:

```env
DISRUPTION_DETECTOR_ADDRESS=agent1q...
SCHEDULER_KERNEL_ADDRESS=agent1q...
PROFILER_AGENT_ADDRESS=agent1q...
ENERGY_MONITOR_ADDRESS=agent1q...
GHOST_WORKER_ADDRESS=agent1q...
REMINDER_AGENT_ADDRESS=agent1q...
```

### 5. (Optional) Publish to Marketplace

Add to each agent for discoverability:

```python
agent = Agent(
    name="rewind-scheduler-kernel",
    seed=SCHEDULER_KERNEL_SEED,
    mailbox=True,
    readme_path="README.md",
    publish_agent_details=True
)
```

### Deployment Options

| Method | Infrastructure | Best for |
|--------|---------------|----------|
| **Local** | Your machine | Development |
| **Mailbox** | Local + Agentverse message buffer | Production with your own infra |
| **Hosted** | Agentverse cloud | Lightweight agents, zero infra |
| **Proxy** | Local + Agentverse visibility | Marketplace discoverability |

See the [uAgents deployment guide](https://uagents.fetch.ai/docs/guides/types) and [Agentverse docs](https://innovationlab.fetch.ai/resources/docs/agentverse/) for more details.

---

## Project Structure

```
rewind/
├── backend/src/
│   ├── agents/           # 7 uAgents
│   │   ├── context_sentinel.py
│   │   ├── disruption_detector.py
│   │   ├── scheduler_kernel.py
│   │   ├── profiler_agent.py
│   │   ├── energy_monitor.py
│   │   ├── ghost_worker.py
│   │   ├── reminder_agent.py
│   │   └── factory.py        # Agent launcher
│   ├── engine/           # Scheduling algorithms
│   │   ├── lts.py            # Long-Term Scheduler
│   │   ├── mts.py            # Medium-Term Scheduler
│   │   ├── sts.py            # Short-Term Scheduler (MLFQ)
│   │   └── task_buffer.py    # Redis task storage
│   ├── models/
│   │   ├── task.py           # Task dataclass + Redis persistence
│   │   └── messages.py       # Inter-agent message types
│   ├── services/
│   │   └── composio_service.py  # Gmail, Calendar, Slack, LinkedIn
│   ├── config/
│   │   └── settings.py       # Environment config
│   ├── data_pipeline/        # Data parsing + embeddings
│   └── server.py             # FastAPI + WebSocket server
├── frontend/src/
│   ├── app/              # Pages
│   │   ├── page.tsx          # Dashboard (Today + Backlog + Voice)
│   │   ├── calendar/         # Google Calendar view
│   │   ├── integrations/     # OAuth connections
│   │   ├── profile/          # Behavioral insights
│   │   └── auth/callback/    # OAuth callback
│   ├── components/
│   │   ├── VoiceAgent.tsx    # ElevenLabs voice interface
│   │   ├── TaskInput.tsx     # Task creation form
│   │   ├── DraftReview.tsx   # GhostWorker draft review
│   │   └── AgentActivityLog.tsx
│   └── lib/
│       ├── useScheduleStore.ts   # State management
│       ├── useWebSocket.ts       # Real-time connection
│       └── useElevenLabsAgent.ts # Voice agent hook
├── data/                 # LinkedIn exports, goals, reflections
├── .env                  # Configuration
└── pyproject.toml        # Python dependencies
```

---

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/schedule` | Active tasks + backlog + energy |
| `POST` | `/api/tasks` | Create task (→ Redis + Calendar) |
| `DELETE` | `/api/tasks/{id}` | Remove task |
| `POST` | `/api/tasks/{id}/complete` | Mark complete |
| `POST` | `/api/tasks/{id}/start` | Start task |
| `POST` | `/api/schedule/plan-day` | Trigger LTS planning |
| `POST` | `/api/disruption` | Report disruption |
| `POST` | `/api/energy` | Update energy level |
| `GET` | `/api/calendar/events` | Google Calendar events |
| `POST` | `/api/calendar/events` | Create calendar event |
| `GET` | `/api/ghostworker/drafts` | Pending drafts |
| `POST` | `/api/ghostworker/drafts/{id}/approve` | Approve draft |
| `POST` | `/api/ghostworker/drafts/{id}/reject` | Reject draft |
| `GET` | `/api/auth/status` | Connected integrations |
| `POST` | `/api/auth/connect/{app}` | Start OAuth |
| `POST` | `/api/auth/disconnect` | Disconnect integration |
| `GET` | `/api/profile/full` | Profiler data |
| `WS` | `/ws` | Real-time updates |

---

## Inter-Agent Messages

```
Context Sentinel ──ContextChangeEvent──▶ Disruption Detector
Disruption Detector ──DisruptionEvent──▶ Scheduler Kernel
Energy Monitor ──EnergyLevel──▶ Scheduler Kernel
Profiler Agent ──UserProfile──▶ All Agents
Scheduler Kernel ──UpdatedSchedule──▶ Frontend (WebSocket)
Scheduler Kernel ──DelegationTask──▶ GhostWorker
GhostWorker ──TaskCompletion──▶ Scheduler Kernel
Reminder Agent ──ReminderNotification──▶ Frontend (Redis → WebSocket)
```

---

## License

MIT
