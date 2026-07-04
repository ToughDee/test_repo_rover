"""
LangGraph-based Agentic Query Engine for RepoRover.

Replaces the rigid LCEL chain (chain.py) with a dynamic StateGraph agent
that can reason over multiple steps, choosing which tools to call based
on the user's question.

Architecture:
  User Question → Agent (LLM) → [Tool Calls] → Agent → ... → Final Answer

The agent has access to:
  - search_codebase: semantic vector search
  - find_symbol_usages: graph MENTIONS traversal
  - get_call_chain: graph CALLS flow tracing
  - expand_graph_neighborhood: graph neighbor expansion
  - read_file: raw file reading
"""
from __future__ import annotations

from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.core.settings import settings
from app.infrastructure.neo4j_client import Neo4jClient
from app.llm.chat_model import get_chat_model
from app.query.tools import build_tools


# ---------------------------------------------------------------------------
# Agent State
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    """State that flows through the LangGraph agent."""
    messages: Annotated[list[BaseMessage], add_messages]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are RepoRover, an expert AI assistant for understanding codebases.

You have access to tools that let you search code, look up definitions, trace call graphs,
find dependencies, and read files from the indexed repository.

## Tool Selection Guide
- **"What does X do?"** → Use `get_definition` first to find the symbol, then `read_file` if you need more context.
- **"Where is X used?"** → Use `find_symbol_usages` to find files mentioning it, and `get_callers` for reverse call graph.
- **"Who calls X?"** → Use `get_callers` for the reverse call graph.
- **"How does X work?" / execution flow** → Use `get_call_chain` to trace what X calls downstream.
- **"What does this file depend on?"** → Use `get_file_dependencies` to see imports and dependents.
- **"Show me the project structure"** → Use `list_files` to browse indexed files.
- **General conceptual questions** → Use `search_codebase` with a detailed technical description.
- **Need to see full source code** → Use `read_file` with the file path.
- **Need related code** → Use `expand_graph_neighborhood` to discover structurally connected symbols.

## Rules
- ALWAYS use tools to gather evidence before answering. Never guess.
- Prefer `get_definition` over `search_codebase` when you know the exact symbol name.
- Cite specific file paths, function names, and line references.
- If you cannot find the answer, say so clearly and explain what you looked for.
- Keep answers structured with headers and code blocks for readability.
- You may call multiple tools in sequence to build a complete picture.
"""


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_agent_graph(neo4j: Neo4jClient, repo_id: str) -> StateGraph:
    """Builds a compiled LangGraph agent for a specific repo context."""

    tools = build_tools(neo4j, repo_id)
    tool_node = ToolNode(tools)

    # Bind tools to the LLM so it knows what's available
    llm = get_chat_model().bind_tools(tools)

    def agent_node(state: AgentState) -> dict:
        """The LLM reasoning node. Decides whether to call tools or respond."""
        messages = state["messages"]

        # Ensure system prompt is always first
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

        response = llm.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        """Route: if the last message has tool calls, go to tools. Otherwise, end."""
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    # Build the graph
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


# ---------------------------------------------------------------------------
# Public API (drop-in replacement for chain.py functions)
# ---------------------------------------------------------------------------

async def run_agent_query(
    neo4j: Neo4jClient,
    repo_id: str,
    question: str,
) -> tuple[str, int]:
    """
    Run the LangGraph agent and return (answer, tool_calls_count).
    Drop-in replacement for run_repo_query_chain.
    """
    if not settings.llm_api_key:
        return "LLM_API_KEY is missing. Set it in .env to enable answers.", 0

    agent = build_agent_graph(neo4j, repo_id)

    initial_state = {
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=question),
        ]
    }

    try:
        result = await agent.ainvoke(initial_state)
        messages = result["messages"]

        # The final message is the agent's answer
        answer = messages[-1].content if messages else "No response generated."

        # Count tool calls for diagnostics
        tool_calls = sum(
            1 for m in messages
            if hasattr(m, "tool_calls") and m.tool_calls
        )

        return answer, tool_calls

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Agent error: {e}", 0
