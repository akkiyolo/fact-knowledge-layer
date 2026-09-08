"""
LLM Service abstraction.
Provides a generic interface with an Ollama implementation.
The rest of the pipeline depends on the interface, not on Ollama directly.
"""

import json
import re
import logging
from abc import ABC, abstractmethod
from typing import Optional

import httpx
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMService(ABC):
    """Abstract LLM service interface."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a text response from the LLM."""
        ...

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict:
        """Generate and parse a JSON response from the LLM."""
        raw = self.generate(prompt, system_prompt, temperature, max_tokens)
        return self._parse_json(raw)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """
        Parse JSON from LLM output, handling common formatting issues.
        Extracts JSON from markdown code blocks if present.
        """
        # Strip thinking tags (qwen3 outputs these)
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = text.strip()

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try finding JSON object/array
        for pattern in [r'\{.*\}', r'\[.*\]']:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    continue

        logger.warning("Failed to parse JSON from LLM output: %s...", text[:200])
        return {}


class OllamaLLMService(LLMService):
    """Ollama-based LLM service implementation."""

    def __init__(self):
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self._verify_connection()

    def _verify_connection(self):
        """Verify Ollama is reachable. Raise clear error if not."""
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            # Check if our model is available (with or without tag)
            found = any(
                self.model in name or name.startswith(self.model.split(":")[0])
                for name in model_names
            )
            if not found:
                logger.warning(
                    "Model '%s' not found in Ollama. Available: %s. "
                    "Pull it with: ollama pull %s",
                    self.model,
                    model_names,
                    self.model,
                )
            else:
                logger.info("Ollama connected: model '%s' available", self.model)
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Ensure Ollama is running: 'ollama serve'"
            )
        except Exception as e:
            raise RuntimeError(
                f"Ollama health check failed: {type(e).__name__}: {e}"
            )

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Call Ollama generate API."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            resp = httpx.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=300,  # LLM calls can be slow
            )
            resp.raise_for_status()
            result = resp.json()
            return result.get("response", "")
        except httpx.ConnectError:
            raise RuntimeError(
                f"Lost connection to Ollama at {self.base_url}. "
                f"Ensure Ollama is still running."
            )
        except httpx.TimeoutException:
            raise RuntimeError(
                "Ollama request timed out. The model may be too large "
                "for available resources, or the prompt is too long."
            )
        except Exception as e:
            raise RuntimeError(f"Ollama generate failed: {type(e).__name__}: {e}")


class GoogleLLMService(LLMService):
    """Google Gemini based LLM service implementation."""

    def __init__(self):
        settings = get_settings()
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is not set in the environment.")
        
        import google.generativeai as genai
        genai.configure(api_key=settings.google_api_key)
        
        # FORCE gemini-3.5-flash to bypass the 20-request/day limit of 2.5-flash, and 1.5-flash which threw a 404
        self.model_name = "gemini-3.5-flash"
        
        # Verify basic initialization
        try:
            self.model = genai.GenerativeModel(self.model_name)
            logger.info("Google LLM Service initialized with forced model '%s'", self.model_name)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Google LLM: {type(e).__name__}: {e}")

    @retry(
        wait=wait_exponential(multiplier=2, min=10, max=60),
        stop=stop_after_attempt(10),
        reraise=True,
    )
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Call Google Gemini generate API with exponential backoff for rate limits."""
        try:
            import google.generativeai as genai
            
            model = genai.GenerativeModel(
                self.model_name,
                system_instruction=system_prompt if system_prompt else None,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            if "429" in str(e) or "Quota exceeded" in str(e) or "ResourceExhausted" in type(e).__name__:
                logger.warning("Google API rate limit hit. Retrying...")
                raise  # Let tenacity handle it
            raise RuntimeError(f"Google generate failed: {type(e).__name__}: {e}")


# ── Singleton ────────────────────────────────────────────────

_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get the configured LLM service instance."""
    global _llm_service
    if _llm_service is None:
        settings = get_settings()
        if settings.llm_provider == "ollama":
            _llm_service = OllamaLLMService()
        elif settings.llm_provider == "google":
            _llm_service = GoogleLLMService()
        else:
            raise ValueError(
                f"Unsupported LLM provider: {settings.llm_provider}. "
                f"Currently supported: 'ollama', 'google'"
            )
    return _llm_service
