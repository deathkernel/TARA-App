# Windows Floating Pet — First Vertical Slice

## Scope

The Windows launcher starts TARA-App with a small native, always-on-top companion. The pet's idle animation runs locally and does not call an AI provider. Clicking the pet opens a lightweight chat window connected to TARA-App's existing loopback \`/api/chat\` endpoint.

This is the first integration slice, not the completed desktop automation engine.

## Controls

- Left-click: open or focus chat.
- Drag: move the pet.
- Right-click: open the menu.
- Escape or Ctrl+Q: exit the pet and local server.
- Close the chat window: hide the chat window; the pet remains available.

## Network and privacy boundary

- The pet starts the existing TARA HTTP server bound to \`127.0.0.1\`.
- The pet accepts only loopback HTTP origins and sends chat requests only after the user submits a message.
- Chat HTTP redirects are rejected so a local response cannot redirect prompts or history to a non-loopback destination.
- The request shape matches the existing \`/api/chat\` contract. Attachments are not sent by the pet.
- Chat history is kept in the pet process for the current run and is bounded to 20 prior messages; the visible transcript is capped at 100,000 characters.
- The pet does not execute shell commands, inspect the screen, control mouse/keyboard outside its own window, update software, terminate processes, or perform system repairs in this slice.
- If Tkinter is unavailable, the existing local web interface remains available as a fallback.

## Verification required

Run the repository CI workflow, including the redirect-boundary, malformed-payload, and transcript-bound tests, and test the Windows launcher on a real Windows machine. In particular, verify Tk transparency behavior, window dragging, taskbar/window focus behavior, clean shutdown, and that the local chat endpoint remains loopback-only. Do not mark the desktop feature as production-ready based only on unit tests.
