# Sims 1 Compatibility Checker

Figure out which sims should talk to whom, based on shared interests and personality compatibility.

Drop your `UserData/` folder from The Sims 1 (Complete Collection / Legacy) into the project root and start the servers.

## Setup

```bash
# Backend
uv run fastapi dev api/main.py

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173

## How it works

The backend parses `UserData/Neighborhood.iff` to extract each sim's interests (8 categories, 0-1000 scale) and personality traits. It then scores compatibility between any two sims:

- **Interest match (70%)** — shared interests boost the score, conflicting ones penalize it
- **Personality match (30%)** — sims with high Outgoing, Playful, and Nice are easier to befriend

Select a sim in the UI to see a ranked list of who they'd get along with best.
