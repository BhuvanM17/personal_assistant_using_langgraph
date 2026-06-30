from typing import List, Set
from langchain_core.tools import BaseTool
from app.tools.gmail_tools import read_emails, draft_reply, get_email_body, search_emails, send_reply
from app.tools.task_tools import add_task, list_tasks, complete_task
from app.tools.calendar_tools import create_calendar_event, list_calendar_events, delete_calendar_event


# List of all tools available to the LLM
ALL_TOOLS: List[BaseTool] = [
    # Gmail tools
    read_emails,
    search_emails,
    get_email_body,
    draft_reply,
    send_reply,
    # Calendar tools
    create_calendar_event,
    list_calendar_events,
    delete_calendar_event,

    # Task management tools
    add_task,
    list_tasks,
    complete_task,
]

# Set of tool names that represent irreversible actions needing human validation
IRREVERSIBLE_TOOLS: Set[str] = {
    "send_reply",

    "complete_task",
    "delete_calendar_event",
}

def get_tool_map():
    """Returns a lookup mapping from tool name to tool instance."""
    return {tool.name: tool for tool in ALL_TOOLS}
