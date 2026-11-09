import json
from difflib import unified_diff
from html import escape
from itertools import zip_longest

import gradio as gr

from comparison import RunResult, run_until_review
from runner import LABS
from ticket_view import ticket_choices
from view import proposal, status


def metric_total(run: RunResult, section: str, field: str) -> float | int | None:
    values = [entry.get(field) for entry in run.sections(section)]
    if values and all(value is not None for value in values):
        return sum(values)
    return None


def measurements(run: RunResult) -> list[float | int | None]:
    return [
        run.elapsed_ms,
        metric_total(run, "Model metrics", "elapsed_ms"),
        metric_total(run, "MCP metrics", "elapsed_ms"),
        len(run.sections("Full request body")),
        len(run.tool_exchanges()),
        metric_total(run, "Model metrics", "input_tokens"),
        metric_total(run, "Model metrics", "output_tokens"),
    ]


def performance_table(left: RunResult, right: RunResult) -> str:
    labels = (
        "Time to result (ms)", "OpenAI wait (ms)", "MCP wait (ms)",
        "Model requests", "MCP calls", "Input tokens", "Output tokens",
    )
    rows = []
    for index, (label, first, second) in enumerate(
        zip(labels, measurements(left), measurements(right), strict=True)
    ):
        digits = 1 if index < 3 else 0
        first_text = f"{first:,.{digits}f}" if first is not None else "—"
        second_text = f"{second:,.{digits}f}" if second is not None else "—"
        delta = f"{second - first:+,.{digits}f}" if first is not None and second is not None else "—"
        rows.append(
            f'<tr><th scope="row">{label}</th><td>{first_text}</td>'
            f'<td>{second_text}</td><td>{delta}</td></tr>'
        )
    return f"""
    <div class="compare-table" tabindex="0">
      <table>
        <caption>Performance</caption>
        <thead><tr><th scope="col">Metric</th><th scope="col">Plain Python</th>
          <th scope="col">LangGraph</th><th scope="col">Difference</th></tr></thead>
        <tbody>{"".join(rows)}</tbody>
      </table>
    </div>
    <p class="compare-note">Difference is LangGraph minus Plain Python.
      Runs are measured sequentially, from worker launch to an answer or approval.
      Wait times and token totals cover completed calls. OpenAI latency varies between runs.</p>
    """


def outcome(run: RunResult) -> str:
    if run.phase == "approval":
        text = "<strong>Escalation proposed</strong>" + proposal(run.pending)
    elif run.phase == "error":
        text = f"<strong>Run stopped</strong><p>{escape(run.message)}</p>"
    else:
        text = f"<strong>Answer returned</strong><p>{escape(run.message)}</p>"
    return f'<div class="compare-side"><h4>{escape(run.workflow)}</h4>{text}</div>'


def payload_text(payload: object) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)


def payload_diff(first: str, second: str) -> str:
    lines = unified_diff(
        first.splitlines(), second.splitlines(), fromfile="Plain Python", tofile="LangGraph",
        lineterm="",
    )
    colored = []
    for line in lines:
        change = {"+": "added", "-": "removed"}.get(line[:1], "unchanged")
        colored.append(f'<span class="{change}">{escape(line)}</span>')
    return '<details class="compare-diff"><summary>Show diff</summary><pre tabindex="0">' + "\n".join(
        colored
    ) + "</pre></details>"


def compare_payloads(title: str, unit: str, left: list, right: list) -> str:
    entries = []
    for index, (first, second) in enumerate(zip_longest(left, right), 1):
        same = first == second
        badge = "Match" if same else "Different"
        state = "match" if same else "different"
        a, b = payload_text(first), payload_text(second)
        a_display = escape(a) if first is not None else "No output at this step."
        b_display = escape(b) if second is not None else "No output at this step."
        diff = "" if same else payload_diff(a, b)
        entry_label = f"{unit} {index}"
        if unit == "Call":
            names = [
                payload["request"]["params"]["name"]
                for payload in (first, second)
                if payload is not None
            ]
            entry_label += " · " + " / ".join(dict.fromkeys(names))
        entries.append(f"""
        <details class="compare-entry">
          <summary>{escape(entry_label)} <span class="compare-badge {state}">{badge}</span></summary>
          <div class="compare-grid">
            <div class="compare-side"><h4>Plain Python</h4><pre tabindex="0">{a_display}</pre></div>
            <div class="compare-side"><h4>LangGraph</h4><pre tabindex="0">{b_display}</pre></div>
          </div>
          {diff}
        </details>
        """)
    body = "".join(entries) if entries else "<p>Neither run returned an output in this section.</p>"
    return f'<section class="compare-section"><h3>{escape(title)}</h3>{body}</section>'


def comparison_report(ticket: str, budget: int, left: RunResult, right: RunResult) -> str:
    return f"""
    <section class="comparison-report" aria-label="Workflow comparison">
      <h2>Ticket #{escape(ticket)} comparison</h2>
      <p class="compare-note">Shared context budget · {budget:,} characters</p>
      {performance_table(left, right)}
      <section class="compare-section">
        <h3>Run outcomes</h3>
        <div class="compare-grid">{outcome(left)}{outcome(right)}</div>
      </section>
      {compare_payloads("MCP calls and results", "Call", left.tool_exchanges(), right.tool_exchanges())}
      {compare_payloads("Model outputs", "Turn", left.model_outputs(), right.model_outputs())}
      <p class="compare-note">Model outputs are aligned by turn. Generated IDs are omitted from the diff.</p>
    </section>
    """


def build_compare_tab(live_available: bool, default_workflow: str, default_ticket: str) -> None:
    async def compare(ticket_id: str, context_chars: float):
        if not live_available:
            raise gr.Error("Set OPENAI_API_KEY before starting the Gradio server.")
        budget = int(context_chars)
        results = []
        for workflow in LABS:
            yield gr.update(interactive=False), status("running", f"Running {workflow}…"), ""
            results.append(await run_until_review(workflow, ticket_id, budget))
        failed = any(result.phase == "error" for result in results)
        message = (
            "A workflow stopped early. See its outcome below."
            if failed else "Both workflows reached an answer or the approval step."
        )
        yield (
            gr.update(interactive=True),
            status("error" if failed else "complete", message),
            comparison_report(ticket_id, budget, *results),
        )

    with gr.Column(elem_classes=["lab-panel", "compare-panel"]):
        gr.Markdown("## Compare workflows")
        gr.Markdown(
            "Run both workflows with the same ticket and context budget. "
            "Comparisons end at an answer or the approval step."
        )
        with gr.Row():
            ticket = gr.Dropdown(
                ticket_choices(default_workflow), value=default_ticket,
                label="Comparison ticket", interactive=True,
            )
            budget = gr.Slider(100, 3200, step=50, value=1700, label="Comparison budget (chars)")
        run_button = gr.Button(
            "Compare both workflows", variant="primary", interactive=live_available
        )
        initial_status = (
            status("ready", "Choose a ticket and run both workflows.")
            if live_available
            else status("setup", "Set OPENAI_API_KEY before starting the Gradio server.")
        )
        run_status = gr.HTML(initial_status)
        report = gr.HTML()
    run_button.click(compare, [ticket, budget], [run_button, run_status, report], api_name="compare")
