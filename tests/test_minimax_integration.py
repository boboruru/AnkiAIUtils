"""Integration tests for MiniMax provider in AnkiAIUtils.

These tests require a valid MINIMAX_API_KEY environment variable.
They verify end-to-end functionality against the live MiniMax API.

Run with:
    MINIMAX_API_KEY=your-key python -m pytest tests/test_minimax_integration.py -v
"""
import os
import sys
import unittest

# Add repo root to path so utils can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")


@unittest.skipUnless(MINIMAX_API_KEY, "MINIMAX_API_KEY not set")
class TestMiniMaxIntegration(unittest.TestCase):
    """Integration tests that call the live MiniMax API."""

    def test_chat_minimax_m27(self):
        """Test a basic chat completion with MiniMax-M2.7."""
        from utils.llm import MINIMAX_API_BASE
        from litellm import completion

        response = completion(
            model="openai/MiniMax-M2.7",
            messages=[{"role": "user", "content": "Say hello in one word."}],
            temperature=0.5,
            api_base=MINIMAX_API_BASE,
            api_key=MINIMAX_API_KEY,
            stream=False,
        )
        result = response.json()
        self.assertIn("choices", result)
        self.assertGreater(len(result["choices"]), 0)
        content = result["choices"][0]["message"]["content"]
        self.assertIsInstance(content, str)
        self.assertGreater(len(content), 0)

    def test_chat_minimax_m27_highspeed(self):
        """Test a basic chat completion with MiniMax-M2.7-highspeed."""
        from utils.llm import MINIMAX_API_BASE
        from litellm import completion

        response = completion(
            model="openai/MiniMax-M2.7-highspeed",
            messages=[{"role": "user", "content": "What is 2+2? Reply with just the number."}],
            temperature=0.5,
            api_base=MINIMAX_API_BASE,
            api_key=MINIMAX_API_KEY,
            stream=False,
        )
        result = response.json()
        self.assertIn("choices", result)
        content = result["choices"][0]["message"]["content"]
        self.assertIn("4", content)

    def test_chat_via_minimax_prefix(self):
        """Test calling via the minimax/ prefix through the chat() wrapper."""
        # Need to clear cache to avoid stale results
        from utils.llm import chat, MINIMAX_API_BASE

        os.environ["MINIMAX_API_KEY"] = MINIMAX_API_KEY

        # Use unique messages to avoid cache hits
        import time
        unique_msg = f"Say 'pong' and nothing else. Timestamp: {time.time()}"

        result = chat(
            model="minimax/MiniMax-M2.7",
            messages=[{"role": "user", "content": unique_msg}],
            temperature=0.5,
        )
        self.assertIn("choices", result)
        content = result["choices"][0]["message"]["content"]
        self.assertIsInstance(content, str)
        self.assertGreater(len(content), 0)


if __name__ == "__main__":
    unittest.main()
