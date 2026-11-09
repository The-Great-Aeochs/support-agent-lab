from mcp.server.fastmcp import FastMCP

from support_fixtures import RUNBOOKS, TICKETS

server = FastMCP("support-desk", log_level="WARNING")

ESCALATIONS: dict[str, dict[str, str]] = {}


@server.tool()
def get_ticket(ticket_id: str) -> dict[str, str]:
    """Read a support ticket, including its incident summary and logs."""
    if ticket_id not in TICKETS:
        raise ValueError(f"Unknown ticket #{ticket_id}")
    record = TICKETS[ticket_id]["record"]
    return {**record, "logs": "\n".join(record["logs"])}


@server.tool()
def get_runbook(slug: str) -> dict[str, str]:
    """Read the runbook named by the ticket."""
    if slug not in RUNBOOKS:
        raise ValueError(f"Unknown runbook {slug}")
    return RUNBOOKS[slug]["record"]


@server.tool()
def escalate_ticket(ticket_id: str, team: str, reason: str) -> dict[str, str]:
    """Record an escalation in the demo server's memory."""
    if ticket_id not in TICKETS:
        raise ValueError(f"Unknown ticket #{ticket_id}")
    action = {"ticket_id": ticket_id, "team": team, "reason": reason}
    if ESCALATIONS.setdefault(ticket_id, action) != action:
        raise ValueError(f"Ticket #{ticket_id} already has a different escalation")
    return {"escalation_id": f"ESC-{ticket_id}"}


if __name__ == "__main__":
    server.run(transport="stdio")
