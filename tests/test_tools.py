import unittest
import os
import sys

# Override config to use in-memory SQLite database before loading session modules
sys.path.append("c:/Users/bizzh_4kk2t8y/Desktop/Bhuvan/personal-assisstant")
from app.config import config
config.DATABASE_URL = "sqlite:///:memory:"

from app.db.session import init_db
from app.tools.task_tools import add_task, list_tasks, complete_task

class TestTaskTools(unittest.TestCase):
    def setUp(self):
        """Initializes the database and clears the state by recreating tables."""
        from app.db.models import Base
        from app.db.session import engine
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def test_add_and_list_tasks(self):
        """Verifies adding a task and listing active tasks."""
        # 1. Add a task
        add_res = add_task.invoke({"description": "Test task", "source": "test_script"})
        self.assertNotIn("error", add_res)
        self.assertEqual(add_res["description"], "Test task")
        self.assertEqual(add_res["source"], "test_script")
        self.assertEqual(add_res["status"], "open")

        # 2. List tasks
        tasks = list_tasks.invoke({"status": "open"})
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["description"], "Test task")

    def test_complete_task(self):
        """Verifies marking a task as completed in SQLite."""
        # 1. Create a task
        task = add_task.invoke({"description": "Task to complete"})
        task_id = task["id"]

        # 2. Complete it
        comp_res = complete_task.invoke({"task_id": task_id})
        self.assertNotIn("error", comp_res)
        self.assertEqual(comp_res["status"], "completed")
        self.assertEqual(comp_res["task"]["status"], "completed")
        self.assertIsNotNone(comp_res["task"]["completed_at"])

if __name__ == "__main__":
    unittest.main()
