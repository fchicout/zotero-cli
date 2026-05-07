import logging
from typing import Any, Optional

from zotero_cli.core.interfaces import LLMProvider

logger = logging.getLogger(__name__)


class MockLLMProvider(LLMProvider):
    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        return f"[MOCK SUMMARY] This is a synthesized answer to: {prompt[:50]}..."


class OpenAILLMProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
        try:
            import openai

            self.client = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            self.client = None

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        if not self.client:
            raise ImportError("openai package not installed. Run 'pip install openai'")

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content or ""


class GeminiLLMProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp"):
        self.api_key = api_key
        self.model_name = model
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
            )
        except ImportError:
            self.model = None

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        if not self.model:
            raise ImportError(
                "google-generativeai package not installed. Run 'pip install google-generativeai'"
            )

        full_prompt = prompt
        if system_instruction:
            full_prompt = f"{system_instruction}\n\nUser Request: {prompt}"

        response = self.model.generate_content(full_prompt)
        return str(response.text)


class LocalTransformersLLMProvider(LLMProvider):
    """
    Local generative LLM using the transformers library.
    Best for small, instruct-tuned models (e.g., Qwen2.5-1.5B, Gemma-2b).
    """

    def __init__(self, model_name: str = "Qwen/Qwen2.5-1.5B-Instruct"):
        self.model_name = model_name
        self._model: Any = None
        self._tokenizer: Any = None

    def _init_model(self):
        if self._model is None:
            from transformers import AutoModelForCausalLM, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_name, torch_dtype="auto", device_map="auto", trust_remote_code=True
            )

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        self._init_model()
        assert self._tokenizer is not None
        assert self._model is not None

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        model_inputs = self._tokenizer([text], return_tensors="pt").to(self._model.device)

        generated_ids = self._model.generate(
            **model_inputs,
            max_new_tokens=512,
            do_sample=True,
            temperature=0.1,  # Low temperature for SLR rigor (less "creativity")
        )

        generated_ids = [
            output_ids[len(input_ids) :]
            for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]

        return str(self._tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0])
