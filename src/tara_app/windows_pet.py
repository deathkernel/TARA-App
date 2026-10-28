"""Windows-only floating companion for the existing TARA-App local server.

The pet UI is local. It sends a request only after the user submits a chat message.
It does not execute desktop actions or model-generated commands in this first slice.
"""
from __future__ import annotations

import errno
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



def _create_local_server(app: Any, port: int) -> tuple[Any, int]:
    """Bind the preferred loopback port, falling back to an OS-assigned port if busy."""
    from tara_app.webapp import _Server

    try:
        server = _Server(("127.0.0.1", port), app)
        return server, server.server_port
    except OSError as exc:
        # Windows reports WSAEADDRINUSE as winerror 10048; POSIX uses errno.EADDRINUSE.
        address_in_use = {errno.EADDRINUSE, 10048, getattr(errno, "WSAEADDRINUSE", 10048)}
        if exc.errno not in address_in_use and getattr(exc, "winerror", None) not in address_in_use:
            raise
    try:
        server = _Server(("127.0.0.1", 0), app)
    except OSError as exc:
        raise RuntimeError("TARA could not bind its local chat server. Check local network permissions and try again.") from exc
    return server, server.server_port

def _pet_window_geometry(*, expanded: bool, pet_center_x: int, top_y: int) -> str:
    """Return window geometry while keeping the pet centered at the same screen point."""
    if expanded:
        return f"390x620+{pet_center_x - 195}+{top_y}"
    return f"132x150+{pet_center_x - 66}+{top_y}"


def run_floating_pet(app: Any, *, port: int = 8765) -> None:
    """Run a Windows floating pet with its chat panel directly beneath the pet."""
    if sys.platform != "win32":
        raise RuntimeError("The floating pet is supported on Windows only.")
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
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
    panel_background = "#17171f"
    try:
        root.configure(bg=background)
        root.attributes("-transparentcolor", background)
    except tk.TclError:
        root.configure(bg=background)

    canvas = tk.Canvas(root, width=132, height=150, bg=background, highlightthickness=0, bd=0, cursor="hand2")
    canvas.pack(fill="x")
    session_id = f"windows-pet-{threading.get_ident()}"
    history: list[dict[str, str]] = []
    shutdown_event = threading.Event()
    chat_workers: set[threading.Thread] = set()
    busy = False
    expanded = False
    animation_tick = 0
    drag = {"x": 0, "y": 0, "root_x": 0, "root_y": 0, "moved": False}

    chat_panel = tk.Frame(root, bg=panel_background, width=390, height=470)
    chat_panel.pack_propagate(False)

    header = tk.Frame(chat_panel, bg="#211b2d", padx=14, pady=10)
    header.pack(fill="x")
    tk.Label(
        header, text="✦  TARA", bg="#211b2d", fg="#e5d6ff",
        font=("Segoe UI", 12, "bold"),
    ).pack(side="left")
    tk.Label(
        header, text="Chat with your AI pet", bg="#211b2d", fg="#b8afc9",
        font=("Segoe UI", 9),
    ).pack(side="left", padx=(10, 0))
    tk.Button(
        header, text="×", command=lambda: collapse_chat(), bg="#211b2d",
        fg="#d8ccef", activebackground="#332743", activeforeground="#ffffff",
        relief="flat", borderwidth=0, font=("Segoe UI", 15), padx=6,
    ).pack(side="right")

    conversation = tk.Frame(chat_panel, bg=panel_background, padx=12, pady=12)
    conversation.pack(fill="both", expand=True)
    scroll = ttk.Scrollbar(conversation)
    scroll.pack(side="right", fill="y")
    transcript = tk.Text(
        conversation, wrap="word", state="disabled", yscrollcommand=scroll.set,
        bg=panel_background, fg="#f0edf7", insertbackground="#f0edf7",
        relief="flat", padx=8, pady=8, font=("Segoe UI", 10),
        selectbackground="#59427a", borderwidth=0,
    )
    transcript.pack(side="left", fill="both", expand=True)
    scroll.configure(command=transcript.yview)
    transcript.tag_configure("user", foreground="#d9c5ff", justify="right", spacing1=8, spacing3=3)
    transcript.tag_configure("tara", foreground="#f0edf7", justify="left", spacing1=8, spacing3=3)
    transcript.tag_configure("notice", foreground="#f2c98a", justify="left", spacing1=8, spacing3=3)
    transcript.tag_configure("label", foreground="#b8a3dc", font=("Segoe UI", 8, "bold"), spacing1=5)

    composer = tk.Frame(chat_panel, bg="#211b2d", padx=12, pady=10)
    composer.pack(fill="x")
    entry = tk.Entry(
        composer, bg="#2b2935", fg="#f7f3ff", insertbackground="#f7f3ff",
        relief="flat", font=("Segoe UI", 10), borderwidth=0,
    )
    entry.pack(side="left", fill="x", expand=True, ipady=10, padx=(0, 8))
    entry.configure(disabledbackground="#2b2935", disabledforeground="#9e95ad")
    send_button = tk.Button(
        composer, text="Send", bg="#b99af7", fg="#20172e",
        activebackground="#cdb8ff", relief="flat", padx=14, pady=8,
        borderwidth=0,
    )
    send_button.pack(side="right")

    def append_transcript(speaker: str, message: str) -> None:
        transcript.configure(state="normal")
        tag = "user" if speaker == "You" else "notice" if speaker == "Notice" else "tara"
        transcript.insert("end", f"{speaker}\n", ("label",))
        transcript.insert("end", f"{message}\n\n", (tag,))
        content = transcript.get("1.0", "end-1c")
        bounded = trim_transcript_text(content)
        if bounded != content:
            transcript.delete("1.0", "end")
            transcript.insert("1.0", bounded)
        transcript.see("end")
        transcript.configure(state="disabled")

    def collapse_chat() -> None:
        nonlocal expanded
        if not expanded:
            return
        pet_center_x = root.winfo_x() + 195
        top_y = root.winfo_y()
        chat_panel.pack_forget()
        expanded = False
        canvas.configure(width=132)
        root.geometry(_pet_window_geometry(expanded=False, pet_center_x=pet_center_x, top_y=top_y))

    def open_chat() -> None:
        nonlocal expanded
        if expanded:
            entry.focus_set()
            return
        pet_center_x = root.winfo_x() + 66
        top_y = root.winfo_y()
        expanded = True
        canvas.configure(width=390)
        chat_panel.pack(fill="both", expand=True)
        root.geometry(_pet_window_geometry(expanded=True, pet_center_x=pet_center_x, top_y=top_y))
        root.lift()
        entry.focus_set()

    def send_message() -> None:
        nonlocal busy, history
        if busy:
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
        send_button.configure(state="disabled", text="Thinking…")
        entry.configure(state="disabled")

        def worker() -> None:
            nonlocal history
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
                if shutdown_event.is_set():
                    return
                busy = False
                if send_button.winfo_exists():
                    send_button.configure(state="normal", text="Send")
                if entry.winfo_exists():
                    entry.configure(state="normal")
                    entry.focus_set()
                append_transcript("TARA" if outcome[0] else "Notice", outcome[1])

            try:
                if not shutdown_event.is_set():
                    root.after(0, finish)
            except (tk.TclError, RuntimeError):
                pass
            finally:
                chat_workers.discard(threading.current_thread())

        worker_thread = threading.Thread(target=worker, name="tara-pet-chat", daemon=True)
        chat_workers.add(worker_thread)
        worker_thread.start()

    send_button.configure(command=send_message)
    entry.bind("<Return>", lambda _event: send_message())

    def draw_pet() -> None:
        nonlocal animation_tick
        try:
            canvas.delete("all")
            center_x = max(66, canvas.winfo_width() // 2)
            bob = math.sin(animation_tick * 0.65) * 2.5
            canvas.create_oval(center_x - 35, 105 + bob, center_x + 35, 121 + bob, fill="#050509", outline="")
            canvas.create_oval(center_x - 39, 32 + bob, center_x + 39, 108 + bob, fill="#6b48b7", outline="#c6a5ff", width=2)
            canvas.create_oval(center_x - 32, 38 + bob, center_x + 32, 100 + bob, fill="#9b78ed", outline="")
            canvas.create_oval(center_x - 23, 43 + bob, center_x + 7, 70 + bob, fill="#c9b5ff", outline="")
            canvas.create_oval(center_x - 17, 46 + bob, center_x - 5, 58 + bob, fill="#e7deff", outline="")
            if animation_tick % 9 == 0:
                canvas.create_line(center_x - 19, 70 + bob, center_x - 9, 70 + bob, fill="#241b3d", width=3, capstyle="round")
                canvas.create_line(center_x + 9, 70 + bob, center_x + 19, 70 + bob, fill="#241b3d", width=3, capstyle="round")
            else:
                canvas.create_oval(center_x - 19, 63 + bob, center_x - 8, 76 + bob, fill="#211637", outline="")
                canvas.create_oval(center_x + 8, 63 + bob, center_x + 19, 76 + bob, fill="#211637", outline="")
                canvas.create_oval(center_x - 16, 65 + bob, center_x - 13, 68 + bob, fill="#ffffff", outline="")
                canvas.create_oval(center_x + 11, 65 + bob, center_x + 14, 68 + bob, fill="#ffffff", outline="")
            canvas.create_oval(center_x - 29, 76 + bob, center_x - 19, 82 + bob, fill="#e8a9e7", outline="")
            canvas.create_oval(center_x + 19, 76 + bob, center_x + 29, 82 + bob, fill="#e8a9e7", outline="")
            canvas.create_arc(center_x - 7, 75 + bob, center_x + 8, 87 + bob, start=205, extent=130, style="arc", outline="#2a1742", width=2)
            canvas.create_text(center_x, 132 + bob, text="TARA", fill="#e6d8ff", font=("Segoe UI", 10, "bold"))
            if not expanded:
                canvas.create_text(center_x, 145, text="click to chat", fill="#c5b4e7", font=("Segoe UI", 7))
            animation_tick += 1
            root.after(650, draw_pet)
        except tk.TclError:
            return

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
    menu.add_command(label="Hide chat panel", command=collapse_chat)
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

    append_transcript("TARA", "Hey! I'm right here. Ask me anything below.")
    try:
        server, actual_port = _create_local_server(app, port)
    except (OSError, RuntimeError):
        root.destroy()
        raise
    server_url = validate_server_url(f"http://127.0.0.1:{actual_port}")
    if actual_port != port:
        print(
            f"TARA's preferred port {port} is busy; using http://127.0.0.1:{actual_port} instead.",
            flush=True,
        )
    server_thread = threading.Thread(target=server.serve_forever, name="tara-local-server", daemon=True)
    server_thread.start()

    draw_pet()
    try:
        root.mainloop()
    finally:
        shutdown_event.set()
        try:
            server.shutdown()
        finally:
            server.server_close()
            server_thread.join(timeout=3)
            for worker_thread in tuple(chat_workers):
                if worker_thread is not threading.current_thread():
                    worker_thread.join(timeout=0.2)
            try:
                root.destroy()
            except tk.TclError:
                pass
