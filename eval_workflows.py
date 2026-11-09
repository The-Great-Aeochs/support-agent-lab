import unittest

from gradio_ui.runner import LABS, LabRun

READS = ["get_ticket", "get_runbook"]


def sections(run: LabRun, label: str) -> list:
    return [event["sections"][label] for event in run.events if label in event["sections"]]


def mcp_requests(run: LabRun) -> list[dict]:
    return [
        request["params"] for request in sections(run, "MCP request method and params")
    ]


async def collect(run: LabRun) -> None:
    async for _ in run.read():
        pass


class WorkflowEval(unittest.IsolatedAsyncioTestCase):
    async def start(self, workflow: str, ticket_id: str) -> LabRun:
        run = LabRun()
        self.addAsyncCleanup(run.close)
        await run.start(workflow, ticket_id, budget=100, live=False)
        await collect(run)
        return run

    async def test_critical_ticket_sequence_and_approval(self) -> None:
        cases = [
            ("42", "checkout-errors", "payments-oncall"),
            ("45", "auth-availability", "platform-oncall"),
        ]
        for workflow in LABS:
            for ticket, runbook, team in cases:
                for approved in (False, True):
                    with self.subTest(workflow=workflow, ticket=ticket, approved=approved):
                        await self.check_escalation(workflow, ticket, runbook, team, approved)

    async def check_escalation(
        self, workflow: str, ticket: str, runbook: str, team: str, approved: bool
    ) -> None:
        run = await self.start(workflow, ticket)
        self.assertEqual(run.phase, "approval", run.message)
        self.assertIsNotNone(run.pending)
        pending = run.pending.copy()
        self.assertEqual(pending["ticket_id"], ticket)
        self.assertEqual(pending["team"], team)

        model_tools = [call["name"] for call in sections(run, "Function call")]
        self.assertEqual(model_tools, [*READS, "propose_escalation"])
        reads = mcp_requests(run)
        self.assertEqual(reads, [
            {"name": "get_ticket", "arguments": {"ticket_id": ticket}},
            {"name": "get_runbook", "arguments": {"slug": runbook}},
        ])

        compacted = sections(run, "After · raw exchanges and compacted facts")[-1]
        self.assertEqual(compacted["history"], [])
        self.assertEqual(set(compacted["summaries"]), set(READS))
        pinned = sections(run, "Pinned application state")[-1]
        self.assertEqual(pinned, {"ticket_id": ticket, "pending": pending, "approved": None})

        await run.decide(approved)
        await collect(run)
        self.assertEqual(run.phase, "complete", run.message)
        self.assertEqual(sections(run, "Decision and reviewed action"), [
            {"approved": approved, "action": pending}
        ])
        if approved:
            self.assertEqual(mcp_requests(run), [
                *reads, {"name": "escalate_ticket", "arguments": pending}
            ])
            self.assertIn(f"Created ESC-{ticket}", run.message)
        else:
            self.assertEqual(mcp_requests(run), reads)
            self.assertIn("Escalation declined", run.message)

    async def test_non_escalation_paths(self) -> None:
        cases = [
            ("43", "checkout-errors", "No escalation needed."),
            ("44", "checkout-errors", "No escalation needed."),
            ("46", "webhook-delivery", "No escalation needed."),
            ("47", "export-stalls", "Unknown runbook export-stalls"),
        ]
        for workflow in LABS:
            for ticket, runbook, answer in cases:
                with self.subTest(workflow=workflow, ticket=ticket):
                    run = await self.start(workflow, ticket)
                    self.assertEqual(run.phase, "complete", run.message)
                    self.assertIsNone(run.pending)
                    self.assertEqual(mcp_requests(run), [
                        {"name": "get_ticket", "arguments": {"ticket_id": ticket}},
                        {"name": "get_runbook", "arguments": {"slug": runbook}},
                    ])
                    self.assertEqual(
                        [call["name"] for call in sections(run, "Function call")], READS
                    )
                    self.assertIn(answer, run.message)
                    self.assertEqual(sections(run, "MCP result")[-1]["isError"], ticket == "47")


if __name__ == "__main__":
    unittest.main(verbosity=2)
