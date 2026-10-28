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
    """Keep the pet centered while switching between compact and chat layouts."""
    width, height = (430, 470) if expanded else (180, 204)
    return f"{width}x{height}+{pet_center_x - width // 2}+{top_y}"


def run_floating_pet(app: Any, *, port: int = 8765) -> None:
    """Run a compact floating pet with an inline toolbar and expandable chat."""
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
    root.geometry("180x204+120+120")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    background = "#111116"
    panel_background = "#17171f"
    root.configure(bg=background)
    try:
        root.attributes("-transparentcolor", background)
    except tk.TclError:
        pass

    canvas = tk.Canvas(root, width=180, height=158, bg=background, highlightthickness=0, bd=0, cursor="hand2")
    canvas.pack(fill="x")
    session_id = f"windows-pet-{threading.get_ident()}"
    history: list[dict[str, str]] = []
    shutdown_event = threading.Event()
    chat_workers: set[threading.Thread] = set()
    busy = False
    expanded = False
    mini_mode = False
    pet_state = "ready"
    animation_tick = 0
    drag = {"x": 0, "y": 0, "root_x": 0, "root_y": 0, "moved": False}

    toolbar = tk.Frame(root, bg="#202027", padx=7, pady=5, highlightthickness=1, highlightbackground="#303039")
    toolbar.pack(fill="x", padx=8, pady=(0, 5))
    icon_button_style = {
        "bg": "#202027", "fg": "#f1eef8", "activebackground": "#383443",
        "activeforeground": "#ffffff", "relief": "flat", "borderwidth": 0,
        "font": ("Segoe UI Symbol", 12), "padx": 11, "pady": 2, "cursor": "hand2",
    }

    chat_area = tk.Frame(root, bg=panel_background, padx=10, pady=9)
    transcript = tk.Text(
        chat_area, wrap="word", state="disabled", bg=panel_background,
        fg="#f0edf7", insertbackground="#f0edf7", relief="flat",
        padx=8, pady=8, font=("Segoe UI", 10), height=10,
        selectbackground="#59427a", borderwidth=0,
    )
    transcript.pack(side="top", fill="both", expand=True)
    transcript.tag_configure("user", foreground="#d9c5ff", justify="right", spacing1=8, spacing3=3)
    transcript.tag_configure("tara", foreground="#f0edf7", justify="left", spacing1=8, spacing3=3)
    transcript.tag_configure("notice", foreground="#f2c98a", justify="left", spacing1=8, spacing3=3)
    transcript.tag_configure("label", foreground="#b8a3dc", font=("Segoe UI", 8, "bold"), spacing1=5)

    composer = tk.Frame(chat_area, bg="#292830", padx=8, pady=7, highlightthickness=1, highlightbackground="#3a3843")
    composer.pack(side="bottom", fill="x", pady=(8, 0))
    entry = tk.Entry(
        composer, bg="#292830", fg="#f7f3ff", insertbackground="#f7f3ff",
        relief="flat", font=("Segoe UI", 10), borderwidth=0,
    )
    entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(4, 8))
    entry.configure(disabledbackground="#292830", disabledforeground="#9e95ad")
    send_button = tk.Button(
        composer, text="↑", bg="#3985f6", fg="#ffffff",
        activebackground="#5a9bff", activeforeground="#ffffff",
        relief="flat", padx=10, pady=2, borderwidth=0,
        font=("Segoe UI", 13, "bold"), cursor="hand2",
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

    def set_pet_state(state: str) -> None:
        nonlocal pet_state
        pet_state = state
        colors = {"ready": "#39d98a", "thinking": "#f4b942", "needs_input": "#f4b942", "blocked": "#ff5c68", "success": "#39d98a"}
        labels = {"ready": "Ready", "thinking": "Working", "needs_input": "Needs input", "blocked": "Blocked", "success": "Task completed"}
        status_button.configure(fg=colors.get(state, "#39d98a"), text="🔔")
        status_button.configure(command=lambda: show_status())
        root.title(f"TARA Floating Pet — {labels.get(state, state.title())}")

    def show_status() -> None:
        labels = {"ready": "Ready", "thinking": "Working on your request…", "needs_input": "Needs your input", "blocked": "Blocked — check the chat for details", "success": "Task completed successfully"}
        if not expanded:
            open_chat()
        append_transcript("Notice", labels.get(pet_state, "Ready"))

    def toggle_mini_mode() -> None:
        nonlocal mini_mode, expanded
        mini_mode = not mini_mode
        if mini_mode:
            chat_area.pack_forget()
            toolbar.pack_forget()
            expanded = False
            canvas.configure(width=54, height=54)
            root.geometry(f"54x54+{root.winfo_x()}+{root.winfo_y()}")
        else:
            canvas.configure(width=180, height=158)
            toolbar.pack(fill="x", padx=8, pady=(0, 5))
            root.geometry(f"180x204+{root.winfo_x()}+{root.winfo_y()}")
        root.lift()

    def collapse_chat() -> None:
        nonlocal expanded
        if not expanded:
            return
        pet_center_x = root.winfo_x() + 215
        top_y = root.winfo_y()
        chat_area.pack_forget()
        expanded = False
        canvas.configure(width=180)
        root.geometry(_pet_window_geometry(expanded=False, pet_center_x=pet_center_x, top_y=top_y))

    def open_chat() -> None:
        nonlocal expanded
        nonlocal mini_mode
        if mini_mode:
            mini_mode = False
            canvas.configure(width=180, height=158)
            toolbar.pack(fill="x", padx=8, pady=(0, 5))
            root.geometry(f"180x204+{root.winfo_x()}+{root.winfo_y()}")
        if expanded:
            entry.focus_set()
            return
        pet_center_x = root.winfo_x() + 90
        top_y = root.winfo_y()
        expanded = True
        canvas.configure(width=430)
        chat_area.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        root.geometry(_pet_window_geometry(expanded=True, pet_center_x=pet_center_x, top_y=top_y))
        root.lift()
        entry.focus_set()

    def show_voice_notice() -> None:
        if not expanded:
            open_chat()
        append_transcript("Notice", "Voice input is not available yet. Type your message below.")

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
        set_pet_state("thinking")
        send_button.configure(state="disabled", text="…")
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
                    send_button.configure(state="normal", text="↑")
                if entry.winfo_exists():
                    entry.configure(state="normal")
                    entry.focus_set()
                append_transcript("TARA" if outcome[0] else "Notice", outcome[1])
                set_pet_state("success" if outcome[0] else "blocked")
                root.after(2400, lambda: set_pet_state("ready") if pet_state == "success" else None)

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

    compose_button = tk.Button(toolbar, text="✎", command=open_chat, **icon_button_style)
    compose_button.pack(side="left")
    tk.Frame(toolbar, bg="#3a3843", width=1, height=23).pack(side="left", padx=3)
    voice_button = tk.Button(toolbar, text="♬", command=show_voice_notice, **icon_button_style)
    voice_button.pack(side="left")
    tk.Frame(toolbar, bg="#3a3843", width=1, height=23).pack(side="left", padx=3)

    def show_menu() -> None:
        menu.tk_popup(root.winfo_x() + root.winfo_width() - 20, root.winfo_y() + 185)
        menu.grab_release()

    dropdown_button = tk.Button(toolbar, text="⌄", command=show_menu, **icon_button_style)
    dropdown_button.pack(side="left")
    status_button = tk.Button(toolbar, text="●", command=lambda: show_status(), **icon_button_style)
    status_button.pack(side="left", padx=(5, 0))

    def draw_pet() -> None:
        nonlocal animation_tick
        try:
            canvas.delete("all")
            if mini_mode:
                canvas.create_oval(7, 7, 47, 47, fill="#6b48b7", outline="#c6a5ff", width=2)
                canvas.create_text(27, 27, text="T", fill="#ffffff", font=("Segoe UI", 16, "bold"))
                bell_color = {"ready": "#39d98a", "thinking": "#f4b942", "blocked": "#ff5c68", "success": "#39d98a"}.get(pet_state, "#39d98a")
                if pet_state == "thinking" and animation_tick % 2:
                    bell_color = "#ffe4a3"
                canvas.create_oval(39, 4, 51, 16, fill=bell_color, outline="")
                animation_tick += 1
                root.after(250 if pet_state == "thinking" else 650, draw_pet)
                return
            center_x = max(90, canvas.winfo_width() // 2)
            bob = math.sin(animation_tick * (1.15 if pet_state == "thinking" else 0.65)) * (4 if pet_state == "thinking" else 2.5)
            canvas.create_oval(center_x - 35, 105 + bob, center_x + 35, 121 + bob, fill="#050509", outline="")
            canvas.create_oval(center_x - 39, 32 + bob, center_x + 39, 108 + bob, fill="#6b48b7", outline="#c6a5ff", width=2)
            canvas.create_oval(center_x - 32, 38 + bob, center_x + 32, 100 + bob, fill="#9b78ed", outline="")
            canvas.create_oval(center_x - 23, 43 + bob, center_x + 7, 70 + bob, fill="#c9b5ff", outline="")
            canvas.create_oval(center_x - 17, 46 + bob, center_x - 5, 58 + bob, fill="#e7deff", outline="")
            if pet_state == "thinking":
                canvas.create_arc(center_x - 24, 52 + bob, center_x + 24, 89 + bob, start=25, extent=290, style="arc", outline="#f4b942", width=3)
                canvas.create_text(center_x, 70 + bob, text="···", fill="#fff0c2", font=("Segoe UI", 16, "bold"))
            elif pet_state == "success":
                canvas.create_text(center_x, 56 + bob, text="✦", fill="#ffe27a", font=("Segoe UI", 17, "bold"))
                canvas.create_oval(center_x - 19, 63 + bob, center_x - 8, 76 + bob, fill="#211637", outline="")
                canvas.create_oval(center_x + 8, 63 + bob, center_x + 19, 76 + bob, fill="#211637", outline="")
            elif animation_tick % 9 == 0:
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
    menu.add_command(label="Open chat", command=open_chat)
    menu.add_command(label="Hide chat", command=collapse_chat)
    menu.add_command(label="Toggle mini mode", command=toggle_mini_mode)
    menu.add_separator()
    menu.add_command(label="Exit TARA", command=root.destroy)

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    root.bind("<Escape>", lambda _event: collapse_chat() if expanded else None)
    root.bind("<Control-space>", lambda _event: open_chat())
    root.bind("<Control-Shift-m>", lambda _event: toggle_mini_mode())

    def dismiss_chat_on_focus_loss(_event: Any) -> None:
        if not expanded:
            return
        def check_focus() -> None:
            if not expanded or shutdown_event.is_set():
                return
            try:
                focused = root.focus_get()
                if focused is None:
                    collapse_chat()
            except tk.TclError:
                pass
        try:
            root.after(180, check_focus)
        except tk.TclError:
            pass

    root.bind("<FocusOut>", dismiss_chat_on_focus_loss, add="+")
    root.bind("<Control-q>", lambda _event: root.destroy())
    root.protocol("WM_DELETE_WINDOW", root.destroy)

    append_transcript("TARA", "Hey! I'm here. What can I help with?")
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
