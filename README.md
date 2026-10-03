# Punish — Scientific Integrity Auditor

London AI x Science Hackathon, Track 2. An auditor agent that inspects another
science agent's reasoning traces and tool calls to detect reward hacking.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the system design and the JSON
schemas every component codes against.

## Setup

```bash
uv venv -p 3.11 && source .venv/bin/activate
uv pip install -e .
export ANTHROPIC_API_KEY=...   # or put it in .env (gitignored)
pytest
```

_Placeholder — usage and results to come._
