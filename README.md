# RepoRover (GraphRAG for Codebases)

RepoRover ingests local or remote Git repositories, extracts code structure (AST), builds a Neo4j code graph, adds embeddings for semantic search, and answers questions using hybrid retrieval + an API-based LLM.

## Quickstart (Neo4j Aura + API)

1) Create a free Neo4j Aura DB (no Docker):

- Create a DB and copy:
  - **Connection URI** (looks like `neo4j+s://...`)
  - **Username** (often `neo4j`)
  - **Password**

2) Create a Python venv and install deps:

```bash
cd repo-rover
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

3) Configure env:

```bash
copy .env.example .env
```

Edit `repo-rover/.env` and set:
- `NEO4J_URI` to your Aura **Connection URI**
- `NEO4J_USER` and `NEO4J_PASSWORD` to your Aura credentials
- `LLM_API_KEY` (e.g. Groq) and optionally `LLM_BASE_URL`.

4) Run the API (from the repository root):

```bash
uvicorn app.main:app --reload --port 8000
```

## Endpoints (MVP)
- `POST /ingest` (local path or remote git URL)
- `POST /query` (question + repo id)
- `GET /function/{name}` (basic lookup)
- `POST /graph/explore` (simple neighborhood expansion)

