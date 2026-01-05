import unittest
import uuid

from cuga.agents.core import run_agent
from cuga.memory.in_memory_store import InMemoryMemoryStore
from cuga.sandbox.registry_based_runner import RegistryBasedRunner


class TestStatefulAgentScenario(unittest.TestCase):
    """
    An end-to-end scenario test for a multi-turn, stateful conversation.

    This test validates that all the core components of the agent system
    (memory, sandboxing, and the core agent logic) work together correctly.
    """

    def test_multi_turn_stateful_conversation_with_sandboxing(self):
        """
        Simulates a multi-turn conversation that involves both stateful memory
        and the execution of a sandboxed tool.
        """
        # 1. Initialize the components for this test run
        session_id = str(uuid.uuid4())
        memory_store = InMemoryMemoryStore()
        tool_runner = RegistryBasedRunner()

        print(f"--- Starting Stateful Agent Scenario Test (Session: {session_id}) ---")

        # --- Turn 1: User provides a piece of information ---
        print("\n--- Turn 1: Remembering user's name ---")
        turn1_input = "My name is Alice."
        result1 = run_agent(
            input_text=turn1_input,
            session_id=session_id,
            memory_store=memory_store,
            tool_runner=tool_runner,
        )
        # For this turn, the agent should just echo the input, as it's not a command.
        self.assertIn("Echo", result1.output)

        # Verify the state was saved
        state1 = memory_store.load_session_state(session_id)
        self.assertIsNotNone(state1)
        self.assertEqual(len(state1["history"]), 1)
        self.assertEqual(state1["history"][0]["input"], turn1_input)

        # --- Turn 2: User asks the agent to execute a sandboxed command ---
        print("\n--- Turn 2: Executing a sandboxed command ---")
        turn2_input = "print(10 + 20)"
        result2 = run_agent(
            input_text=turn2_input,
            session_id=session_id,
            memory_store=memory_store,
            tool_runner=tool_runner,
        )
        self.assertIn("Execution result: 30", result2.output)
        self.assertIsNone(result2.error)

        # Verify the state has been updated
        state2 = memory_store.load_session_state(session_id)
        self.assertEqual(len(state2["history"]), 2)

        # --- Turn 3: User asks a question that requires the agent to recall information ---
        # This is a conceptual test. The current hardcoded agent logic does not
        # actually "remember" in a smart way, but we can verify that the history
        # is being maintained correctly.
        print("\n--- Turn 3: Recalling information from Turn 1 ---")
        turn3_input = "What is my name?"
        result3 = run_agent(
            input_text=turn3_input,
            session_id=session_id,
            memory_store=memory_store,
            tool_runner=tool_runner,
        )
        self.assertIn("Echo", result3.output)

        # The most important assertion: Verify the full history is in the final state.
        final_state = memory_store.load_session_state(session_id)
        self.assertEqual(len(final_state["history"]), 3)
        self.assertEqual(final_state["history"][0]["input"], "My name is Alice.")
        self.assertEqual(final_state["history"][1]["input"], "print(10 + 20)")
        self.assertEqual(final_state["history"][2]["input"], "What is my name?")

        print("\n--- Stateful Agent Scenario Test finished successfully! ---")


if __name__ == '__main__':
    unittest.main()
