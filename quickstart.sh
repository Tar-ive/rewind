# 1. Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Fill in your keys

# 2. Start Redis
redis-server &

# 3. Run all agents (each in a separate terminal, or use the script)
python scripts/run_all_agents.py

# 4. Start backend
uvicorn backend.main:app --reload --port 8000

# 5. Start frontend
cd frontend && npm install && npm run dev

# 6. Register on Agentverse
python scripts/register_agents.py

# 7. Trigger demo disruption
python scripts/demo_trigger.py