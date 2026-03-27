"""
LLM client wrapper
Use OpenAI format uniformly
"""

import json
import re
import time
from typing import Optional, Dict, Any, List
import openai
from openai import OpenAI

from ..config import Config
from ..utils.logger import get_logger


logger = get_logger('mirofish.llm')


class LLMClient:
    """LLM client"""
    MAX_RETRIES = 2
    RETRY_DELAY_SECONDS = 1.5
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        self.timeout = timeout
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY not configured")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Send chat request
        
        Args:
            messages: message list
            temperature: temperature parameter
            max_tokens: maximum token count
            response_format: response format (e.g., JSON mode)
            
        Returns:
            model response text
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if response_format:
            kwargs["response_format"] = response_format

        last_error: Optional[Exception] = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content or ""
                content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()

                if response_format and not content:
                    logger.warning(
                        "LLM model %s returned empty content in JSON mode; retrying without response_format",
                        self.model,
                    )
                    fallback_kwargs = dict(kwargs)
                    fallback_kwargs.pop("response_format", None)
                    response = self.client.chat.completions.create(**fallback_kwargs)
                    content = response.choices[0].message.content or ""
                    content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()

                return content
            except (openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError) as exc:
                last_error = exc
                if attempt >= self.MAX_RETRIES:
                    raise
                logger.warning(
                    "LLM request failed for model %s (attempt %s/%s): %s",
                    self.model,
                    attempt + 1,
                    self.MAX_RETRIES + 1,
                    exc,
                )
                time.sleep(self.RETRY_DELAY_SECONDS * (attempt + 1))

        if last_error is not None:
            raise last_error
        raise RuntimeError("LLM request failed without a specific error")
    
    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Send chat request and return JSON
        
        Args:
            messages: message list
            temperature: temperature parameter
            max_tokens: maximum token count
            
        Returns:
            parsed JSON object
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        cleaned_response = self._clean_json_text(response)
        
        if not cleaned_response:
            raise ValueError("LLM returned empty content in JSON mode")
        
        try:
            return self._parse_json_response(response)
        except ValueError as first_error:
            logger.warning("LLM returned JSON cannot be parsed directly, attempting automatic repair: %s", str(first_error))

        repair_messages = [
            {
                "role": "system",
                "content": (
                    "You are a JSON fixer.",
                    "Please fix the user-provided content into a valid JSON object.",
                    "Only output the JSON object, do not output explanations, Markdown, comments, or extra text.",
                )
            },
            {
                "role": "user",
                "content": f"Please fix the following content into a valid JSON object, only output JSON: \n\n{cleaned_response}",
            }
        ]
        
        repaired_response = self.chat(
            messages=repair_messages,
            temperature=0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        
        try:
            return self._parse_json_response(repaired_response)
        except ValueError as repair_error:
            logger.warning("JSON repair failed, retry original request once: %s", str(repair_error))
        
        retry_response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        return self._parse_json_response(retry_response)

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse the JSON text returned by LLM, tolerating common wrapper formats as much as possible."""
        cleaned_response = self._clean_json_text(response)
        
        candidates = [cleaned_response]
        extracted = self._extract_json_object(cleaned_response)
        if extracted and extracted not in candidates:
            candidates.append(extracted)
        
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if not isinstance(parsed, dict):
                    raise ValueError("LLM returned JSON is not an object")
                return parsed
            except (json.JSONDecodeError, ValueError):
                continue
        
        preview = cleaned_response[:1000]
        raise ValueError(f"LLM returned JSON format is invalid: {preview}")

    def _clean_json_text(self, response: str) -> str:
        """Clean common Markdown wrappers and surrounding noise."""
        cleaned = (response or "").strip()
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\n?```\s*$', '', cleaned)
        return cleaned.strip()

    def _extract_json_object(self, text: str) -> Optional[str]:
        """Extract the first balanced JSON object from mixed text."""
        start = text.find('{')
        if start == -1:
            return None
        
        depth = 0
        in_string = False
        escape = False
        
        for idx in range(start, len(text)):
            ch = text[idx]
            
            if in_string:
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            
            if ch == '"':
                in_string = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return text[start:idx + 1]
        
        return None
