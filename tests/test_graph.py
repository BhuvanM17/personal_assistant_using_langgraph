import unittest
import sys

sys.path.append("c:/Users/bizzh_4kk2t8y/Desktop/Bhuvan/personal-assisstant")
from app.agent.graph import app_graph

class TestAgentGraph(unittest.TestCase):
    def test_graph_nodes(self):
        """Validates that all essential nodes exist in the compiled state machine."""
        nodes = app_graph.nodes
        self.assertIn("plan_node", nodes)
        self.assertIn("act_node", nodes)
        self.assertIn("confirm_node", nodes)
        self.assertIn("observe_node", nodes)
        self.assertIn("respond_node", nodes)

if __name__ == "__main__":
    unittest.main()
