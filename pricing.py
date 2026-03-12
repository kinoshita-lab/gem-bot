"""Usage cost calculation and model pricing data."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from i18n import I18nManager


class PricingMixin:
    """Mixin providing usage cost formatting for GeminiBot.

    Expects the host class to have:
        - self.i18n: I18nManager
    """

    # Pricing table: model keyword -> list of (threshold, input_price, output_price)
    # Source: https://ai.google.dev/gemini-api/docs/pricing / Vertex AI pricing (2025)
    # - threshold: prompt_token_count upper bound for this tier (None = no limit / catch-all)
    # - Tiers must be ordered from smallest threshold to largest (None last).
    # - Key is a substring matched against the model name; longest match wins.
    # Prices are in USD per 1M tokens (Standard Tier).
    MODEL_PRICING: dict[str, list[tuple[int | None, float, float]]] = {
        # --- Latest aliases ---
        # gemini-pro-latest = gemini-3.1-pro-preview: <=200K $2/$12, >200K $4/$18
        "gemini-pro-latest": [
            (200_000, 2.00, 12.00),
            (None,    4.00, 18.00),
        ],
        # gemini-flash-latest = gemini-3.1-flash-lite-preview: flat rate
        "gemini-flash-latest": [
            (None, 0.25, 1.50),
        ],
        # --- Gemini 3.1 ---
        # Gemini 3.1 Pro Preview: <=200K $2/$12, >200K $4/$18
        "gemini-3.1-pro-preview": [
            (200_000, 2.00, 12.00),
            (None,    4.00, 18.00),
        ],
        # Gemini 3.1 Flash Image Preview: flat rate
        "gemini-3.1-flash-image-preview": [
            (None, 0.50, 3.00),
        ],
        # Gemini 3.1 Flash-Lite Preview: flat rate
        "gemini-3.1-flash-lite-preview": [
            (None, 0.25, 1.50),
        ],
        # --- Gemini 3 ---
        # Gemini 3 Pro Preview: <=200K $2/$12, >200K $4/$18
        "gemini-3-pro-preview": [
            (200_000, 2.00, 12.00),
            (None,    4.00, 18.00),
        ],
        # Gemini 3 Flash Preview: flat rate
        "gemini-3-flash-preview": [
            (None, 0.50, 3.00),
        ],
        # --- Gemini 2.5 ---
        # Gemini 2.5 Pro: <=200K $1.25/$10, >200K $2.5/$15
        "gemini-2.5-pro": [
            (200_000, 1.25, 10.00),
            (None,    2.50, 15.00),
        ],
        # Gemini 2.5 Flash-Lite: flat rate
        "gemini-2.5-flash-lite": [
            (None, 0.10, 0.40),
        ],
        # Gemini 2.5 Flash: flat rate (must come after "gemini-2.5-flash-lite")
        "gemini-2.5-flash": [
            (None, 0.30, 2.50),
        ],
        # --- Gemini 2.0 ---
        # Gemini 2.0 Flash-Lite: flat rate
        "gemini-2.0-flash-lite": [
            (None, 0.075, 0.30),
        ],
        # Gemini 2.0 Flash: flat rate (must come after "gemini-2.0-flash-lite")
        "gemini-2.0-flash": [
            (None, 0.15, 0.60),
        ],
        # --- Gemini 1.5 ---
        # Gemini 1.5 Flash-8B: <=128K $0.0375/$0.15, >128K $0.075/$0.30
        "gemini-1.5-flash-8b": [
            (128_000, 0.0375, 0.15),
            (None,    0.075,  0.30),
        ],
        # Gemini 1.5 Flash: <=128K $0.075/$0.30, >128K $0.15/$0.60
        "gemini-1.5-flash": [
            (128_000, 0.075, 0.30),
            (None,    0.15,  0.60),
        ],
        # Gemini 1.5 Pro: <=128K $1.25/$5, >128K $2.5/$10
        "gemini-1.5-pro": [
            (128_000, 1.25, 5.00),
            (None,    2.50, 10.00),
        ],
    }

    def _format_usage_cost(self, usage_metadata: Any, model: str) -> str:
        """Format usage metadata and estimated cost as a footer string.

        Args:
            usage_metadata: The usage_metadata object from a Gemini API response.
            model: Model name used for the request.

        Returns:
            Formatted usage/cost string to append to the response.
        """
        if usage_metadata is None:
            return ""

        i18n: I18nManager = self.i18n  # type: ignore[attr-defined]

        prompt_tokens: int = getattr(usage_metadata, "prompt_token_count", 0) or 0
        output_tokens: int = getattr(usage_metadata, "candidates_token_count", 0) or 0
        thoughts_tokens: int = getattr(usage_metadata, "thoughts_token_count", 0) or 0
        total_tokens: int = getattr(usage_metadata, "total_token_count", 0) or 0

        # Build token detail string
        token_parts = [f"in={prompt_tokens:,}", f"out={output_tokens:,}"]
        if thoughts_tokens:
            token_parts.append(f"thoughts={thoughts_tokens:,}")
        token_str = " / ".join(token_parts)

        # Find best matching pricing entry (longest key match)
        model_lower = model.lower()
        matched_key = ""
        matched_tiers: list[tuple[int | None, float, float]] | None = None
        for key, tiers in self.MODEL_PRICING.items():
            if key in model_lower and len(key) > len(matched_key):
                matched_key = key
                matched_tiers = tiers

        if matched_tiers is not None:
            # Select the appropriate tier based on prompt_token_count
            input_price, output_price = matched_tiers[-1][1], matched_tiers[-1][2]
            for threshold, in_price, out_price in matched_tiers:
                if threshold is None or prompt_tokens <= threshold:
                    input_price, output_price = in_price, out_price
                    break
            cost = (prompt_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price
            cost_str = i18n.t("usage_cost_footer", tokens=token_str, total=f"{total_tokens:,}", cost=cost)
        else:
            cost_str = i18n.t("usage_cost_unknown_model", tokens=token_str, total=f"{total_tokens:,}")

        return f"\n\n---\n{cost_str}"
