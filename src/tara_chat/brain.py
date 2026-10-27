"""Conversation-only runtime for TARA."""
from __future__ import annotations

from dataclasses import dataclass

from .memory import LongTermMemory


DEFAULT_SYSTEM_PROMPT = (
    "You are TARA, a helpful conversational AI. Answer the user's latest message "
    "naturally and accurately. Use prior conversation context when relevant. "
    "Do not claim to have performed actions outside this chat."
)


@dataclass(frozen=True)
class BrainResponse:
    text: str
    recalled: tuple = ()


class TARABrain:
    """Keep the chat boundary small: provider, session context, and explicit memory."""

    def __init__(
        self,
        model=None,
        tokenizer=None,
        *,
        memory=None,
        llm_provider=None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_history_turns: int = 12,
        **_unused,
    ):
        if max_history_turns < 1:
            raise ValueError("max_history_turns must be positive")
        self.model = model
        self.tokenizer = tokenizer
        self.memory = LongTermMemory() if memory is None else memory
        self.llm_provider = llm_provider
        self.system_prompt = system_prompt
        self.max_history_turns = max_history_turns
        self.conversation_history: list[tuple[str, str]] = []
        self.last_emotion = "neutral"

    def clear_context(self) -> None:
        """Clear only the active session context; saved memories are preserved."""
        self.conversation_history.clear()

    def respond(
        self,
        prompt: str,
        *,
        remember_key: str | None = None,
        importance: float = 1.0,
        max_new_tokens: int = 128,
        temperature: float = 0.6,
        **_unused,
    ) -> BrainResponse:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must not be empty")
        if self.llm_provider is None:
            raise RuntimeError("No language provider configured. Start TARA with the Ollama backend.")
        if isinstance(max_new_tokens, bool) or not isinstance(max_new_tokens, int) or max_new_tokens <= 0:
            raise ValueError("max_new_tokens must be a positive integer")

        recalled = tuple(self.memory.retrieve(prompt, limit=5))
        sections = []
        if recalled:
            memory_lines = [
                f"- {item['key']}: {item['value']}"
                for item in recalled
                if isinstance(item, dict) and "key" in item and "value" in item
            ]
            if memory_lines:
                sections.append("Relevant saved memories (user-managed; use only when relevant):\n" + "\n".join(memory_lines))

        if self.conversation_history:
            history_lines = []
            for role, content in self.conversation_history[-self.max_history_turns * 2:]:
                history_lines.append(f"{role}: {content}")
            sections.append("Recent conversation:\n" + "\n".join(history_lines))

        sections.append("User: " + prompt.strip())
        context = "\n\n".join(sections)
        text = self.llm_provider.complete(
            context,
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
        return BrainResponse(text=text.strip(), recalled=recalled)
