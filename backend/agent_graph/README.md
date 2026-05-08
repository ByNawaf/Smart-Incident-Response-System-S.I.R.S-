# S.I.R.S Agent Graph

FastAPI remains the web/API layer. LangGraph is the internal agent orchestration engine.

Workflow:

1. Camera Vision Agent
2. Traffic Agent
3. Emergency Agent
4. Environment Agent
5. Analysis Agent
6. Coordinator Agent
7. Validation Node

Each node receives the shared incident state, calls backend tools, optionally asks local Qwen/Ollama for reasoning text, and returns structured outputs. Critical operational values such as dispatched units, ETA, route provider, and incident status are validated by backend guardrails and are not allowed to be overwritten by the LLM.

Install dependencies with:

```bash
pip install -r requirements.txt
```

Check engine status:

```text
GET /api/agent-graph/status
```
