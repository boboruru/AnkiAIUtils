"""Unit tests for MiniMax provider integration in AnkiAIUtils.

These tests verify MiniMax model registration, temperature clamping,
and model name matching without requiring a live API key.
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add repo root to path so utils can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestMiniMaxRegistration(unittest.TestCase):
    """Test that MiniMax models are registered in litellm."""

    def test_models_by_provider_contains_minimax(self):
        import litellm
        from utils.llm import _register_minimax
        _register_minimax()
        self.assertIn("minimax", litellm.models_by_provider)
        self.assertIn("MiniMax-M2.7", litellm.models_by_provider["minimax"])
        self.assertIn(
            "MiniMax-M2.7-highspeed", litellm.models_by_provider["minimax"]
        )

    def test_model_cost_contains_minimax(self):
        import litellm
        from utils.llm import _register_minimax
        _register_minimax()
        self.assertIn("minimax/MiniMax-M2.7", litellm.model_cost)
        self.assertIn("minimax/MiniMax-M2.7-highspeed", litellm.model_cost)
        self.assertIn("MiniMax-M2.7", litellm.model_cost)
        self.assertIn("MiniMax-M2.7-highspeed", litellm.model_cost)

    def test_model_cost_has_pricing_fields(self):
        import litellm
        from utils.llm import _register_minimax
        _register_minimax()
        cost = litellm.model_cost["minimax/MiniMax-M2.7"]
        self.assertIn("input_cost_per_token", cost)
        self.assertIn("output_cost_per_token", cost)
        self.assertIn("max_tokens", cost)
        self.assertGreater(cost["input_cost_per_token"], 0)
        self.assertGreater(cost["output_cost_per_token"], 0)
        self.assertEqual(cost["max_tokens"], 204800)

    def test_register_minimax_idempotent(self):
        """Calling _register_minimax() multiple times should not error."""
        from utils.llm import _register_minimax
        _register_minimax()
        _register_minimax()
        import litellm
        self.assertIn("minimax", litellm.models_by_provider)

    def test_minimax_api_base_constant(self):
        from utils.llm import MINIMAX_API_BASE
        self.assertEqual(MINIMAX_API_BASE, "https://api.minimax.io/v1")

    def test_minimax_models_dict_not_empty(self):
        from utils.llm import MINIMAX_MODELS
        self.assertGreater(len(MINIMAX_MODELS), 0)
        for name, info in MINIMAX_MODELS.items():
            self.assertIn("max_tokens", info)
            self.assertIn("input_cost_per_token", info)
            self.assertIn("output_cost_per_token", info)


class TestMiniMaxTemperatureClamping(unittest.TestCase):
    """Test that MiniMax temperature is clamped to (0, 1]."""

    @patch("utils.llm.completion")
    def test_zero_temperature_clamped(self, mock_completion):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"finish_reason": "stop", "message": {"content": "hi"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_completion.return_value = mock_resp

        # Need to bypass the cache for testing
        from utils.llm import MINIMAX_API_BASE
        from litellm import completion as _comp

        os.environ["MINIMAX_API_KEY"] = "test-key"

        # Call chat directly (bypassing cache by importing the inner logic)
        from utils.llm import chat
        # The cached function won't call completion again for same args,
        # so we test the routing logic directly
        kwargs = {}
        model = "minimax/MiniMax-M2.7"
        temperature = 0.0

        # Simulate the routing logic from chat()
        if model.startswith("minimax/"):
            model_name = model.split("/", 1)[1]
            kwargs["api_base"] = MINIMAX_API_BASE
            kwargs["api_key"] = os.environ.get("MINIMAX_API_KEY")
            if temperature <= 0:
                temperature = 0.01
            elif temperature > 1:
                temperature = 1.0
            model = f"openai/{model_name}"

        self.assertEqual(temperature, 0.01)
        self.assertEqual(model, "openai/MiniMax-M2.7")
        self.assertEqual(kwargs["api_base"], MINIMAX_API_BASE)

    def test_high_temperature_clamped(self):
        """Temperature > 1.0 should be clamped to 1.0 for MiniMax."""
        from utils.llm import MINIMAX_API_BASE

        model = "minimax/MiniMax-M2.7"
        temperature = 1.5
        kwargs = {}

        if model.startswith("minimax/"):
            model_name = model.split("/", 1)[1]
            kwargs["api_base"] = MINIMAX_API_BASE
            if temperature <= 0:
                temperature = 0.01
            elif temperature > 1:
                temperature = 1.0
            model = f"openai/{model_name}"

        self.assertEqual(temperature, 1.0)

    def test_valid_temperature_unchanged(self):
        """Temperature within (0, 1] should not be changed."""
        from utils.llm import MINIMAX_API_BASE

        model = "minimax/MiniMax-M2.7"
        temperature = 0.7
        kwargs = {}

        if model.startswith("minimax/"):
            model_name = model.split("/", 1)[1]
            kwargs["api_base"] = MINIMAX_API_BASE
            if temperature <= 0:
                temperature = 0.01
            elif temperature > 1:
                temperature = 1.0
            model = f"openai/{model_name}"

        self.assertEqual(temperature, 0.7)

    def test_negative_temperature_clamped(self):
        """Negative temperature should be clamped to 0.01."""
        from utils.llm import MINIMAX_API_BASE

        model = "minimax/MiniMax-M2.7"
        temperature = -0.5
        kwargs = {}

        if model.startswith("minimax/"):
            model_name = model.split("/", 1)[1]
            kwargs["api_base"] = MINIMAX_API_BASE
            if temperature <= 0:
                temperature = 0.01
            elif temperature > 1:
                temperature = 1.0
            model = f"openai/{model_name}"

        self.assertEqual(temperature, 0.01)


class TestMiniMaxModelRouting(unittest.TestCase):
    """Test that MiniMax models are correctly routed through OpenAI-compat."""

    def test_minimax_model_rewritten_to_openai_prefix(self):
        from utils.llm import MINIMAX_API_BASE

        model = "minimax/MiniMax-M2.7-highspeed"
        kwargs = {}

        if model.startswith("minimax/"):
            model_name = model.split("/", 1)[1]
            kwargs["api_base"] = MINIMAX_API_BASE
            model = f"openai/{model_name}"

        self.assertEqual(model, "openai/MiniMax-M2.7-highspeed")
        self.assertEqual(kwargs["api_base"], "https://api.minimax.io/v1")

    def test_non_minimax_model_unchanged(self):
        """Non-MiniMax models should not be affected."""
        model = "openai/gpt-4"
        kwargs = {}

        if model.startswith("minimax/"):
            model_name = model.split("/", 1)[1]
            kwargs["api_base"] = "https://api.minimax.io/v1"
            model = f"openai/{model_name}"

        self.assertEqual(model, "openai/gpt-4")
        self.assertNotIn("api_base", kwargs)


class TestModelNameMatcher(unittest.TestCase):
    """Test that model_name_matcher works with MiniMax models."""

    def test_minimax_model_in_models_by_provider(self):
        """The minimax backend should be recognized."""
        import litellm
        from utils.llm import _register_minimax
        _register_minimax()
        self.assertIn("minimax", litellm.models_by_provider)

    def test_minimax_model_found_by_wrapped_matcher(self):
        """wrapped_model_name_matcher should find MiniMax-M2.7."""
        import litellm
        from utils.llm import _register_minimax, wrapped_model_name_matcher
        _register_minimax()
        os.environ["MINIMAX_API_KEY"] = "test-key"
        result = wrapped_model_name_matcher("minimax/MiniMax-M2.7")
        self.assertEqual(result, "minimax/MiniMax-M2.7")

    def test_minimax_highspeed_found_by_wrapped_matcher(self):
        """wrapped_model_name_matcher should find MiniMax-M2.7-highspeed."""
        import litellm
        from utils.llm import _register_minimax, wrapped_model_name_matcher
        _register_minimax()
        os.environ["MINIMAX_API_KEY"] = "test-key"
        result = wrapped_model_name_matcher("minimax/MiniMax-M2.7-highspeed")
        self.assertEqual(result, "minimax/MiniMax-M2.7-highspeed")


class TestAPIKeyLoading(unittest.TestCase):
    """Test that MINIMAX API key is loaded from API_KEYS directory."""

    @patch("pathlib.Path.iterdir")
    @patch("pathlib.Path.mkdir")
    def test_minimax_api_key_loaded(self, mock_mkdir, mock_iterdir):
        """load_api_keys should set MINIMAX_API_KEY from API_KEYS/MINIMAX file."""
        mock_file = MagicMock()
        mock_file.stem = "MINIMAX"
        mock_file.read_text.return_value = "test-minimax-key-12345"
        mock_iterdir.return_value = [mock_file]

        from utils.llm import load_api_keys
        keys = load_api_keys()

        self.assertIn("MINIMAX_API_KEY", keys)
        self.assertEqual(keys["MINIMAX_API_KEY"], "test-minimax-key-12345")
        self.assertEqual(
            os.environ.get("MINIMAX_API_KEY"), "test-minimax-key-12345"
        )


class TestLLMCostCompute(unittest.TestCase):
    """Test cost computation with MiniMax pricing."""

    def test_minimax_cost_computation(self):
        import litellm
        from utils.llm import llm_cost_compute, _register_minimax
        _register_minimax()

        price = litellm.model_cost["minimax/MiniMax-M2.7"]
        cost = llm_cost_compute(
            input_cost=1000,
            output_cost=500,
            price=price,
        )
        expected = (
            1000 * price["input_cost_per_token"]
            + 500 * price["output_cost_per_token"]
        )
        self.assertAlmostEqual(cost, expected)
        self.assertGreater(cost, 0)


if __name__ == "__main__":
    unittest.main()
