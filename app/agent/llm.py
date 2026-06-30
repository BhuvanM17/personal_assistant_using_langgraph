import sys
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import config
from app.tools.tool_registry import ALL_TOOLS

def get_llm():
    """Initializes the Gemini LLM and binds the registration tools."""
    if not config.GEMINI_API_KEY or config.GEMINI_API_KEY == "your_gemini_api_key_here":
        print("ERROR: GEMINI_API_KEY is not configured in .env. Please update it.", file=sys.stderr)
        raise ValueError("GEMINI_API_KEY not configured. Update your .env file.")

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=config.GEMINI_API_KEY,
        temperature=0.0,
    )
    # Bind tools so LLM can call them
    return llm.bind_tools(ALL_TOOLS)
