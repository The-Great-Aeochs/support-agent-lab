ARCHITECTURE = """
<section class="lab-architecture" aria-labelledby="architecture-title">
  <p class="event-kicker">System walkthrough</p>
  <h2 id="architecture-title">How an investigation runs</h2>
  <p>One agent, two ways to coordinate its steps. Follow the request, the tool loop, and the approval boundary.</p>

  <figure class="architecture-diagram" aria-label="Support agent request and response flow">
    <ol class="architecture-start" aria-label="Request path">
      <li>
        <h3>1 · Gradio UI</h3>
        <p>Choose a ticket, workflow, and raw context budget.</p>
      </li>
      <li>
        <h3>2 · Workflow worker</h3>
        <p>Start a separate worker with the ticket ID and run state.</p>
      </li>
      <li>
        <h3>3 · OpenAI model</h3>
        <p>Send instructions, the user message, tool schemas, and any retained or compacted tool data.</p>
      </li>
    </ol>

    <p class="architecture-fork">Model response routes to one of three paths</p>
    <ul class="architecture-branches" aria-label="Model response paths">
      <li>
        <h3>Final answer</h3>
        <p>Return triage to Gradio and end the run. The worker also enforces a model turn limit.</p>
      </li>
      <li class="architecture-read">
        <h3>Read via MCP</h3>
        <p><code>get_ticket</code> and <code>get_runbook</code> read fixtures from a local server over stdio.</p>
        <p class="architecture-edge">Result → history → compact if over budget → back to the model</p>
      </li>
      <li class="architecture-approval">
        <h3>Propose an escalation</h3>
        <p><code>propose_escalation</code> stores the action locally and pauses for review in Gradio.</p>
        <p class="architecture-edge">Approve → MCP <code>escalate_ticket</code> → result<br>Decline → end without a write</p>
      </li>
    </ul>
    <figcaption>In Investigate, use the Model, MCP, Context, and Approval filters to inspect the payloads at each step.</figcaption>
  </figure>

  <h3>How the two workflows pause and resume</h3>
  <div class="architecture-workflows">
    <div>
      <h4>Plain Python</h4>
      <p>A loop runs the steps and returns pending state. The worker passes that state and your decision to <code>resume()</code>.</p>
    </div>
    <div>
      <h4>LangGraph</h4>
      <p>Nodes and edges run the steps. <code>interrupt()</code> pauses at an in-memory checkpoint, then <code>Command(resume=…)</code> continues to resolution.</p>
    </div>
  </div>
</section>
"""
