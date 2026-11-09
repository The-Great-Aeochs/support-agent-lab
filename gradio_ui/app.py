import asyncio
import os
from pathlib import Path

import gradio as gr

from architecture_view import ARCHITECTURE
from comparison_view import build_compare_tab
from runner import LABS, LabRun
from ticket_view import ticket_choices, ticket_overview
from view import EMPTY_TRACE, STAGES, event_detail, proposal, select_events, status

APPROVAL_TIMEOUT = 600


def build_app() -> gr.Blocks:
    runs: dict[str, LabRun] = {}
    live_available = bool(os.getenv("OPENAI_API_KEY"))
    default_workflow = "Plain Python"
    default_ticket = "42"

    def update(run: LabRun, stage: str) -> tuple:
        events = run.events.copy()
        picker, detail = select_events(events, stage, prefer_model=run.phase == "approval")
        can_start = run.phase in {"complete", "error"}
        return (
            events,
            picker,
            detail,
            status(run.phase, run.message),
            gr.update(interactive=live_available and can_start),
            gr.update(visible=run.phase == "approval"),
            proposal(run.pending),
            gr.update(interactive=run.phase != "running"),
            gr.update(interactive=can_start),
            gr.update(interactive=can_start),
        )

    async def release(session: str, run: LabRun) -> None:
        if runs.get(session) is run:
            del runs[session]
        await run.close()

    async def expire(session: str, run: LabRun) -> None:
        await asyncio.sleep(APPROVAL_TIMEOUT)
        if runs.get(session) is run and run.phase == "approval":
            await release(session, run)

    async def stream(run: LabRun, stage: str):
        try:
            async for _ in run.read():
                yield update(run, stage)
        except (OSError, ValueError, TimeoutError):
            run.fail("The connection to the lab worker ended.")
            yield update(run, stage)

    async def start(implementation, ticket, budget, stage, request: gr.Request):
        if not live_available:
            raise gr.Error("Set OPENAI_API_KEY before starting the Gradio server.")
        session = request.session_hash
        if not session or session in runs:
            raise gr.Error("Finish the current run before starting another.")
        run = LabRun()
        runs[session] = run
        handed_off = False
        try:
            yield update(run, stage)
            await run.start(implementation, ticket, int(budget), live=True)
            async for result in stream(run, stage):
                if run.phase == "approval":
                    run.expiry = asyncio.create_task(expire(session, run))
                    handed_off = True
                yield result
        except OSError:
            run.fail("Could not start the lab worker.")
            yield update(run, stage)
        finally:
            if not handed_off:
                await release(session, run)

    def decision(approved: bool):
        async def resume(stage, events, request: gr.Request):
            session = request.session_hash
            run = runs.get(session)
            if run is None:
                expired = LabRun(events=events)
                expired.fail("This run has ended. Start a fresh run to review another action.")
                yield update(expired, stage)
                return
            if run.phase != "approval":
                return
            try:
                await run.decide(approved)
                yield update(run, stage)
                async for result in stream(run, stage):
                    yield result
            except OSError:
                run.fail("The lab worker ended before it could resume.")
                yield update(run, stage)
            finally:
                await release(session, run)

        return resume

    with gr.Blocks(title="Support Agent Lab", analytics_enabled=False) as app:
        events = gr.State([])
        gr.HTML("""
        <header class="lab-header">
          <p class="lab-eyebrow">AI SYSTEM DESIGN · WEEK 01</p>
          <h1>Support Agent Lab</h1>
          <p>Run the same agent in Python or LangGraph and follow every model and tool decision.</p>
        </header>
        """)
        with gr.Tabs(overflow_behavior="wrap"):
            with gr.Tab("Investigate"):
                with gr.Row(equal_height=False, elem_id="lab-layout"):
                    with gr.Column(scale=1, min_width=280, elem_classes=["lab-panel", "controls"]):
                        gr.Markdown("## Run controls")
                        implementation = gr.Radio(list(LABS), value=default_workflow, label="Workflow")
                        ticket = gr.Dropdown(
                            ticket_choices(default_workflow),
                            value=default_ticket,
                            label="Support ticket",
                            interactive=True,
                        )
                        gr.Markdown("**Model** · OpenAI")
                        budget = gr.Slider(
                            minimum=100, maximum=3200, step=50, value=1700, label="Raw context budget (chars)"
                        )
                        run_button = gr.Button(
                            "Run investigation", variant="primary", interactive=live_available
                        )
                        initial_status = (
                            status("ready", "Choose a workflow and run the investigation.")
                            if live_available
                            else status("setup", "Set OPENAI_API_KEY before starting the Gradio server.")
                        )
                        run_status = gr.HTML(initial_status)
                        with gr.Group(visible=False, elem_classes=["approval-panel"]) as approval:
                            gr.Markdown("### Review escalation")
                            action = gr.HTML()
                            with gr.Row():
                                approve = gr.Button("Approve", variant="primary")
                                decline = gr.Button("Decline", variant="secondary")
                    with gr.Column(scale=3, min_width=360, elem_classes=["lab-detail-column"]):
                        with gr.Column(elem_classes=["lab-panel", "ticket-panel"]):
                            overview = gr.HTML(ticket_overview(default_workflow, default_ticket))
                        with gr.Column(elem_classes=["lab-panel", "explorer"]):
                            gr.Markdown("## Trace explorer")
                            gr.Markdown("Filter by stage, then select an event to inspect its payload.")
                            with gr.Row():
                                stage = gr.Dropdown(STAGES, value="All", label="Stage", interactive=True, scale=1)
                                event = gr.Dropdown(
                                    choices=[],
                                    label="Trace event",
                                    interactive=True,
                                    scale=3,
                                    type="value",
                                )
                            detail = gr.HTML(EMPTY_TRACE)
            with gr.Tab("Compare"):
                build_compare_tab(live_available, default_workflow, default_ticket)
            with gr.Tab("Architecture"):
                with gr.Column(elem_classes=["lab-panel"]):
                    gr.HTML(ARCHITECTURE)
        outputs = [
            events, event, detail, run_status, run_button, approval, action, stage,
            implementation, ticket,
        ]
        gr.on(
            [implementation.input, ticket.input],
            ticket_overview,
            [implementation, ticket],
            overview,
            queue=False,
            show_progress="hidden",
            trigger_mode="always_last",
        )
        run_button.click(
            start,
            [implementation, ticket, budget, stage],
            outputs,
            concurrency_limit=None,
            api_name="run_investigation",
        )
        approve.click(decision(True), [stage, events], outputs, api_name="approve_escalation")
        decline.click(decision(False), [stage, events], outputs, api_name="decline_escalation")
        stage.input(select_events, [events, stage], [event, detail], queue=False)
        event.input(event_detail, [events, event], detail, queue=False)
    return app


def main() -> None:
    palette = {
        "body_background_fill": "#f5efe5",
        "body_text_color": "#342820",
        "body_text_color_subdued": "#685547",
        "background_fill_primary": "#fffaf2",
        "background_fill_secondary": "#f3e9db",
        "border_color_primary": "#d8c9b8",
        "block_background_fill": "#fffaf2",
        "block_label_text_color": "#685547",
        "block_title_text_color": "#685547",
        "input_background_fill": "#fffdf8",
        "checkbox_background_color": "#fffdf8",
        "checkbox_background_color_selected": "#76523b",
        "button_primary_background_fill": "#76523b",
        "button_primary_background_fill_hover": "#61412e",
        "button_primary_text_color": "#fffaf2",
        "button_secondary_background_fill": "#eee2d2",
        "button_secondary_background_fill_hover": "#e5d6c4",
        "button_secondary_text_color": "#342820",
        "button_secondary_text_color_hover": "#342820",
    }
    theme = gr.themes.Base(
        primary_hue=gr.themes.colors.stone,
        neutral_hue=gr.themes.colors.stone,
        font=["system-ui", "sans-serif"],
        font_mono=["ui-monospace", "monospace"],
    ).set(**palette, **{f"{name}_dark": color for name, color in palette.items()})
    build_app().launch(
        server_name="127.0.0.1",
        share=False,
        ssr_mode=False,
        theme=theme,
        css=Path(__file__).with_name("style.css").read_text(encoding="utf-8"),
        footer_links=[],
    )


if __name__ == "__main__":
    main()
