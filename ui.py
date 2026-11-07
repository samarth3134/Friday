import html

import brain
import dashboard
import voice


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

* {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

.gradio-container {
    background: #0a0e14 !important;
    color: #e0e0e0 !important;
}

/* Tabs */
.tabs {
    border: none !important;
}
.tab-nav {
    background: #131820 !important;
    border: 1px solid #1e293b !important;
    border-radius: 12px !important;
    padding: 4px !important;
    gap: 4px !important;
}
.tab-nav button {
    background: transparent !important;
    border: none !important;
    color: #64748b !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    padding: 8px 20px !important;
    border-radius: 8px !important;
    transition: all 0.2s !important;
}
.tab-nav button.selected {
    background: #1e293b !important;
    color: #f59e0b !important;
}
.tab-nav button:hover {
    color: #f59e0b !important;
}

/* Headers */
h1 {
    color: #f59e0b !important;
    font-weight: 700 !important;
    font-size: 28px !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    text-align: center !important;
    padding: 16px 0 8px !important;
    border-bottom: 1px solid #1e293b !important;
    margin-bottom: 16px !important;
}

/* Chat */
.chatbot {
    border: 1px solid #1e293b !important;
    border-radius: 12px !important;
    background: #0d1117 !important;
    overflow-y: auto !important;
}
.chatbot .message {
    border-radius: 12px !important;
    padding: 12px 16px !important;
    margin: 4px 0 !important;
}
.chatbot .user {
    background: #1e293b !important;
    color: #e0e0e0 !important;
    border: 1px solid #334155 !important;
}
.chatbot .assistant {
    background: #131820 !important;
    color: #f59e0b !important;
    border: 1px solid #f59e0b33 !important;
}

/* Text input */
textarea {
    background: #131820 !important;
    border: 1px solid #1e293b !important;
    border-radius: 10px !important;
    color: #e0e0e0 !important;
    font-size: 14px !important;
    padding: 12px !important;
    resize: none !important;
}
textarea:focus {
    border-color: #f59e0b !important;
    box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.15) !important;
    outline: none !important;
}

/* Buttons */
button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 8px 20px !important;
    transition: all 0.2s !important;
    border: 1px solid #1e293b !important;
    background: #1e293b !important;
    color: #e0e0e0 !important;
}
button:hover {
    background: #334155 !important;
    border-color: #f59e0b !important;
    color: #f59e0b !important;
}
button.primary {
    background: #f59e0b !important;
    color: #0a0e14 !important;
    border-color: #f59e0b !important;
}
button.primary:hover {
    background: #fbbf24 !important;
}

/* Dashboard HUD */
.hud-panel {
    border: 1px solid #1e293b;
    background: #0d1117;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
}

.hud-title {
    color: #f59e0b;
    font-size: 16px;
    font-weight: 600;
    letter-spacing: 1.5px;
    margin-bottom: 16px;
    text-transform: uppercase;
}

.hud-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 10px;
}

.hud-card {
    border-left: 3px solid #f59e0b;
    background: rgba(245, 158, 11, 0.04);
    padding: 10px 14px;
    border-radius: 0 8px 8px 0;
    min-height: 60px;
}

.hud-label {
    color: #94a3b8;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 4px;
    font-weight: 600;
}

.hud-value {
    color: #e0e0e0;
    font-size: 13px;
    line-height: 1.5;
    white-space: pre-wrap;
}

/* State indicator */
.state-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
    padding-bottom: 16px;
    border-bottom: 1px solid #1e293b;
}

.pulse-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #f59e0b;
    box-shadow: 0 0 0 rgba(245, 158, 11, 0.7);
    animation: pulse 1.5s infinite;
}

@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.6); }
    70% { box-shadow: 0 0 0 10px rgba(245, 158, 11, 0); }
    100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
}

/* Labels */
.markdown small {
    color: #64748b !important;
    font-size: 11px !important;
}
"""


def _escape(value):
    return html.escape(str(value))


def _format_status():
    status = dashboard.get_status()
    memories = status.get("recent_memory_snippets") or []
    memory_text = "\n".join(f"- {_escape(item)}" for item in memories) or "No recent memory yet."

    cards = [
        ("Time", f"{status['current_time']}\n{status['date']}"),
        ("Weather", status["weather"]),
        ("Tasks Today", status["todays_tasks"]),
        ("Calendar Today", status["todays_calendar_events"]),
        ("Unread Email", status["unread_email_count"]),
        ("Unread WhatsApp", status["unread_whatsapp_count"]),
        ("Now Playing", status["now_playing"]),
        ("Recent Memory", memory_text),
    ]

    card_html = "\n".join(
        f"""
        <div class="hud-card">
            <div class="hud-label">{_escape(label)}</div>
            <div class="hud-value">{value if label == "Recent Memory" else _escape(value)}</div>
        </div>
        """
        for label, value in cards
    )

    return f"""
    <div class="hud-panel">
        <div class="hud-title">FRIDAY STATUS</div>
        <div class="state-row">
            <span class="pulse-dot"></span>
            <span>STATE: {_escape(status.get("friday_state", "idle")).upper()}</span>
        </div>
        <div class="hud-grid">{card_html}</div>
    </div>
    """


def _append_response(history, user_text):
    history = history or []
    if not user_text or not str(user_text).strip():
        return history, "", "Handled by: none"

    message = str(user_text).strip()
    intent = brain.classify_intent(message)
    response = brain.process(message)
    response_with_label = f"{response}\n\n<small>Handled by: {intent}</small>"

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": response_with_label})
    return history, "", f"Handled by: {intent}"


def _mic_response(history):
    heard = voice.listen()
    if not heard:
        return history or [], "", "Could not hear a command. Check your microphone and connection, then try again."

    return _append_response(history, heard)


def build_app():
    import gradio as gr

    with gr.Blocks() as app:
        gr.Markdown("# FRIDAY")

        with gr.Tab("Dashboard"):
            status_panel = gr.HTML(_format_status())
            timer = gr.Timer(1)
            timer.tick(fn=_format_status, outputs=status_panel)
            refresh = gr.Button("Refresh")
            refresh.click(fn=_format_status, outputs=status_panel)

        with gr.Tab("Chat"):
            state_indicator = gr.HTML('<div style="font-size:16px;font-weight:600;padding:10px 14px;border:1px solid #334155;border-radius:10px;background:#131820;color:#64748b;">⚪ STATE: IDLE</div>')
            chatbot = gr.Chatbot(height=440, label="Friday Chat")
            module_label = gr.Markdown("Handled by: none")
            with gr.Row():
                text_input = gr.Textbox(
                    show_label=False,
                    placeholder="Ask Friday...",
                    scale=8,
                    lines=3,
                )
                submit = gr.Button("Submit", scale=1)
                mic = gr.Button("Mic", scale=1)

            _last_voice_version = 0

            def _chat_tick(history):
                nonlocal _last_voice_version
                import wakeword

                s = getattr(wakeword, "STATE", "idle").upper()
                dots = {"IDLE": "⚪", "LISTENING": "🟢", "THINKING": "🔵", "SPEAKING": "🟠"}
                color = {"IDLE": "#888", "LISTENING": "#4caf50", "THINKING": "#2196f3", "SPEAKING": "#ff9800"}
                dot = dots.get(s, "⚪")
                c = color.get(s, "#888")
                state_html = f'<div style="font-size:16px;font-weight:600;padding:10px 14px;border:1px solid {c};border-radius:10px;background:#131820;color:{c};">{dot} STATE: {s}</div>'

                ver = getattr(wakeword, "_voice_version", 0)
                if ver > _last_voice_version:
                    _last_voice_version = ver
                    cmd = getattr(wakeword, "_voice_command", None)
                    resp = getattr(wakeword, "_voice_response", None)
                    if cmd and resp:
                        history = history or []
                        intent = brain.classify_intent(cmd)
                        response_with_label = f"{resp}\n\n<small>Handled by: {intent}</small>"
                        history.append({"role": "user", "content": cmd})
                        history.append({"role": "assistant", "content": response_with_label})

                return history, state_html

            chat_timer = gr.Timer(0.5)
            chat_timer.tick(fn=_chat_tick, inputs=[chatbot], outputs=[chatbot, state_indicator])

            submit.click(
                fn=_append_response,
                inputs=[chatbot, text_input],
                outputs=[chatbot, text_input, module_label],
            )
            text_input.submit(
                fn=_append_response,
                inputs=[chatbot, text_input],
                outputs=[chatbot, text_input, module_label],
            )
            mic.click(
                fn=_mic_response,
                inputs=[chatbot],
                outputs=[chatbot, text_input, module_label],
            )

    original_launch = app.launch

    def launch_with_hud(*args, **kwargs):
        kwargs.setdefault("css", CSS)
        kwargs.setdefault("theme", gr.themes.Base())
        return original_launch(*args, **kwargs)

    app.launch = launch_with_hud
    return app


if __name__ == "__main__":
    build_app().launch()
