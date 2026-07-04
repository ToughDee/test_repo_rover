# RepoRover (Agentic Codebase Intelligence)

RepoRover is a decoupled, microservices-based intelligence platform for analyzing codebases. It extracts code structure via Tree-Sitter ASTs, builds a semantic Knowledge Graph in Neo4j, and uses an autonomous LangGraph Agent to answer deep architectural questions.

## Architecture

The system has been refactored into three distinct layers:
1. **Python AI Worker (`app/`)**: A FastAPI microservice handling heavy AST extraction, incremental graph ingestion, and the LangGraph Agent reasoning loop.
2. **Node.js Orchestrator (`orchestrator/`)**: An Express.js backend that manages state (MongoDB), handles incremental file diffing, and routes API requests to the Python worker.
3. **React Frontend (`frontend/`)**: A Vite-powered React UI providing a workspace dashboard and an interactive 2D Graph Explorer.

## Quickstart

### Prerequisites
- Neo4j Aura DB (or local Neo4j instance)
- MongoDB (or MongoDB Atlas)
- Node.js (v18+)
- Python 3.10+

### 1. Setup Python Worker (FastAPI)
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```
Ensure your `.env` contains your `NEO4J_URI`, `NEO4J_PASSWORD`, and `OPENAI_API_KEY` (or equivalent).
Start the worker:
```bash
uvicorn app.worker_main:app --reload --port 8000
```

### 2. Setup Node.js Orchestrator
Open a new terminal:
```bash
cd orchestrator
npm install
copy .env.example .env
```
Ensure your orchestrator `.env` has `MONGO_URI`, `NEO4J_URI`, and points `PYTHON_WORKER_URL=http://localhost:8000`.
Start the orchestrator:
```bash
npm run dev
# Runs on http://localhost:5000
```

### 3. Setup React Frontend
Open a third terminal:
```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:5173
```

## Features
- **Incremental Indexing**: The Node.js orchestrator hashes files and only sends modified/added/deleted files to the Python worker, making re-indexing extremely fast.
- **Semantic FQNs**: Nodes in Neo4j use Fully Qualified Names (e.g., `file.py::Class.method`) to ensure idempotent updates.
- **LangGraph Agent**: The query interface uses an autonomous StateGraph loop that can trigger tools like `get_definition`, `get_callers`, and `expand_graph_neighborhood`.
- **Interactive UI**: A Vercel/Linear-inspired interface featuring a 2D canvas of your actual code topology.
