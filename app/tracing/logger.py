import os
import json
from datetime import datetime
from typing import Any, Dict

# Define logs file path
LOGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../logs"))
TRACE_FILE = os.path.join(LOGS_DIR, "trace.jsonl")

def write_trace(event_type: str, data: Dict[str, Any]) -> None:
    """Appends a single line to logs/trace.jsonl containing trace data.
    
    Args:
        event_type: The type of event (e.g. 'node_entry', 'node_exit', 'tool_call', 'tool_result').
        data: Additional dictionary metadata to include in the trace.
    """
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        
        trace_record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            **data
        }
        
        # Append record to trace.jsonl
        with open(TRACE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace_record) + "\n")
            
    except Exception as e:
        # Prevent logging errors from crashing the main application flow
        print(f"[Warning] Failed to write trace log: {str(e)}")
