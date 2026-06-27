"""aop_common.models — ADK model factory.

The model id is NEVER hard-coded; it is read from AopSettings.model_id. The
factory constructs the primary model on first use. ``model_fallback_list`` is the
ordered runtime fallback policy (applied on quota/availability errors at
invocation time), not a construction-time concern.

Verified against google-adk 2.3.0: the model class is ``Gemini`` in
``google.adk.models.google_llm`` (ADK 2.x has no ``LlmModel``, which the original
skeleton guessed).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ModelFactory:
    """Creates and caches the configured ADK 2.0 model instance.

    Args:
        model_id: Primary model id (e.g., 'gemini-3-pro'). Comes from config.
        fallback_list: Ordered list of fallback model ids tried on error.
        temperature: Sampling temperature (0.0 = deterministic).
        max_output_tokens: Hard cap on output token count.
    """

    def __init__(
        self,
        model_id: str,
        fallback_list: list[str],
        temperature: float = 0.0,
        max_output_tokens: int = 8192,
    ) -> None:
        self._model_id = model_id
        self._fallback_list = fallback_list
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._model: Any = None

    def get_model(self) -> Any:
        """Return the ADK model instance, constructing it on first call.

        Returns:
            A ``google.adk.models.google_llm.Gemini`` bound to the primary model
            id. Generation parameters (temperature, max_output_tokens) are applied
            by the agent through its ``generate_content_config``; the fallback list
            is a runtime policy (``model_fallback_list``), not a construction-time
            concern.

        Verified against google-adk 2.3.0: ``Gemini(model=...)`` constructs offline
        (no credentials are used until the model is invoked).
        """
        if self._model is not None:
            return self._model

        from google.adk.models.google_llm import Gemini

        logger.info("ModelFactory.get_model: primary=%s", self._model_id)
        self._model = Gemini(model=self._model_id)
        return self._model

    @classmethod
    def from_settings(cls, settings: Any) -> ModelFactory:
        """Convenience constructor from an AopSettings instance.

        Args:
            settings: An AopSettings instance (aop_common.config.AopSettings).

        Returns:
            A configured ModelFactory.
        """
        return cls(
            model_id=settings.model_id,
            fallback_list=settings.model_fallback_list,
            temperature=settings.model_temperature,
            max_output_tokens=settings.model_max_output_tokens,
        )
