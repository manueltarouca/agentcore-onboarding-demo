"""Rough cost per call, in USD per million tokens. An estimate for teaching, not a bill."""
PRICES_PER_MILLION = {
    "sonnet": (3.00, 15.00),
    "haiku": (1.00, 5.00),
}


def estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    family = next((f for f in PRICES_PER_MILLION if f in model_id), "sonnet")
    input_price, output_price = PRICES_PER_MILLION[family]
    return round((input_tokens * input_price + output_tokens * output_price) / 1_000_000, 6)
