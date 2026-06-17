# Claude API pricing in USD per million tokens (input, output).
# Sources: https://www.anthropic.com/pricing — update when prices change.
_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-8":          (15.0,  75.0),
    "claude-opus-4-7":          (15.0,  75.0),
    "claude-sonnet-4-6":        (3.0,   15.0),
    "claude-haiku-4-5":         (0.80,  4.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
}
_FALLBACK = (3.0, 15.0)  # sonnet-level if model is unknown


def query_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    inp, out = _PRICING.get(model, _FALLBACK)
    return (input_tokens * inp + output_tokens * out) / 1_000_000
