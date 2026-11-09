import json
from html import escape
from math import floor

from runner import LAB_ROOT, LABS


def support_data(implementation: str) -> dict:
    path = LAB_ROOT / LABS[implementation] / "support_data.json"
    return json.loads(path.read_text(encoding="utf-8"))


def ticket_choices(implementation: str) -> list[tuple[str, str]]:
    return [
        (f'{ticket_id} · {ticket["title"]}', ticket_id)
        for ticket_id, ticket in support_data(implementation)["tickets"].items()
    ]


def error_rate_chart(rates: dict[str, float], threshold: float) -> str:
    scale = (floor(max(*rates.values(), threshold) / 5) + 1) * 5
    rows = []
    for key, label in (("before", "Before release"), ("after", "After release")):
        rate = rates[key]
        rows.append(f"""
        <div class="rate-row">
          <span>{label}</span>
          <div class="rate-track" aria-hidden="true">
            <span class="rate-bar {key}" style="width: {rate / scale:.2%}"></span>
          </div>
          <strong>{rate:g}%</strong>
        </div>
        """)
    return f"""
    <figure class="ticket-chart" style="--threshold: {threshold / scale:.2%}">
      <figcaption>Checkout error rate</figcaption>
      {"".join(rows)}
      <div class="rate-row rate-scale" aria-hidden="true">
        <div><span>0%</span><span>{scale:g}%</span></div>
      </div>
      <p class="rate-legend">Runbook escalation threshold · {threshold:g}%</p>
    </figure>
    """


def log_timeline(logs: list[str]) -> str:
    outcomes = {
        "upstream_timeout": "Upstream timeout",
        "ok": "Request succeeded",
        "http_503": "HTTP 503 · Unavailable",
        "delivery_retry": "Delivery retry",
        "queue_drained": "Queue drained",
        "job_stalled": "Export job stalled",
    }
    items = []
    for line in logs:
        timestamp, zone, service, outcome, *_ = line.split()
        state = "recovered" if outcome in {"ok", "queue_drained"} else "issue"
        items.append(f"""
        <li class="{state}">
          <time>{escape(timestamp)} {escape(zone)}</time>
          <span><strong>{escape(outcomes.get(outcome, outcome.replace("_", " ").capitalize()))}</strong>
            <span class="log-service">{escape(service)}</span></span>
        </li>
        """)
    return f'<div class="ticket-timeline"><h3>Observed events</h3><ol>{"".join(items)}</ol></div>'


def ticket_overview(implementation: str, ticket_id: str) -> str:
    data = support_data(implementation)
    ticket = data["tickets"][ticket_id]
    record = ticket["record"]
    if rates := ticket.get("error_rate_pct"):
        threshold = data["runbooks"][record["runbook"]]["escalation_threshold_pct"]
        visual = error_rate_chart(rates, threshold)
    else:
        visual = log_timeline(record["logs"])
    logs = escape("\n".join(record["logs"]))
    severity = record["severity"]
    return f"""
    <section class="ticket-overview" aria-label="Ticket overview">
      <div class="ticket-heading">
        <p class="event-kicker">Support ticket #{escape(ticket_id)}</p>
        <span class="ticket-severity" data-severity="{escape(severity)}">{escape(severity.title())}</span>
      </div>
      <h2>{escape(ticket["title"])}</h2>
      <p class="ticket-summary">{escape(record["summary"])}</p>
      {visual}
      <div class="ticket-footer">
        <span>Runbook · <code>{escape(record["runbook"])}</code></span>
        <details class="ticket-logs">
          <summary>Raw log samples ({len(record["logs"])})</summary>
          <pre tabindex="0">{logs}</pre>
        </details>
      </div>
    </section>
    """
