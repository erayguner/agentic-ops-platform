"""aop_common.models — ADK 2.0 model factory with fallback list.

The model id is NEVER hard-coded. It is read from AopSettings.model_id.
The factory tries the primary model first; on quota or availability errors
it cycles through model_fallback_list.

ADK 2.0 API — confirm LlmModel / GenerativeModel constructor and
fallback API against adk.dev/2.0/ release notes.
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
        """Return the ADK 2.0 model instance, constructing it on first call.

        Returns:
            An ADK 2.0 LlmModel instance configured with the primary model id.

        Raises:
            NotImplementedError: Skeleton — real ADK model construction not wired.

        ADK 2.0 API — confirm google.adk.models.LlmModel (or equivalent) constructor
        signature and fallback registration pattern against adk.dev/2.0/ release notes.
        """
        if self._model is not None:
            return self._model

        logger.info("ModelFactory.get_model: primary=%s", self._model_id)

        # SKELETON: In production, construct via ADK 2.0 model API, e.g.:
        #
        #   from google.adk.models import LlmModel  # ADK 2.0 API — confirm name
        #   self._model = LlmModel(
        #       model=self._model_id,
        #       generation_config={
        #           "temperature": self._temperature,
        #           "max_output_tokens": self._max_output_tokens,
        #       },
        #       fallback_models=self._fallback_list,
        #   )
        #   return self._model

        raise NotImplementedError(
            "ModelFactory.get_model is a skeleton. "
            "Wire the ADK 2.0 LlmModel constructor before connecting to the model API."
        )

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
