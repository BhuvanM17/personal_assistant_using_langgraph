from typing import TypedDict, Annotated, Sequence, List, Dict, Any
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    """The state schema representing the current status of the agent session."""
    
    # The complete history of messages in the current conversation,
    # annotated with operator.add to merge new message updates
    messages: Annotated[Sequence[BaseMessage], operator.add]
    
    # User ID to identify memory scope
    user_id: str
    
    # The agent's current step-by-step plan
    plan: str | None
    
    # Information about the tool call that is pending human approval
    # e.g., {"tool": "draft_reply", "args": {...}}
    pending_action: Dict[str, Any] | None
    
    # Flag raised when an irreversible action is selected by the agent
    requires_confirmation: bool
    
    # Approval state populated when the human responds (True=Approve, False=Reject)
    human_approved: bool | None
    
    # Memories relevant to the current user's request pulled from vector db
    retrieved_memories: List[str]
    
    # Monotonically increasing counter to prevent infinite tool loops
    iteration_count: int
