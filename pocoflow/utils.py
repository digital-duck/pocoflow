"""PocoFlow Utilities — LLM provider abstraction and flow visualization.

Migrated from MarkovFlow's utils module and adapted for PocoFlow.

Features
--------
- **UniversalLLMProvider**: Multi-provider LLM client with self-healing
  error recovery, automatic fallbacks, and exponential backoff.
- **call_llm**: Simple convenience function mirroring PocketFlow's pattern.
- **visualize_flow**: Generate Mermaid diagrams from any PocoFlow Flow.

Supported LLM providers: OpenAI, Anthropic, Google Gemini, OpenRouter.
Provider selection and model defaults are configurable via environment
variables (see UniversalLLMProvider docstring).
"""

from __future__ import annotations

import os
import time
import random
from dataclasses import dataclass
from typing import Any, Dict, List

from pocoflow.logging import get_logger

_log = get_logger("utils")

# ---------------------------------------------------------------------------
# .env loading (best-effort)
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv

    load_dotenv()  # loads from CWD/.env or closest parent
except ImportError:
    pass  # python-dotenv is optional


# ============================================================================
# LLM Response dataclass
# ============================================================================

@dataclass
class LLMResponse:
    """Structured LLM response with metadata."""

    content: str
    success: bool
    provider: str
    model: str
    attempts: int
    total_time: float
    error_history: List[Dict[str, Any]] | None = None


# ============================================================================
# Universal LLM Provider — self-healing, multi-provider
# ============================================================================

class UniversalLLMProvider:
    """Multi-provider LLM client with self-healing error recovery.

    Self-healing means that when a call fails, the error context is fed back
    into subsequent retry prompts so the LLM can self-correct.  If the
    primary provider is exhausted the client falls back to alternatives.

    Environment variables
    ---------------------
    LLM_PROVIDER        Primary provider name (default: ``"openai"``).
    LLM_MODEL           Default model for all providers.
    LLM_MODEL_OPENAI    Override model for OpenAI.
    LLM_MODEL_ANTHROPIC Override model for Anthropic.
    LLM_MODEL_GEMINI    Override model for Google Gemini.
    LLM_MODEL_OPENROUTER Override model for OpenRouter.
    LLM_MAX_RETRIES     Max retry attempts per provider (default: 3).
    LLM_INITIAL_WAIT    Initial backoff seconds (default: 1).
    LLM_MAX_WAIT        Maximum backoff seconds (default: 30).
    OPENAI_API_KEY      API key for OpenAI.
    ANTHROPIC_API_KEY   API key for Anthropic.
    GEMINI_API_KEY      API key for Google Gemini.
    OPENROUTER_API_KEY  API key for OpenRouter.
    """

    def __init__(
        self,
        primary_provider: str | None = None,
        fallback_providers: list[str] | None = None,
        max_retries: int | None = None,
        initial_wait: float | None = None,
        max_wait: float | None = None,
    ):
        self.primary_provider = primary_provider or os.environ.get("LLM_PROVIDER", "openai")
        self.fallback_providers = fallback_providers or ["anthropic", "gemini", "openrouter"]
        self.max_retries = max_retries or int(os.environ.get("LLM_MAX_RETRIES", "3"))
        self.initial_wait = initial_wait or float(os.environ.get("LLM_INITIAL_WAIT", "1"))
        self.max_wait = max_wait or float(os.environ.get("LLM_MAX_WAIT", "30"))

        self._client_factories = {
            "openai": self._create_openai_client,
            "anthropic": self._create_anthropic_client,
            "gemini": self._create_gemini_client,
            "openrouter": self._create_openrouter_client,
        }

        # Per-provider success/failure tracking
        self.provider_stats: Dict[str, Dict[str, Any]] = {
            name: {"successes": 0, "failures": 0, "avg_time": 0.0}
            for name in self._client_factories
        }

    # -- client factories ----------------------------------------------------

    @staticmethod
    def _create_openai_client():
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        return OpenAI(api_key=api_key)

    @staticmethod
    def _create_anthropic_client():
        from anthropic import Anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        return Anthropic(api_key=api_key)

    @staticmethod
    def _create_gemini_client():
        from google import genai

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        return genai.Client(api_key=api_key)

    @staticmethod
    def _create_openrouter_client():
        from openai import OpenAI

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    # -- public API ----------------------------------------------------------

    def call(
        self,
        prompt: str,
        model: str | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Call the LLM with self-healing retry and provider fallback.

        Parameters
        ----------
        prompt :
            The user prompt to send.
        model :
            Override the default model for this call.
        **kwargs :
            Extra keyword arguments forwarded to the provider SDK.

        Returns
        -------
        LLMResponse
            Structured response (check ``.success`` before using ``.content``).
        """
        start_time = time.time()
        error_history: List[Dict[str, Any]] = []

        providers_to_try = [self.primary_provider] + [
            p for p in self.fallback_providers if p != self.primary_provider
        ]

        for provider_name in providers_to_try:
            if provider_name not in self._client_factories:
                continue

            result = self._try_provider(
                provider_name, prompt, model, error_history, **kwargs
            )

            if result.success:
                total_time = time.time() - start_time
                result.total_time = total_time
                self._update_stats(provider_name, True, total_time)

                _log.info(
                    "llm_call provider=%s model=%s attempts=%d time=%.2fs",
                    provider_name, result.model, result.attempts, total_time,
                )
                return result

            error_history.extend(result.error_history or [])
            self._update_stats(provider_name, False, time.time() - start_time)

        return LLMResponse(
            content="",
            success=False,
            provider="all_failed",
            model=model or "unknown",
            attempts=len(error_history),
            total_time=time.time() - start_time,
            error_history=error_history,
        )

    def get_provider_stats(self) -> Dict[str, Any]:
        """Return per-provider success rates and average response times."""
        return {
            name: {
                **stats,
                "success_rate": stats["successes"] / max(stats["successes"] + stats["failures"], 1),
            }
            for name, stats in self.provider_stats.items()
        }

    # -- internals -----------------------------------------------------------

    def _try_provider(
        self,
        provider_name: str,
        prompt: str,
        model: str | None,
        global_errors: List[Dict[str, Any]],
        **kwargs,
    ) -> LLMResponse:
        """Try a single provider with exponential backoff and error-context injection."""
        client = self._client_factories[provider_name]()
        wait_time = self.initial_wait
        local_errors: List[Dict[str, Any]] = []

        for attempt in range(self.max_retries):
            try:
                # On retries, inject error context so the LLM can self-correct
                effective_prompt = (
                    self._add_error_context(prompt, local_errors, global_errors)
                    if attempt > 0
                    else prompt
                )

                content = self._make_call(client, provider_name, effective_prompt, model, **kwargs)

                return LLMResponse(
                    content=content,
                    success=True,
                    provider=provider_name,
                    model=model or self._default_model(provider_name),
                    attempts=attempt + 1,
                    total_time=0.0,
                    error_history=local_errors or None,
                )

            except Exception as exc:
                local_errors.append({
                    "provider": provider_name,
                    "attempt": attempt + 1,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "timestamp": time.time(),
                })
                _log.warning(
                    "llm retry provider=%s attempt=%d/%d error=%s",
                    provider_name, attempt + 1, self.max_retries, exc,
                )

                if attempt < self.max_retries - 1:
                    jitter = random.uniform(0.1, 0.3) * wait_time
                    time.sleep(wait_time + jitter)
                    wait_time = min(wait_time * 2, self.max_wait)

        return LLMResponse(
            content="",
            success=False,
            provider=provider_name,
            model=model or self._default_model(provider_name),
            attempts=self.max_retries,
            total_time=0.0,
            error_history=local_errors,
        )

    @staticmethod
    def _add_error_context(
        original_prompt: str,
        local_errors: List[Dict[str, Any]],
        global_errors: List[Dict[str, Any]],
    ) -> str:
        """Inject recent error context so the LLM can self-correct."""
        recent = (local_errors + global_errors)[-3:]
        if not recent:
            return original_prompt

        lines = ["Previous attempts failed with the following errors:"]
        for i, err in enumerate(recent, 1):
            lines.append(f"{i}. {err['error_type']}: {err['error']}")
        lines.append("")
        lines.append("Please analyse these errors and provide a corrected response.")
        lines.append(f"Original request: {original_prompt}")
        return "\n".join(lines)

    @staticmethod
    def _make_call(
        client, provider_name: str, prompt: str, model: str | None, **kwargs
    ) -> str:
        """Dispatch to the appropriate SDK method."""
        if provider_name in ("openai", "openrouter"):
            resp = client.chat.completions.create(
                model=model or UniversalLLMProvider._default_model(provider_name),
                messages=[{"role": "user", "content": prompt}],
                **kwargs,
            )
            return resp.choices[0].message.content

        if provider_name == "anthropic":
            resp = client.messages.create(
                model=model or UniversalLLMProvider._default_model(provider_name),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.pop("max_tokens", 1024),
                **kwargs,
            )
            return resp.content[0].text

        if provider_name == "gemini":
            resp = client.models.generate_content(
                model=model or UniversalLLMProvider._default_model(provider_name),
                contents=prompt,
                **kwargs,
            )
            return resp.text

        raise ValueError(f"Unknown provider: {provider_name}")

    @staticmethod
    def _default_model(provider_name: str) -> str:
        """Resolve default model from env vars or built-in defaults."""
        env_key = f"LLM_MODEL_{provider_name.upper()}"
        env_model = os.environ.get(env_key) or os.environ.get("LLM_MODEL")
        if env_model:
            return env_model

        defaults = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-5-20250929",
            "gemini": "gemini-2.0-flash",
            "openrouter": "anthropic/claude-sonnet-4-5-20250929",
        }
        return defaults.get(provider_name, "gpt-4o")

    def _update_stats(self, provider_name: str, success: bool, elapsed: float):
        stats = self.provider_stats[provider_name]
        if success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1
        total = stats["successes"] + stats["failures"]
        stats["avg_time"] = (stats["avg_time"] * (total - 1) + elapsed) / total


# ============================================================================
# Flow Visualizer — Mermaid diagram generation
# ============================================================================

class FlowVisualizer:
    """Generate Mermaid flowchart diagrams from a PocoFlow Flow."""

    NODE_COLORS = {
        "Node": "#e1f5fe",
        "AsyncNode": "#f3e5f5",
        "Flow": "#fff3e0",
    }

    def build_mermaid(
        self,
        flow,
        *,
        include_stats: bool = False,
        max_depth: int = 10,
    ) -> str:
        """Return a Mermaid ``flowchart TD`` string for *flow*.

        Parameters
        ----------
        flow :
            A :class:`pocoflow.Flow` (or any object with a ``start`` attribute
            pointing to the first node).
        include_stats :
            If ``True`` and nodes expose ``get_stats()``, display call counts.
        max_depth :
            Maximum recursion depth to prevent infinite loops.
        """
        visited_ids: set[str] = set()
        visited_objs: set[int] = set()
        node_defs: list[str] = []
        edges: list[str] = []

        def _walk(node, node_id: str = "start", depth: int = 0):
            if depth > max_depth or node_id in visited_ids or id(node) in visited_objs:
                return
            visited_ids.add(node_id)
            visited_objs.add(id(node))

            node_type = type(node).__name__
            color = self.NODE_COLORS.get(node_type, "#f0f0f0")

            label = node_type
            if include_stats and hasattr(node, "get_stats"):
                calls = node.get_stats().get("calls", 0)
                label = f"{node_type}\\nCalls: {calls}"

            node_defs.append(f'{node_id}["{label}"]')
            node_defs.append(f"style {node_id} fill:{color}")

            if hasattr(node, "successors") and node.successors:
                for action, successor in node.successors.items():
                    succ_id = f"{node_id}_{action}"
                    edges.append(f'{node_id} -->|{action}| {succ_id}')
                    if successor:
                        _walk(successor, succ_id, depth + 1)

        start = getattr(flow, "start", None) or getattr(flow, "start_node", None)
        if start is None:
            return 'flowchart TD\n    Error["No start node found"]'

        _walk(start)

        lines = ["flowchart TD"]
        if node_defs:
            lines.extend(f"    {d}" for d in node_defs)
        if edges:
            lines.extend(f"    {e}" for e in edges)
        return "\n".join(lines)


# ============================================================================
# Convenience functions
# ============================================================================

_global_llm: UniversalLLMProvider | None = None


def _get_llm() -> UniversalLLMProvider:
    global _global_llm
    if _global_llm is None:
        _global_llm = UniversalLLMProvider()
    return _global_llm


def call_llm(prompt: str, **kwargs) -> str:
    """Simple LLM call — returns the response text.

    Uses the global :class:`UniversalLLMProvider` with self-healing retry.
    """
    response = _get_llm().call(prompt, **kwargs)
    if not response.success:
        errors = response.error_history or []
        last = errors[-1]["error"] if errors else "unknown error"
        raise RuntimeError(f"LLM call failed after {response.attempts} attempts: {last}")
    return response.content


def get_llm_stats() -> Dict[str, Any]:
    """Return per-provider success/failure statistics."""
    return _get_llm().get_provider_stats()


def visualize_flow(flow, **kwargs) -> str:
    """Generate a Mermaid diagram string for a PocoFlow Flow."""
    return FlowVisualizer().build_mermaid(flow, **kwargs)
