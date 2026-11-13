"""Conversation-only runtime for TARA."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .memory import LongTermMemory
from .token_budget import ContextBudgetError, ContextSection, estimate_tokens, pack_context


DEFAULT_SYSTEM_PROMPT = (
    "You are TARA, a precise conversational assistant. "
    "Goal: answers that are simple, polished, and correct—not long or showy.\n\n"
    "Core rules:\n"
    "1. Lead with the direct answer or takeaway in the first sentence or two.\n"
    "2. Then add only the explanation, steps, or example the user still needs.\n"
    "3. Prefer short sentences and plain words. Explain jargon once, briefly.\n"
    "4. Match depth to the question: a simple question gets a short reply; "
    "a complex one gets structured Markdown without padding.\n"
    "5. Do not invent facts, papers, URLs, benchmarks, or tool results. "
    "If evidence is missing, say what is known vs uncertain.\n"
    "6. Never claim you ran code, changed files, or called external systems "
    "unless that action was actually verified in this session.\n\n"
    "Structure by task (omit empty sections; do not print these labels):\n"
    "- How-to / troubleshooting: ordered steps; commands in language-labelled "
    "fenced blocks; where to run them; expected result when useful.\n"
    "- Code: state assumptions; give complete runnable code when asked; "
    "add a minimal test or sample output when it helps.\n"
    "- Comparisons: decision criteria first; compact table only when it clarifies.\n"
    "- Study: short definition, key points, one example or flow.\n"
    "- Plans: priorities and the single next concrete action.\n"
    "- Research / factual claims: state the claim, note confidence, cite real "
    "sources only when available; never fabricate paper titles or DOIs.\n\n"
    "Formatting: readable Markdown—headings only for multi-part answers, "
    "bullets for lists, numbered steps for sequences, tables for true "
    "comparisons, language-labelled fences for code. "
    "No giant paragraphs, no repeated conclusions, no preamble like "
    "‘Great question’, no raw metadata dumps.\n\n"
    "Use the user’s language when practical. Stay helpful, calm, and specific."
)

DEFAULT_MAX_NEW_TOKENS = 1536
DEFAULT_MAX_INPUT_TOKENS = 12_000
DEFAULT_MEMORY_TOKEN_BUDGET = 1_200
DEFAULT_RECENT_HISTORY_TURNS = 6


@dataclass(frozen=True)
class BrainResponse:
    text: str
    recalled: tuple = ()
    estimated_input_tokens: int = 0
    omitted_context: tuple[str, ...] = ()
    provider_usage: dict | None = None


class TARABrain:
    """Bounded conversation context, selective memory, and one inference call."""

    def __init__(
        self,
        model=None,
        tokenizer=None,
        *,
        memory=None,
        llm_provider=None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_history_turns: int = 12,
        max_input_tokens: int = DEFAULT_MAX_INPUT_TOKENS,
        memory_token_budget: int = DEFAULT_MEMORY_TOKEN_BUDGET,
        recent_history_turns: int = DEFAULT_RECENT_HISTORY_TURNS,
        token_estimator: Callable[[str], int] = estimate_tokens,
        **_unused,
    ):
        if max_history_turns < 1:
            raise ValueError("max_history_turns must be positive")
        if (
            isinstance(max_input_tokens, bool)
            or not isinstance(max_input_tokens, int)
            or max_input_tokens < 1
            or isinstance(memory_token_budget, bool)
            or not isinstance(memory_token_budget, int)
            or memory_token_budget < 0
            or isinstance(recent_history_turns, bool)
            or not isinstance(recent_history_turns, int)
            or recent_history_turns < 0
            or not callable(token_estimator)
        ):
            raise ValueError("context budgets and token estimator are invalid")
        self.model = model
        self.tokenizer = tokenizer
        self.memory = LongTermMemory() if memory is None else memory
        self.llm_provider = llm_provider
        self.system_prompt = system_prompt
        self.max_history_turns = max_history_turns
        self.max_input_tokens = max_input_tokens
        self.memory_token_budget = memory_token_budget
        self.recent_history_turns = min(recent_history_turns, max_history_turns)
        self.token_estimator = token_estimator
        self.conversation_history: list[tuple[str, str]] = []
        self.last_emotion = "neutral"

    def clear_context(self) -> None:
        """Clear only the active session context; saved memories are preserved."""
        self.conversation_history.clear()

    def _build_context(self, prompt: str, recalled: tuple, max_new_tokens: int):
        sections = [
            ContextSection("User request", prompt.strip(), priority=10_000, required=True)
        ]
        memory_parts: list[str] = []
        memory_used = 0
        for item in recalled:
            if not isinstance(item, dict) or "key" not in item or "value" not in item:
                continue
            line = f"- {item['key']}: {item['value']}"
            cost = self.token_estimator(line)
            if memory_used + cost > self.memory_token_budget:
                continue
            memory_parts.append(line)
            memory_used += cost
        if memory_parts:
            sections.append(ContextSection(
                "Relevant saved memories (user-managed; use only when relevant)",
                "\n".join(memory_parts), priority=300,
            ))

        history = self.conversation_history[-self.recent_history_turns * 2:] if self.recent_history_turns else []
        if history:
            history_lines = [f"{role}: {content}" for role, content in history]
            sections.append(ContextSection(
                "Recent conversation", "\n".join(history_lines), priority=200,
            ))

        # System instructions are a separate provider message, but count against
        # the same context budget so the planner cannot silently overfill it.
        system_tokens = self.token_estimator(self.system_prompt)
        plan = pack_context(
            sections,
            max_tokens=self.max_input_tokens,
            reserve_tokens=max_new_tokens + system_tokens,
            estimator=self.token_estimator,
        )
        return plan

    def respond(
        self,
        prompt: str,
        *,
        remember_key: str | None = None,
        importance: float = 1.0,
        max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
        temperature: float = 0.5,
        **_unused,
    ) -> BrainResponse:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must not be empty")
        if self.llm_provider is None:
            raise RuntimeError(
                "No OmniRoute provider configured. "
                "Set TARA_OMNIROUTE_API_KEY and start the OmniRoute gateway."
            )
        if isinstance(max_new_tokens, bool) or not isinstance(max_new_tokens, int) or max_new_tokens <= 0:
            raise ValueError("max_new_tokens must be a positive integer")

        recalled = tuple(self.memory.retrieve(prompt, limit=8))
        try:
            plan = self._build_context(prompt, recalled, max_new_tokens)
        except ContextBudgetError as exc:
            raise ValueError(
                "The current request and system instructions exceed TARA's configured context budget; "
                "increase the budget or shorten the request."
            ) from exc

        text = self.llm_provider.complete(
            plan.text,
            system=self.system_prompt,
            max_completion_tokens=max_new_tokens,
            temperature=temperature,
        )
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("The language provider returned an empty response")

        self.conversation_history.extend((("User", prompt.strip()), ("TARA", text.strip())))
        self.conversation_history = self.conversation_history[-self.max_history_turns * 2:]
        if remember_key is not None:
            self.memory.remember(remember_key, prompt.strip(), importance=importance)
            self.memory.save()

        provider_usage = getattr(self.llm_provider, "last_usage", None)
        return BrainResponse(
            text=text.strip(),
            recalled=recalled,
            estimated_input_tokens=plan.estimated_tokens + self.token_estimator(self.system_prompt),
            omitted_context=plan.omitted_sections,
            provider_usage=dict(provider_usage) if isinstance(provider_usage, dict) else None,
        )
