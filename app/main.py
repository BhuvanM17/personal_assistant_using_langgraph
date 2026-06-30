import os
import sys
import json
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from app.config import config
from app.db.session import init_db, get_db
from app.db.models import Task
from app.agent.graph import app_graph


app = FastAPI(title="Personal Assistant API")

# Configure CORS for local frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize SQLite database on startup
@app.on_event("startup")
def startup_event():
    init_db()

class ChatRequest(BaseModel):
    message: str
    user_id: str

class ConfirmRequest(BaseModel):
    user_id: str
    approved: bool


def _format_pending_action_message(pending_action: dict | None) -> str:
    """Builds a user-friendly confirmation prompt for the pending tool action."""
    if not pending_action:
        return "I need your confirmation before I continue."

    tool = pending_action.get("tool", "")
    args = pending_action.get("args", {})

    if tool == "send_reply":
        return (
            f"I've prepared a reply for thread `{args.get('thread_id', '')}`. "
            "Approve it and I'll send it."
        )
    if tool == "delete_calendar_event":
        return (
            f"I found the calendar event `{args.get('event_id', '')}`. "
            "Approve it and I'll delete it."
        )

    if tool == "complete_task":
        return (
            f"I found task `{args.get('task_id', '')}`. "
            "Approve it and I'll mark it complete."
        )

    return "I need your confirmation before I continue."

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """Processes user input. Starts or continues a StateGraph thread session."""
    thread_id = f"thread_{req.user_id}"
    run_config = {"configurable": {"thread_id": thread_id}}
    
    # 1. Check if graph is already paused at confirm_node
    state_info = app_graph.get_state(run_config)
    if state_info and state_info.next and state_info.next[0] == "confirm_node":
        pending = state_info.values.get("pending_action")
        return {
            "response": _format_pending_action_message(pending),
            "pending_action": pending
        }
        
    # 2. Run graph with new message
    inputs = {
        "messages": [HumanMessage(content=req.message)],
        "user_id": req.user_id,
        "iteration_count": 0,
        "requires_confirmation": False,
        "human_approved": None
    }
    
    try:
        # Stream the graph execution until completion or confirmation pause
        for event in app_graph.stream(inputs, run_config, stream_mode="values"):
            pass
            
        # Fetch status after stream halts
        updated_state = app_graph.get_state(run_config)
        next_nodes = updated_state.next
        
        # If interrupted before confirm_node, return the pending action
        if next_nodes and next_nodes[0] == "confirm_node":
            pending = updated_state.values.get("pending_action")
            return {
                "response": _format_pending_action_message(pending),
                "pending_action": pending
            }
            
        # Parse final response message
        messages = updated_state.values.get("messages", [])
        response_text = "Task completed successfully."
        if messages:
            # Look for the last AI response (which is the output of respond_node)
            for msg in reversed(messages):
                if msg.type == "ai" and not (hasattr(msg, "tool_calls") and msg.tool_calls):
                    response_text = msg.content
                    break
                    
        return {
            "response": response_text,
            "pending_action": None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent Error: {str(e)}")

@app.post("/confirm")
async def confirm_endpoint(req: ConfirmRequest):
    """Resumes the graph execution after human confirmation (approving or rejecting)."""
    thread_id = f"thread_{req.user_id}"
    run_config = {"configurable": {"thread_id": thread_id}}
    
    # 1. Verify the thread is currently paused at confirm_node
    state_info = app_graph.get_state(run_config)
    if not state_info or not state_info.next or state_info.next[0] != "confirm_node":
        raise HTTPException(status_code=400, detail="No pending actions found needing confirmation.")
        
    # 2. Inject decision into the state
    app_graph.update_state(
        run_config,
        {"human_approved": req.approved}
    )
    
    try:
        # 3. Resume the graph (passing None will resume from previous checkpoint)
        for event in app_graph.stream(None, run_config, stream_mode="values"):
            pass
            
        # Inspect final state
        updated_state = app_graph.get_state(run_config)
        next_nodes = updated_state.next
        
        # In case another tool call in the loop also needs validation
        if next_nodes and next_nodes[0] == "confirm_node":
            pending = updated_state.values.get("pending_action")
            return {
                "response": _format_pending_action_message(pending),
                "pending_action": pending
            }
            
        messages = updated_state.values.get("messages", [])
        response_text = "Task processed."
        if messages:
            for msg in reversed(messages):
                if msg.type == "ai" and not (hasattr(msg, "tool_calls") and msg.tool_calls):
                    response_text = msg.content
                    break
                    
        return {
            "response": response_text,
            "pending_action": None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent Confirmation Error: {str(e)}")

@app.get("/tasks")
async def list_tasks_endpoint(status: str = "open"):
    """Bypasses agent graph to list tasks directly from the SQLite database."""
    try:
        with get_db() as db:
            tasks = db.query(Task).filter(Task.status == status).order_by(Task.created_at.desc()).all()
            return [t.to_dict() for t in tasks]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

@app.get("/health")
async def health_endpoint():
    """Liveness check for API service."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@app.get("/calendar")
async def calendar_endpoint(max_results: int = 10):
    """Returns upcoming Google Calendar events for the sidebar widget."""
    try:
        from app.auth.google_auth import get_calendar_service
        service = get_calendar_service()
        
        now = datetime.utcnow().isoformat() + "Z"
        events_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        
        events = events_result.get("items", [])
        results = []
        for event in events:
            results.append({
                "event_id": event["id"],
                "summary": event.get("summary", "(No title)"),
                "start": event["start"].get("dateTime", event["start"].get("date")),
                "end": event["end"].get("dateTime", event["end"].get("date")),
                "description": event.get("description", ""),
                "location": event.get("location", ""),
            })
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calendar error: {str(e)}")

@app.get("/trace")
async def trace_endpoint(limit: int = 20):
    """Exposes the last N lines of trace.jsonl for frontend visualization."""
    from app.tracing.logger import TRACE_FILE
    if not os.path.exists(TRACE_FILE):
        return []
    try:
        with open(TRACE_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        last_lines = lines[-limit:]
        
        traces = []
        for line in last_lines:
            line_str = line.strip()
            if line_str:
                try:
                    traces.append(json.loads(line_str))
                except Exception:
                    pass
        return traces
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load traces: {str(e)}")
