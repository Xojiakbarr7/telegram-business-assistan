"""OpenRouter CLI wrapper for the Telegram Business Assistant Bot."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import openai


class OpenRouterError(Exception):
    """Base OpenRouter error."""

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.detail = detail


class OpenRouterTimeout(OpenRouterError):
    """OpenRouter timeout error."""
    pass


class OpenRouterAuthError(OpenRouterError):
    """OpenRouter authentication error."""
    pass


class OpenRouterLimitError(OpenRouterError):
    """OpenRouter rate limit error."""

    def __init__(
        self,
        detail: str,
        resets_at: float | None = None,
        reset_text: str = "",
    ) -> None:
        message = f"OpenRouter rate limit reached (resets {reset_text or 'unknown'})"
        super().__init__(message, detail)
        self.resets_at = resets_at
        self.reset_text = reset_text


def classify_openrouter_error(exc: Exception) -> OpenRouterError:
    """Classify OpenRouter exception into appropriate error type."""
    import re

    msg = str(exc).lower()

    # Rate limit errors
    if isinstance(exc, openai.RateLimitError) or "rate limit" in msg or "429" in msg:
        return OpenRouterLimitError(
            detail=str(exc),
            reset_text="retry after",
        )

    # Auth errors
    if isinstance(exc, openai.AuthenticationError) or "unauthorized" in msg or "401" in msg or "invalid api key" in msg:
        return OpenRouterAuthError(
            "OpenRouter authentication failed. Check OPENROUTER_API_KEY.",
            detail=str(exc)[:300],
        )

    # Timeout errors
    if isinstance(exc, (openai.APITimeoutError, asyncio.TimeoutError)) or "timeout" in msg:
        return OpenRouterTimeout(str(exc)[:500])

    # Generic error
    return OpenRouterError(str(exc)[:500])


@dataclass
class InspectResult:
    """Result of inspect() call."""
    auth: str
    init: dict[str, Any]
    reply: str


class OpenRouterCLI:
    """Async wrapper for OpenRouter API (OpenAI-compatible)."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "anthropic/claude-3.5-sonnet",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: int = 120,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Initialize OpenAI client with OpenRouter base URL
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            default_headers={
                "HTTP-Referer": "https://github.com/telegram-business-assistant",
                "X-Title": "Telegram Business Assistant Bot",
                **(extra_headers or {}),
            }
        )

    def __repr__(self) -> str:
        return f"OpenRouterCLI(model={self.model!r})"

    @property
    def auth_mode(self) -> str:
        return f"OpenRouter API key ({self.model})"

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Generate a reply using OpenRouter API.

        Args:
            system_prompt: System prompt with profile
            user_prompt: User prompt with conversation history

        Returns:
            Reply text (empty string if SKIP_TOKEN)
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
        except asyncio.TimeoutError:
            raise OpenRouterTimeout("OpenRouter API timed out")
        except openai.RateLimitError as e:
            raise OpenRouterLimitError(
                detail=str(e),
                reset_text="retry after",
            )
        except openai.AuthenticationError as e:
            raise OpenRouterAuthError(
                "OpenRouter API key rejected or expired.",
                detail=str(e)[:300],
            )
        except openai.APIError as e:
            raise classify_openrouter_error(e)
        except Exception as e:
            raise OpenRouterError(f"Failed to call OpenRouter API: {e}")

        # Extract reply text
        content = response.choices[0].message.content
        return content.strip() if content else ""

    async def inspect(self) -> InspectResult:
        """
        Run a minimal OpenRouter call to inspect configuration.

        Returns:
            InspectResult with auth mode, init data, and reply
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Reply with exactly: OK"},
                    {"role": "user", "content": "ping"},
                ],
                max_tokens=10,
                temperature=0,
            )
            reply = response.choices[0].message.content or ""
        except Exception as e:
            raise OpenRouterError(f"Inspect failed: {e}")

        return InspectResult(
            auth=self.auth_mode,
            init={
                "model": self.model,
                "base_url": self.base_url,
            },
            reply=reply.strip(),
        )


def make_openrouter_cli(
    api_key: str,
    *,
    model: str = "anthropic/claude-3.5-sonnet",
    base_url: str = "https://openrouter.ai/api/v1",
    timeout: int = 120,
    max_tokens: int = 4000,
    temperature: float = 0.7,
) -> OpenRouterCLI:
    """Create OpenRouterCLI instance."""
    return OpenRouterCLI(
        api_key=api_key,
        model=model,
        base_url=base_url,
        timeout=timeout,
        max_tokens=max_tokens,
        temperature=temperature,
    )