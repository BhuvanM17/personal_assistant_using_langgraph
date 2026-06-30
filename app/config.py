import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    BIZZHUB_API_BASE_URL: str = os.getenv("BIZZHUB_API_BASE_URL", "http://localhost:3000/api")
    BIZZHUB_USER_EMAIL: str = os.getenv("BIZZHUB_USER_EMAIL", "")
    BIZZHUB_PASSWORD: str = os.getenv("BIZZHUB_PASSWORD", "")
    GOOGLE_OAUTH_CREDENTIALS_PATH: str = os.getenv(
        "GOOGLE_OAUTH_CREDENTIALS_PATH", str(BASE_DIR / "credentials.json")
    )
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/tasks.db")
    CHECKPOINTS_DATABASE_URL: str = os.getenv(
        "CHECKPOINTS_DATABASE_URL", "sqlite:///./data/checkpoints.db"
    )
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
    MAX_AGENT_ITERATIONS: int = int(os.getenv("MAX_AGENT_ITERATIONS", "6"))

    # Tracing
    LANGCHAIN_TRACING_V2: str = os.getenv("LANGCHAIN_TRACING_V2", "false")
    LANGCHAIN_API_KEY: str = os.getenv("LANGCHAIN_API_KEY", "")
    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "dailyops-agent")

    @classmethod
    def validate(cls):
        """Simple check to alert on missing critical variables."""
        missing = []
        if not cls.GEMINI_API_KEY or cls.GEMINI_API_KEY == "your_gemini_api_key_here":
            missing.append("GEMINI_API_KEY")
        return missing

config = Config()
