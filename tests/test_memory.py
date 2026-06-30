import unittest
import os
import sys
import shutil

sys.path.append("c:/Users/bizzh_4kk2t8y/Desktop/Bhuvan/personal-assisstant")
from app.config import config
# Override persistent directory to prevent production collision
config.CHROMA_PERSIST_DIR = "./data/test_chroma_db"

from app.memory.vector_memory import store_memory, retrieve_memories

class TestVectorMemory(unittest.TestCase):
    def tearDown(self):
        """Cleans up the test collection on disk."""
        if os.path.exists(config.CHROMA_PERSIST_DIR):
            try:
                shutil.rmtree(config.CHROMA_PERSIST_DIR)
            except Exception:
                pass

    def test_store_and_retrieve(self):
        """Verifies storing a preference and retrieving it using semantic search."""
        user_id = "test_user_456"
        store_memory(user_id, "Always keep my email replies short.")
        store_memory(user_id, "CC manager on client emails.")

        # Search query
        memories = retrieve_memories(user_id, "How should I respond to client emails?")
        self.assertTrue(len(memories) > 0)
        # Verify it finds the CC manager preference
        has_cc = any("cc manager" in m.lower() for m in memories)
        self.assertTrue(has_cc)

if __name__ == "__main__":
    unittest.main()
