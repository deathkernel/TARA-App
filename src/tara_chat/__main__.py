"""Interactive conversation-first TARA CLI."""
from __future__ import annotations

import os

from .brain import TARABrain
from .llm_provider_factory import provider_from_env
from .memory import LongTermMemory


def _display_text(value, *, limit=240) -> str:
    text = "".join(char for char in str(value or "") if char.isprintable())
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _run_handler_command(command_text: str) -> str | None:
    """Handle opt-in, fixed read-only diagnostics delegated to Handler."""
    parts = command_text.strip().split(maxsplit=1)
    if not parts or parts[0].lower() not in {"/handler", "/diagnose"}:
        return None
    action = parts[1].strip().lower() if len(parts) > 1 else "help"
    if action in {"", "help"}:
        from .handler_bridge import TARAHandler
        return "Handler read-only commands: " + ", ".join(TARAHandler.available_commands())
    try:
        from .handler_bridge import HandlerUnavailable, handler_from_env
        bridge = handler_from_env()
        result = bridge.run(action)
        status = "completed" if result.ok else f"exited with code {result.returncode}"
        output = _display_text(result.output, limit=6000)
        return f"Handler {result.command}: {status}\n{output or '(no output)'}"
    except (HandlerUnavailable, OSError, ValueError) as exc:
        return f"Handler request not run: {_display_text(exc, limit=500)}"


def _run_memory_command(command_text: str, brain) -> str | None:
    """Handle explicit persistent-memory commands without involving the LLM."""
    parts = command_text.strip().split(maxsplit=1)
    if not parts:
        return None
    verb = parts[0].lower()
    if verb not in {"/memory", "/remember", "/learn", "/forget"}:
        return None
    argument = parts[1].strip() if len(parts) > 1 else ""
    memory = getattr(brain, "memory", None)
    if memory is None:
        return "Memory is not configured for this chat session."

    try:
        if verb == "/memory":
            if argument:
                results = memory.retrieve(argument, limit=5)
                if not results:
                    return "No matching saved memories."
                lines = ["Matching saved memories:"]
                for item in results:
                    if isinstance(item, dict):
                        score = item.get("score")
                        suffix = f" (score: {score:.2f})" if isinstance(score, (int, float)) else ""
                        lines.append(f"- {_display_text(item.get('key'), limit=120)}: {_display_text(item.get('value'), limit=300)}{suffix}")
                return "\n".join(lines)
            keys = memory.keys()
            if not keys:
                return "No saved memories yet. Use /remember key=value to save one."
            lines = ["Saved memories:"]
            for key in keys[:20]:
                lines.append(f"- {_display_text(key, limit=120)}: {_display_text(memory.recall(key), limit=300)}")
            if len(keys) > 20:
                lines.append(f"... and {len(keys) - 20} more.")
            return "\n".join(lines)

        if verb in {"/remember", "/learn"}:
            if "=" not in argument:
                return "Usage: /remember key=value (or /learn key=value)"
            key, value = (part.strip() for part in argument.split("=", 1))
            if not key or not value:
                return "Both memory key and value are required."
            if len(key) > 120 or len(value) > 2000:
                return "Memory key must be at most 120 characters and value at most 2,000 characters."
            memory.remember(key, value)
            memory.save()
            return f"Saved memory: {_display_text(key, limit=120)}"

        if not argument:
            return "Usage: /forget key"
        if len(argument) > 120:
            return "Memory key must be at most 120 characters."
        removed = memory.forget(argument)
        if removed is None:
            return f"No saved memory found for: {_display_text(argument, limit=120)}"
        memory.save()
        return f"Forgot memory: {_display_text(argument, limit=120)}"
    except (OSError, TypeError, ValueError) as exc:
        return f"Memory operation failed: {_display_text(exc, limit=240)}"


def chat_loop(brain, *, input_fn=input, output_fn=print) -> None:
    """Run an interactive chat with bounded in-session context."""
    output_fn("TARA chat is ready. Type /help for commands, /exit to quit.")
    while True:
        try:
            prompt = input_fn("You: ")
        except (EOFError, KeyboardInterrupt):
            output_fn("\nTARA: Chat closed.")
            return
        prompt = prompt.strip()
        if not prompt:
            continue
        command = prompt.lower()
        if command in {"/exit", "/quit", "/bye"}:
            output_fn("TARA: Bye, bhai!")
            return
        if command == "/help":
            output_fn("Commands: /help, /exit, /memory [query], /remember key=value, /forget key, /handler [action]")
            continue
        if command == "/handler" or command == "/diagnose" or command.startswith(("/handler ", "/diagnose ")):
            handler_result = _run_handler_command(prompt)
            output_fn(f"TARA: {handler_result or 'Handler command not recognized.'}")
            continue
        if command in {"/memory", "/learn", "/remember", "/forget"} or command.startswith(("/memory ", "/learn ", "/remember ", "/forget ")):
            result = _run_memory_command(prompt, brain)
            if result is not None:
                output_fn(f"TARA: {result}")
                continue
        try:
            provider = getattr(brain, "llm_provider", None)
            default_tokens = getattr(provider, "default_max_tokens", 128)
            raw_tokens = os.getenv("TARA_MAX_RESPONSE_TOKENS", "").strip()
            if raw_tokens:
                try:
                    max_tokens = int(raw_tokens)
                except ValueError as exc:
                    raise ValueError("TARA_MAX_RESPONSE_TOKENS must be a positive integer") from exc
                if max_tokens <= 0:
                    raise ValueError("TARA_MAX_RESPONSE_TOKENS must be a positive integer")
            else:
                max_tokens = default_tokens
            response = brain.respond(prompt, max_new_tokens=max_tokens, temperature=0.6)
        except (RuntimeError, TimeoutError, OSError, ValueError) as exc:
            output_fn(f"TARA: I couldn't generate a response. Check the configured language provider. Details: {_display_text(exc)}")
            continue
        output_fn(f"TARA: {response.text}")


def main() -> int:
    os.environ.setdefault("TARA_LLM_BACKEND", "ollama")
    try:
        provider = provider_from_env()
        if provider is None:
            print("TARA chat needs a language provider. Set TARA_LLM_BACKEND=ollama.")
            return 2
        memory_path = os.getenv("TARA_MEMORY_PATH", "data/tara_memory.json").strip()
        if not memory_path:
            raise ValueError("TARA_MEMORY_PATH must not be empty")
        brain = TARABrain(llm_provider=provider, memory=LongTermMemory(memory_path))
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"TARA could not start: {exc}")
        return 2
    print(
        "TARA resource profile: "
        f"{getattr(provider, 'power_mode', 'custom')} "
        f"(context={getattr(provider, 'num_ctx', 'default')}, "
        f"CPU threads={getattr(provider, 'num_thread', 'auto')}, "
        f"batch={getattr(provider, 'num_batch', 'default')}, "
        f"max response tokens={getattr(provider, 'default_max_tokens', 128)})"
    )
    chat_loop(brain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
