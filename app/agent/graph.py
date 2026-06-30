import sqlite3
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import ToolMessage

from app.config import config
from app.agent.state import AgentState
from app.agent.nodes import plan_node, act_node, confirm_node, observe_node, respond_node

# Create SQLite connection for checkpoints database
import os
db_path = config.CHECKPOINTS_DATABASE_URL
if db_path.startswith("sqlite:///"):
    db_path = db_path.replace("sqlite:///", "")

# Ensure the parent directory exists
db_dir = os.path.dirname(db_path)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

conn = sqlite3.connect(
    db_path, 
    check_same_thread=False
)
checkpointer = SqliteSaver(conn)

# Define conditional routing helper functions

def route_after_plan(state: AgentState) -> Literal["act_node", "respond_node"]:
    """Routes to act_node if the LLM generated tool calls, otherwise to respond_node."""
    messages = state.get("messages", [])
    if not messages:
        return "respond_node"
        
    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "act_node"
        
    return "respond_node"

def route_after_act(state: AgentState) -> Literal["confirm_node", "observe_node"]:
    """Routes to confirm_node if the action is flagged as irreversible, otherwise to observe_node."""
    if state.get("requires_confirmation"):
        return "confirm_node"
    return "observe_node"

def route_after_confirm(state: AgentState) -> Literal["observe_node", "respond_node"]:
    """Routes to respond_node if the user rejected the confirmation, otherwise to observe_node."""
    messages = state.get("messages", [])
    if messages and isinstance(messages[-1], ToolMessage):
        content = messages[-1].content
        if "rejected" in content or "cancelled" in content:
            return "respond_node"
    return "observe_node"

def route_after_observe(state: AgentState) -> Literal["plan_node", "respond_node"]:
    """Halts execution and responds if the iteration limit is hit, otherwise loops back to plan."""
    iteration = state.get("iteration_count", 0)
    if iteration >= config.MAX_AGENT_ITERATIONS:
        # Force terminate loop to prevent runaway API spend
        return "respond_node"
    return "plan_node"

# Construct the StateGraph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("plan_node", plan_node)
workflow.add_node("act_node", act_node)
workflow.add_node("confirm_node", confirm_node)
workflow.add_node("observe_node", observe_node)
workflow.add_node("respond_node", respond_node)

# Add Edges
workflow.set_entry_point("plan_node")

# Conditional edges
workflow.add_conditional_edges(
    "plan_node",
    route_after_plan,
    {
        "act_node": "act_node",
        "respond_node": "respond_node"
    }
)

workflow.add_conditional_edges(
    "act_node",
    route_after_act,
    {
        "confirm_node": "confirm_node",
        "observe_node": "observe_node"
    }
)

workflow.add_conditional_edges(
    "confirm_node",
    route_after_confirm,
    {
        "observe_node": "observe_node",
        "respond_node": "respond_node"
    }
)

workflow.add_conditional_edges(
    "observe_node",
    route_after_observe,
    {
        "plan_node": "plan_node",
        "respond_node": "respond_node"
    }
)

# respond_node always exits
workflow.add_edge("respond_node", END)

# Compile the graph
# We interrupt *before* confirm_node execution starts, so it saves state
# and yields control when pending_action is populated.
app_graph = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["confirm_node"]
)
