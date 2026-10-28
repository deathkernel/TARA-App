"""Windows-only floating companion for the existing TARA-App local server.

The pet UI is local. It sends a request only after the user submits a chat message.
It does not execute desktop actions or model-generated commands in this first slice.
"""
from __future__ import annotations

import json
import math
import sys
import threading
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit


def validate_server_url(value: str) -> str:
    """Accept only a loopback HTTP origin with an explicit non-privileged port."""
    if not isinstance(value, str) or not value or len(value) > 256:
        raise ValueError("server URL is invalid")
    try:
        parsed = urlsplit(value)
        port = parsed.port or 80
    except ValueError:
        raise ValueError("server URL is invalid") from None
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or not 1024 <= port <= 65535
    ):
        raise ValueError("server URL must be a loopback HTTP origin on port 1024–65535")
    return f"http://{parsed.hostname}:{port}"


def build_chat_payload(question: str, session_id: str, history: list[dict[str, str]]) -> dict[str, Any]:
    """Build a bounded request compatible with TARA-App's existing /api/chat API."""
    if not isinstance(question, str) or not question.strip() or len(question) > 20_000:
        raise ValueError("message must contain 1–20000 characters")
    if not isinstance(session_id, str) or not session_id or len(session_id) > 128:
        raise ValueError("session ID is invalid")
    safe_history: list[dict[str, str]] = []
    for item in history[-20:]:
        if (
            isinstance(item, dict)
            and item.get("role") in {"user", "assistant"}
            and isinstance(item.get("content"), str)
            and len(item["content"]) <= 20_000
        ):
            safe_history.append({"role": item["role"], "content": item["content"]})
    return {
        "question": question.strip(),
        "session_id": session_id,
        "attachments": [],
        "history": safe_history,
    }


def trim_transcript_text(text: str, max_chars: int = 100_000) -> str:
    """Keep the newest transcript content within a predictable memory bound."""
    if not isinstance(text, str):
        raise TypeError("transcript must be text")
    if not isinstance(max_chars, int) or isinstance(max_chars, bool) or max_chars < 1:
        raise ValueError("max_chars must be a positive integer")
    return text[-max_chars:]


def extract_answer(payload: Any) -> str:
    """Extract the existing TARA response shape without trusting arbitrary types."""
    if not isinstance(payload, dict):
        raise ValueError("TARA returned an invalid response")
    result = payload.get("result")
    data = result.get("data") if isinstance(result, dict) else None
    candidates = [
        data.get("text") if isinstance(data, dict) else None,
        data.get("reply") if isinstance(data, dict) else None,
        data.get("answer") if isinstance(data, dict) else None,
        result.get("error") if isinstance(result, dict) else None,
        data.get("message") if isinstance(data, dict) else None,
        payload.get("error"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return json.dumps(payload, ensure_ascii=False)[:20_000]


class _LoopbackOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse redirects so chat requests cannot escape the validated loopback origin."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


def _post_chat(server_url: str, payload: dict[str, Any]) -> str:
    request = urllib.request.Request(
        f"{server_url}/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(_LoopbackOnlyRedirectHandler)
    try:
        with opener.open(request, timeout=45) as response:
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise RuntimeError("TARA response exceeded the 1 MB limit")
            result = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"TARA request failed (HTTP {exc.code})") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RuntimeError("TARA is not reachable. Check that the local app is running.") from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("TARA returned an invalid response.") from None
    return extract_answer(result)


def run_floating_pet(app: Any, *, port: int = 8765) -> None:
    """Run the local TARA server in a background thread and the pet in the UI thread."""
    if sys.platform != "win32":
        raise RuntimeError("The floating pet is supported on Windows only.")
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        # Keep the existing web UI usable on Python builds without Tcl/Tk.
        from tara_app.webapp import serve
        print("Windows floating pet needs Python with Tcl/Tk; opening TARA's local web interface instead.", file=sys.stderr)
        serve(app, port=port)
        return

    if not 1024 <= port <= 65535:
        raise ValueError("port must be between 1024 and 65535")
    try:
        root = tk.Tk()
    except tk.TclError:
        from tara_app.webapp import serve
        print("Windows floating pet could not initialize; opening TARA's local web interface instead.", file=sys.stderr)
        serve(app, port=port)
        return

    root.title("TARA Floating Pet")
    root.geometry("132x150+120+120")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    background = "#111116"
    try:
        root.configure(bg=background)
        root.attributes("-transparentcolor", background)
    except tk.TclError:
        root.configure(bg=background)

    canvas = tk.Canvas(root, width=132, height=150, bg=background, highlightthickness=0, bd=0, cursor="hand2")
    canvas.pack(fill="both", expand=True)
    session_id = f"windows-pet-{threading.get_ident()}"
    history: list[dict[str, str]] = []
    chat_window: Any = None
    transcript: Any = None
    entry: Any = None
    send_button: Any = None
    busy = False
    animation_tick = 0
    drag = {"x": 0, "y": 0, "root_x": 0, "root_y": 0, "moved": False}

    def draw_pet() -> None:
        nonlocal animation_tick
        canvas.delete("all")
        bob = math.sin(animation_tick * 0.65) * 2.5
        canvas.create_oval(31, 105 + bob, 101, 121 + bob, fill="#050509", outline="")
        canvas.create_oval(27, 32 + bob, 105, 108 + bob, fill="#6b48b7", outline="#c6a5ff", width=2)
        canvas.create_oval(34, 38 + bob, 98, 100 + bob, fill="#9b78ed", outline="")
        canvas.create_oval(43, 43 + bob, 73, 70 + bob, fill="#c9b5ff", outline="")
        canvas.create_oval(49, 46 + bob, 61, 58 + bob, fill="#e7deff", outline="")
        if animation_tick % 9 == 0:
            canvas.create_line(47, 70 + bob, 57, 70 + bob, fill="#241b3d", width=3, capstyle="round")
            canvas.create_line(75, 70 + bob, 85, 70 + bob, fill="#241b3d", width=3, capstyle="round")
        else:
            canvas.create_oval(47, 63 + bob, 58, 76 + bob, fill="#211637", outline="")
            canvas.create_oval(74, 63 + bob, 85, 76 + bob, fill="#211637", outline="")
            canvas.create_oval(50, 65 + bob, 53, 68 + bob, fill="#ffffff", outline="")
            canvas.create_oval(77, 65 + bob, 80, 68 + bob, fill="#ffffff", outline="")
        canvas.create_oval(37, 76 + bob, 47, 82 + bob, fill="#e8a9e7", outline="")
        canvas.create_oval(85, 76 + bob, 95, 82 + bob, fill="#e8a9e7", outline="")
        canvas.create_arc(59, 75 + bob, 74, 87 + bob, start=205, extent=130, style="arc", outline="#2a1742", width=2)
        canvas.create_text(66, 132 + bob, text="TARA", fill="#e6d8ff", font=("Segoe UI", 10, "bold"))
        canvas.create_text(66, 145, text="click to chat", fill="#c5b4e7", font=("Segoe UI", 7))
        animation_tick += 1
        root.after(650, draw_pet)

    def append_transcript(speaker: str, text: str) -> None:
        if transcript is None:
            return
        transcript.configure(state="normal")
        transcript.insert("end", f"{speaker}\n{text}\n\n")
        content = transcript.get("1.0", "end-1c")
        bounded = trim_transcript_text(content)
        if bounded != content:
            transcript.delete("1.0", "end")
            transcript.insert("1.0", bounded)
        transcript.see("end")
        transcript.configure(state="disabled")

    def open_chat() -> None:
        nonlocal chat_window, transcript, entry, send_button
        if chat_window is not None and chat_window.winfo_exists():
            chat_window.deiconify()
            chat_window.lift()
            entry.focus_set()
            return
        chat_window = tk.Toplevel(root)
        chat_window.title("Chat with TARA")
        chat_window.geometry("390x520+260+180")
        chat_window.minsize(320, 380)
        chat_window.configure(bg="#17171f")
        chat_window.attributes("-topmost", True)
        chat_window.protocol("WM_DELETE_WINDOW", chat_window.withdraw)

        header = tk.Frame(chat_window, bg="#211b2d", padx=14, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="✦  TARA", bg="#211b2d", fg="#e5d6ff", font=("Segoe UI", 12, "bold")).pack(side="left")
        tk.Label(header, text="Local assistant", bg="#211b2d", fg="#b8afc9", font=("Segoe UI", 9)).pack(side="right")

        body = tk.Frame(chat_window, bg="#17171f", padx=12, pady=12)
        body.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(body)
        scroll.pack(side="right", fill="y")
        transcript = tk.Text(
            body, wrap="word", state="disabled", yscrollcommand=scroll.set,
            bg="#17171f", fg="#f0edf7", insertbackground="#f0edf7",
            relief="flat", padx=8, pady=8, font=("Segoe UI", 10),
        )
        transcript.pack(side="left", fill="both", expand=True)
        scroll.configure(command=transcript.yview)
        append_transcript("TARA", "Hey! Click the pet any time to chat. I'll only send a request when you submit a message.")

        composer = tk.Frame(chat_window, bg="#17171f", padx=12, pady=10)
        composer.pack(fill="x")
        entry = tk.Entry(composer, bg="#24232c", fg="#f7f3ff", insertbackground="#f7f3ff", relief="flat", font=("Segoe UI", 10))
        entry.pack(side="left", fill="x", expand=True, ipady=9, padx=(0, 8))
        entry.bind("<Return>", lambda _event: send_message())
        send_button = tk.Button(
            composer, text="Send", command=send_message, bg="#b99af7", fg="#20172e",
            activebackground="#cdb8ff", relief="flat", padx=12, pady=7,
        )
        send_button.pack(side="right")
        entry.focus_set()

    def send_message() -> None:
        nonlocal busy, history
        if busy or entry is None or not entry.winfo_exists():
            return
        question = entry.get().strip()
        if not question:
            return
        try:
            payload = build_chat_payload(question, session_id, history)
        except ValueError as exc:
            append_transcript("Notice", str(exc))
            return
        entry.delete(0, "end")
        append_transcript("You", question)
        busy = True
        if send_button is not None:
            send_button.configure(state="disabled", text="…")

        def worker() -> None:
            nonlocal busy, history
            try:
                answer = _post_chat(server_url, payload)
                history = payload["history"] + [
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": answer},
                ]
                outcome = (True, answer)
            except (RuntimeError, ValueError) as exc:
                outcome = (False, str(exc))

            def finish() -> None:
                nonlocal busy
                busy = False
                if send_button is not None and send_button.winfo_exists():
                    send_button.configure(state="normal", text="Send")
                if outcome[0]:
                    append_transcript("TARA", outcome[1])
                else:
                    append_transcript("Notice", outcome[1])

            try:
                root.after(0, finish)
            except tk.TclError:
                pass

        threading.Thread(target=worker, name="tara-pet-chat", daemon=True).start()

    def on_press(event: Any) -> None:
        drag.update(x=event.x_root, y=event.y_root, root_x=root.winfo_x(), root_y=root.winfo_y(), moved=False)

    def on_drag(event: Any) -> None:
        dx, dy = event.x_root - drag["x"], event.y_root - drag["y"]
        if abs(dx) + abs(dy) > 5:
            drag["moved"] = True
            root.geometry(f"+{drag['root_x'] + dx}+{drag['root_y'] + dy}")

    def on_release(_event: Any) -> None:
        if not drag["moved"]:
            open_chat()

    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="Chat with TARA", command=open_chat)
    menu.add_separator()
    menu.add_command(label="Exit TARA", command=root.destroy)

    def show_menu(event: Any) -> None:
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    canvas.bind("<Button-3>", show_menu)
    root.bind("<Escape>", lambda _event: root.destroy())
    root.bind("<Control-q>", lambda _event: root.destroy())
    root.protocol("WM_DELETE_WINDOW", root.destroy)

    from tara_app.webapp import _Server
    server_url = validate_server_url(f"http://127.0.0.1:{port}")
    server = _Server(("127.0.0.1", port), app)
    server_thread = threading.Thread(target=server.serve_forever, name="tara-local-server", daemon=True)
    server_thread.start()

    draw_pet()
    try:
        root.mainloop()
    finally:
        try:
            server.shutdown()
        finally:
            server.server_close()
            server_thread.join(timeout=3)
