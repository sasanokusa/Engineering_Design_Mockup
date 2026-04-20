from __future__ import annotations

from openai import OpenAI

from backend.adapters.llm.base import LLMResponse
from backend.config import Settings


class OpenAICompatibleLLMAdapter:
    provider_name = "openai_compatible"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_name = settings.llm_model
        self.client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)

    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMResponse:
        response = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
        )
        text = response.choices[0].message.content or ""
        return LLMResponse(text=text.strip(), provider=self.provider_name, model=self.model_name)

