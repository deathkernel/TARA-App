"""Conversation-only runtime for TARA."""
from __future__ import annotations

from dataclasses import dataclass

from .memory import LongTermMemory


# Answer-style guidance draws on standard instruction-tuning practice:
# lead with the answer, compress reasoning, prefer clarity over length,
# and separate verified claims from uncertainty (no invented sources).
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

# Default completion budget: 128 was too low and produced truncated replies.
DEFAULT_MAX_NEW_TOKENS = 1536


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

        recalled = tuple(self.memory.retrieve(prompt, limit=5))
        sections = []
        if recalled:
            memory_lines = [
                f"- {item['key']}: {item['value']}"
                for item in recalled
                if isinstance(item, dict) and "key" in item and "value" in item
            ]
            if memory_lines:
                sections.append(
                    "Relevant saved memories (user-managed; use only when relevant):\n"
                    + "\n".join(memory_lines)
                )

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
