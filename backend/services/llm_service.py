import json
from typing import Dict, Any, Optional


class LLMProvider:
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError


class DemoProvider(LLMProvider):
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return json.dumps({"demo": True, "value": "sample"})


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model or "claude-sonnet-4-20250514"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=self.api_key)
            msg = client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system_prompt or "You generate realistic synthetic test data. Respond only with valid JSON.",
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text
        except Exception as e:
            return json.dumps({"error": str(e)})


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model or "gpt-4o"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt or "Generate realistic JSON test data."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2048,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            return json.dumps({"error": str(e)})


class AzureOpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, endpoint: str, deployment: str, api_version: str = "2024-02-15-preview"):
        self.api_key = api_key
        self.endpoint = endpoint
        self.deployment = deployment
        self.api_version = api_version

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        try:
            from openai import AzureOpenAI
            client = AzureOpenAI(api_key=self.api_key, azure_endpoint=self.endpoint, api_version=self.api_version)
            resp = client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system_prompt or "Generate realistic JSON test data."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2048,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            return json.dumps({"error": str(e)})


class GoogleProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-pro"):
        self.api_key = api_key
        self.model = model or "gemini-1.5-pro"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model, system_instruction=system_prompt or None)
            resp = model.generate_content(prompt)
            return resp.text or ""
        except Exception as e:
            return json.dumps({"error": str(e)})


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self.base_url = base_url.rstrip("/")
        self.model = model or "llama3"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        try:
            import httpx
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system_prompt or "Generate realistic JSON test data.",
                "stream": False,
            }
            r = httpx.post(f"{self.base_url}/api/generate", json=payload, timeout=120.0)
            r.raise_for_status()
            return r.json().get("response", "")
        except Exception as e:
            return json.dumps({"error": str(e)})


def get_provider(settings: Dict[str, Any]) -> LLMProvider:
    provider = (settings.get("provider") or "demo").lower()
    api_key = settings.get("api_key") or ""
    model = settings.get("model") or ""
    extra = settings.get("extra_config") or {}

    if provider == "anthropic" and api_key:
        return AnthropicProvider(api_key, model)
    if provider == "openai" and api_key:
        return OpenAIProvider(api_key, model)
    if provider == "azure" and api_key:
        return AzureOpenAIProvider(
            api_key=api_key,
            endpoint=extra.get("endpoint", ""),
            deployment=extra.get("deployment", model),
        )
    if provider == "google" and api_key:
        return GoogleProvider(api_key, model)
    if provider == "ollama":
        return OllamaProvider(extra.get("base_url", "http://localhost:11434"), model)
    return DemoProvider()
