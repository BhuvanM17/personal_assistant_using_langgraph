import sys
from datetime import datetime
from typing import Dict, Any
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import config
from app.agent.state import AgentState
from app.agent.llm import get_llm
from app.tools.tool_registry import get_tool_map, IRREVERSIBLE_TOOLS
from app.memory.vector_memory import retrieve_memories, store_memory
from app.tracing.logger import write_trace

SYSTEM_PROMPT_TEMPLATE = """You are Bhuvan's personal AI assistant — smart, proactive, and efficient.
You manage emails (Gmail), calendar (Google Calendar), and tasks seamlessly.

Current Date/Time: {current_time}
Timezone: Asia/Kolkata (IST, UTC+5:30)

User Preferences & Remembered Facts:
{memories}

═══════════════════════════════════════════
AVAILABLE CAPABILITIES:
═══════════════════════════════════════════

📧 EMAIL (Gmail):
  • read_emails — List emails with Gmail search query (supports: is:unread, from:X, subject:X, newer_than:Xd)
  • search_emails — Smart search with keywords, sender filter, date range. Returns FULL email body.
  • get_email_body — Read the complete body of a specific email by ID
  • draft_reply — Create a draft reply to an email thread
  • send_reply — Send a reply to an email thread after explicit user confirmation

📅 CALENDAR (Google Calendar):
  • create_calendar_event — Schedule meetings/events with title, time, description, attendees, location
  • list_calendar_events — View upcoming events on the calendar
  • delete_calendar_event — Remove a calendar event

🏢 LEAVE MANAGEMENT (BizzHub):
  • apply_leave — Apply for leave in the connected leave management system
  • list_my_leaves — View my submitted leave requests
  • list_pending_leave_requests — View pending leave approvals for the configured manager/admin
  • list_team_leaves — View team leave history for the configured manager/admin
  • list_all_leaves — View all leave requests for HR or super-admin
  • approve_leave_request — Approve a pending leave request after confirmation
  • reject_leave_request — Reject a leave request after confirmation
  • cancel_leave_request — Cancel one of my pending leave requests after confirmation

📋 TASKS:
  • add_task — Add a new item to the personal task list
  • list_tasks — View open or completed tasks
  • complete_task — Mark a task as done

═══════════════════════════════════════════
CRITICAL RULES — FOLLOW THESE STRICTLY:
═══════════════════════════════════════════

1. **NEVER ask the user for IDs.** If you need an email ID, thread ID, or event ID, search for it yourself
   using search_emails, read_emails, or list_calendar_events. The user should never have to provide technical identifiers.

2. **Be proactive with multi-step tasks.** Example: If the user says "schedule a meeting about the internet issue email
   tomorrow at 10am", you should:
   Step 1: Use search_emails with keywords like '{{internet OR network OR connectivity}}' to find the email
   Step 2: Read the email body to understand the context
   Step 3: Create a calendar event with relevant details from the email
   Step 4: If the user also wants a reply, draft it immediately. If they explicitly ask to send it, use send_reply.

3. **Search broadly for topics.** When looking for emails by topic:
   - NEVER use multi-word exact phrases in keywords unless you are 100% sure.
   - Always use Gmail OR syntax for concepts. Example: '{{network OR internet OR connectivity}}'
   - Do NOT search for 'internet issue' literally.
   - Also search with different time ranges if initial search returns nothing.
   - Read email bodies to analyze content, not just subjects.

4. **Use correct datetime format.** Calendar events need ISO format: '2026-06-23T10:00:00'
   Tomorrow's date would be calculated from the current date/time shown above.

5. **Be conversational and helpful.** Respond naturally, summarize findings clearly.
   Use markdown formatting (bold, lists, etc.) for readability.

6. **Remember context.** If the user mentions something from earlier in the conversation,
   refer back to it without asking them to repeat.

7. **Minimize unnecessary confirmation loops.**
   - Drafting a reply or creating a calendar event does not need extra permission when the user already asked for it.
   - Sending an email, deleting a calendar event, or completing a task should still require confirmation.

8. **For leave management, be operational.**
   - If the user asks to approve or reject leave, first fetch pending leave requests yourself.
   - Never ask the user for technical leave IDs if the leave can be identified from recent context or pending requests.
   - Apply for leave directly when the user gives dates and leave type.
   - Approvals, rejections, and cancellations should still require confirmation.
   - Note that you CAN reject or approve leave requests even if they were previously approved or rejected (the backend API supports changing their status at any time).
"""


def plan_node(state: AgentState) -> Dict[str, Any]:
    """Retrieves memories, builds system prompt context, and invokes Gemini to plan or decide next step."""
    user_id = state.get("user_id", "default_user")

    # 1. Retrieve relevant memories based on the last human message
    last_user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if msg.type == "human":
            last_user_msg = msg.content
            break

    memories = []
    if last_user_msg:
        memories = retrieve_memories(user_id, last_user_msg)

    # 2. Inject memories and current time into system prompt
    current_time_str = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p IST")
    memories_text = "\n".join(f"  • {m}" for m in memories) if memories else "  No specific preferences saved yet."

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        current_time=current_time_str,
        memories=memories_text
    )

    messages = [SystemMessage(content=system_prompt)] + list(state.get("messages", []))

    # 3. Call LLM with bound tools
    llm = get_llm()
    response = llm.invoke(messages)

    # Update plan in state if LLM provides new details in text
    new_plan = response.content if response.content else state.get("plan")

    write_trace("node_exit", {
        "node": "plan_node",
        "user_id": user_id,
        "decision": f"tool_calls:{[t['name'] for t in response.tool_calls]}" if response.tool_calls else "respond",
        "reasoning_summary": response.content[:300] if response.content else "Formulated tool calls",
        "iteration": state.get("iteration_count", 0) + 1
    })

    return {
        "messages": [response],
        "plan": new_plan,
        "retrieved_memories": memories,
        "requires_confirmation": False
    }

def act_node(state: AgentState) -> Dict[str, Any]:
    """Checks the LLM's selected tool. Prompts confirmation for irreversible tools or runs immediately."""
    messages = state.get("messages", [])
    if not messages:
        return {"requires_confirmation": False}

    last_message = messages[-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"requires_confirmation": False}

    # Standardize to process the first tool call
    tool_call = last_message.tool_calls[0]
    tool_name = tool_call["name"]
    tool_args = tool_call["args"]
    tool_call_id = tool_call["id"]

    # If the action is irreversible, save details and flag confirmation
    if tool_name in IRREVERSIBLE_TOOLS:
        pending_action = {
            "tool": tool_name,
            "args": tool_args,
            "id": tool_call_id
        }
        write_trace("node_exit", {
            "node": "act_node",
            "user_id": state.get("user_id"),
            "decision": f"flagged_for_confirmation:{tool_name}",
            "tool": tool_name,
            "args": tool_args,
            "iteration": state.get("iteration_count", 0)
        })
        return {
            "pending_action": pending_action,
            "requires_confirmation": True
        }

    # Execute immediately for reversible tools
    tool_map = get_tool_map()
    tool_instance = tool_map.get(tool_name)

    if not tool_instance:
        result = f"Error: Tool '{tool_name}' not found in registry."
    else:
        try:
            result = tool_instance.invoke(tool_args)
        except Exception as e:
            result = f"Error executing tool '{tool_name}': {str(e)}"

    tool_msg = ToolMessage(content=str(result), tool_call_id=tool_call_id, name=tool_name)

    write_trace("node_exit", {
        "node": "act_node",
        "user_id": state.get("user_id"),
        "decision": f"execute_tool:{tool_name}",
        "tool": tool_name,
        "args": tool_args,
        "result_summary": str(result)[:300],
        "iteration": state.get("iteration_count", 0)
    })

    return {
        "messages": [tool_msg],
        "requires_confirmation": False
    }

def confirm_node(state: AgentState) -> Dict[str, Any]:
    """Executes or skips the pending irreversible tool call based on human approval response."""
    pending_action = state.get("pending_action")
    if not pending_action:
        return {"requires_confirmation": False}

    tool_name = pending_action["tool"]
    tool_args = pending_action["args"]
    tool_call_id = pending_action["id"]
    approved = state.get("human_approved")

    if approved is True:
        # Run the tool since the human approved it
        tool_map = get_tool_map()
        tool_instance = tool_map.get(tool_name)
        if not tool_instance:
            result = f"Error: Tool '{tool_name}' not found."
        else:
            try:
                result = tool_instance.invoke(tool_args)
            except Exception as e:
                result = f"Error executing tool '{tool_name}': {str(e)}"

        tool_msg = ToolMessage(content=str(result), tool_call_id=tool_call_id, name=tool_name)
        write_trace("node_exit", {
            "node": "confirm_node",
            "user_id": state.get("user_id"),
            "decision": f"approved_and_executed:{tool_name}",
            "tool": tool_name,
            "args": tool_args,
            "result_summary": str(result)[:300]
        })
    else:
        # Rejected by human
        result = "Error: Action cancelled/rejected by human confirmation."
        tool_msg = ToolMessage(content=result, tool_call_id=tool_call_id, name=tool_name)
        write_trace("node_exit", {
            "node": "confirm_node",
            "user_id": state.get("user_id"),
            "decision": f"rejected_by_human:{tool_name}",
            "tool": tool_name,
            "args": tool_args,
            "result_summary": result
        })

    return {
        "messages": [tool_msg],
        "pending_action": None,
        "requires_confirmation": False,
        "human_approved": None
    }

def observe_node(state: AgentState) -> Dict[str, Any]:
    """Simple helper to increment the safety iteration counter."""
    iteration = state.get("iteration_count", 0) + 1
    return {"iteration_count": iteration}

def respond_node(state: AgentState) -> Dict[str, Any]:
    """Generates the final natural language response, and monitors/stores explicit user preferences."""
    user_id = state.get("user_id", "default_user")
    messages = state.get("messages", [])

    # 1. Look for explicit user preference declarations in the last human message
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.type == "human":
            last_user_msg = msg.content
            break

    if last_user_msg:
        keywords = ["always", "never", "remember", "prefer", "remind", "keep replies", "cc manager"]
        if any(kw in last_user_msg.lower() for kw in keywords):
            try:
                # Use a fast LLM extraction run
                extract_llm = ChatGoogleGenerativeAI(
                    model="gemini-2.5-flash",
                    google_api_key=config.GEMINI_API_KEY,
                    temperature=0.0
                )
                pref_prompt = (
                    f"Extract any long-term user preferences, instructions, or rules from this user message: '{last_user_msg}'. "
                    f"Respond ONLY with the preference itself (e.g. 'Keep email replies short'), or respond with 'NONE' if no long-term preference is found."
                )
                res = extract_llm.invoke(pref_prompt)
                pref = res.content.strip()
                if pref and pref != "NONE" and len(pref) > 5:
                    store_memory(user_id, pref)
                    write_trace("memory_stored", {
                        "user_id": user_id,
                        "preference": pref
                    })
            except Exception as e:
                print(f"[Warning] Failed to extract/store memory: {str(e)}", file=sys.stderr)

    # 2. Check if we already have the final response (AIMessage from plan_node) or need to generate one
    last_message = messages[-1] if messages else None
    if last_message and last_message.type == "ai" and not (hasattr(last_message, "tool_calls") and last_message.tool_calls):
        # We already have the final response from plan_node
        response_message = last_message
        needs_append = False
    else:
        # Generate a final response summarizing the tool output / cancellation
        system_prompt = (
            "You are Bhuvan's personal AI assistant. "
            "Format your final response in clear, friendly markdown. "
            "Summarize your actions and results concisely. "
            "Use bullet points, bold text, and emojis where appropriate to make the response easy to scan. "
            "Be conversational and warm, not robotic."
        )
        combined_messages = [SystemMessage(content=system_prompt)] + list(messages)

        # Use raw LLM without tools bound so it responds instead of making tool calls
        raw_llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=config.GEMINI_API_KEY,
            temperature=0.0
        )
        response_message = raw_llm.invoke(combined_messages)
        needs_append = True

    write_trace("node_exit", {
        "node": "respond_node",
        "user_id": user_id,
        "decision": "respond_to_user",
        "reasoning_summary": response_message.content[:300]
    })

    return {
        "messages": [response_message] if needs_append else []
    }
