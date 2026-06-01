from typing import Dict, Tuple, List, Union
import os
import litellm
from pathlib import Path
from textwrap import dedent
from litellm import completion
from joblib import Memory
from difflib import get_close_matches

import tiktoken

from .shared import shared

litellm.drop_params = True

# ---------------------------------------------------------------------------
# MiniMax provider registration
# ---------------------------------------------------------------------------
# MiniMax offers an OpenAI-compatible API at https://api.minimax.io/v1
# Register models so litellm's model_cost / models_by_provider can find them.

MINIMAX_API_BASE = "https://api.minimax.io/v1"

MINIMAX_MODELS = {
    "MiniMax-M3": {
        "max_tokens": 524288,
        "max_input_tokens": 524288,
        "max_output_tokens": 131072,
        "input_cost_per_token": 0.0000006,
        "output_cost_per_token": 0.0000024,
        "litellm_provider": "openai",
    },
    "MiniMax-M2.7": {
        "max_tokens": 204800,
        "max_input_tokens": 204800,
        "max_output_tokens": 16384,
        "input_cost_per_token": 0.000001,
        "output_cost_per_token": 0.000003,
        "litellm_provider": "openai",
    },
    "MiniMax-M2.7-highspeed": {
        "max_tokens": 204800,
        "max_input_tokens": 204800,
        "max_output_tokens": 16384,
        "input_cost_per_token": 0.0000005,
        "output_cost_per_token": 0.0000015,
        "litellm_provider": "openai",
    },
}


def _register_minimax() -> None:
    """Register MiniMax models with litellm so they appear in
    ``litellm.models_by_provider`` and ``litellm.model_cost``.
    """
    litellm.models_by_provider["minimax"] = list(MINIMAX_MODELS.keys())
    for model_name, cost_info in MINIMAX_MODELS.items():
        litellm.model_cost[f"minimax/{model_name}"] = cost_info
        litellm.model_cost[model_name] = cost_info


_register_minimax()

def load_api_keys() -> Dict:
    """Load API keys from files in the API_KEYS directory.

    Creates API_KEYS directory if it doesn't exist.
    Each file in API_KEYS/ should contain a single API key.
    The filename (without extension) becomes part of the environment variable name.

    Returns
    -------
    Dict
        Dictionary mapping environment variable names to API key values
    """
    Path("API_KEYS").mkdir(exist_ok=True)
    if not list(Path("API_KEYS").iterdir()):
        shared.red("## No API_KEYS found in API_KEYS")
    api_keys = {}
    for apifile in Path("API_KEYS").iterdir():
        keyname = f"{apifile.stem.upper()}_API_KEY"
        key = apifile.read_text().strip()
        os.environ[keyname] = key
        api_keys[keyname] = key
    return api_keys


llm_price = {}
for k, v in litellm.model_cost.items():
    llm_price[k] = v

embedding_models = [
        "openai/text-embedding-3-large",
        "openai/text-embedding-3-small",
        "mistral/mistral-embed",
        ]

# steps : price
sd_price = {
    "15": 0.001,
    "30": 0.002,
    "50": 0.004,
    "100": 0.007,
    "150": "0.01",
}

def llm_cost_compute(
        input_cost: int,
        output_cost: int,
        price: Tuple[float]) -> float:
    """
    Parameters
    ----------
    input_cost: int
        number of tokens in input messages
    output_cost: int
        number of tokens in completion answer from the LLM
    price: [int, int]
        list with the cost in dollars per 1000 token for in the
        format [input, completion]

    Returns
    -------
    total cost in dollars as a float

    """
    return input_cost * price["input_cost_per_token"] + output_cost * price["output_cost_per_token"]


tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")


def tkn_len(message: Union[str, List[Union[str, Dict]], Dict]):
    if isinstance(message, str):
        return len(tokenizer.encode(dedent(message)))
    elif isinstance(message, dict):
        return len(tokenizer.encode(dedent(message["content"])))
    elif isinstance(message, list):
        return sum([tkn_len(subel) for subel in message])

llm_cache = Memory(".cache", verbose=0)

@llm_cache.cache
def chat(
    model: str,
    messages: List[Dict],
    temperature: float,
    check_reason: bool = True,
    **kwargs: Dict,
    ) -> Dict:
    """call to the LLM api. Cached."""
    # Handle MiniMax models: route through OpenAI-compatible API
    if model.startswith("minimax/"):
        model_name = model.split("/", 1)[1]
        kwargs["api_base"] = MINIMAX_API_BASE
        kwargs["api_key"] = os.environ.get("MINIMAX_API_KEY")
        # MiniMax requires temperature in (0.0, 1.0]
        if temperature <= 0:
            temperature = 0.01
        elif temperature > 1:
            temperature = 1.0
        model = f"openai/{model_name}"

    answer = completion(
        model=model,
        messages=messages,
        temperature=temperature,
        stream=False,
        **kwargs,
    ).json()
    if check_reason:
        assert all(a["finish_reason"] == "stop" for a in answer["choices"]), f"Found bad finish_reason: '{answer}'"
    return answer

def wrapped_model_name_matcher(model: str) -> str:
    "find the best match for a modelname (wrapped to make some check)"
    # find the currently set api keys to avoid matching models from
    # unset providers
    all_backends = list(litellm.models_by_provider.keys())
    backends = []
    for k, v in dict(os.environ).items():
        if k.endswith("_API_KEY"):
            backend = k.split("_API_KEY")[0].lower()
            if backend in all_backends:
                backends.append(backend)
    assert backends, "No API keys found in environnment"

    # filter by providers
    backend, modelname = model.split("/", 1)
    if backend not in all_backends:
        raise Exception(
            f"Model {model} with backend {backend}: backend not found in "
            "litellm.\nList of litellm providers/backend:\n"
            f"{all_backends}"
        )
    if backend not in backends:
        raise Exception(f"Trying to use backend {backend} but no API KEY was found for it in the environnment.")
    candidates = litellm.models_by_provider[backend]
    if modelname in candidates:
        return model
    subcandidates = [m for m in candidates if m.startswith(modelname)]
    if len(subcandidates) == 1:
        good = f"{backend}/{subcandidates[0]}"
        return good
    match = get_close_matches(modelname, candidates, n=1)
    if match:
        return match[0]
    else:
        print(f"Couldn't match the modelname {model} to any known model. "
            "Continuing but this will probably crash DocToolsLLM further "
            "down the code.")
        return model

def model_name_matcher(model: str) -> str:
    """find the best match for a modelname (wrapper that checks if the matched
    model has a known cost and print the matched name)"""
    assert "testing" not in model
    assert "/" in model, f"expected / in model '{model}'"

    out = wrapped_model_name_matcher(model)
    assert out in litellm.model_cost or out.split("/", 1)[1] in litellm.model_cost, f"Neither {out} nor {out.split('/', 1)[1]} found in litellm.model_cost"
    if out != model:
        print(f"Matched modelname '{model}' to '{out}'")
    return out
