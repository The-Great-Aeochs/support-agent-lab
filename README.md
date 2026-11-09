# Support Agent Lab

Run the same support triage agent in plain Python and in LangGraph. Both versions read a sample ticket and its runbook through a local MCP server, then either report what they found or propose an escalation for you to review. The browser UI shows each model request, tool call, result, and approval decision.

Start with the command-line demo in step 3 if you want to try the lab without an OpenAI account. Go to step 4 to run the browser UI with your own OpenAI API key. If you're using a coding assistant to set up the project, give it [CODING_AGENT_HANDOFF.txt](CODING_AGENT_HANDOFF.txt).

## 1. Download the lab

On the repository page, click **Code**, then **Download ZIP**. Extract the ZIP and open the extracted folder in Cursor, VS Code, or your file browser. In Cursor or VS Code, choose **Terminal → New Terminal**. Otherwise, open Terminal on macOS or Linux, or PowerShell on Windows, and navigate to the extracted folder with `cd`.

If you already use Git, you can clone the repository instead.

```sh
git clone https://github.com/The-Great-Aeochs/support-agent-lab.git
cd support-agent-lab
```

Run the commands below from the folder that contains this README. To check, run `ls` on macOS/Linux or `Get-ChildItem` in PowerShell. You should see `plain_python`, `langgraph_version`, and `gradio_ui`.

## 2. Install Python and the lab packages

Install [Python 3.13 or 3.12](https://www.python.org/downloads/). Reopen your terminal after installation so it can find Python. Follow the commands for your operating system, one line at a time. The first setup creates a folder called `.venv`, an isolated Python environment for this lab. The install step downloads the packages used by both implementations and the UI.

### macOS and Linux

```sh
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r gradio_ui/requirements.txt
```

If the version check prints a different Python version, use `python3.13` or `python3.12` for the first two commands after installing that version. When you open a new terminal for the lab, run `source .venv/bin/activate` again from the project folder. Most terminals show `(.venv)` in the prompt when it's active.

### Windows PowerShell

```powershell
py -3.13 --version
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r gradio_ui/requirements.txt
```

If you installed Python 3.12, use `-3.12` instead of `-3.13`. These instructions call the virtual environment's Python directly, so you can keep using the same commands in a new PowerShell window.

## 3. Run both implementations without an API key

The default command-line demo uses a scripted model so the same input gives the same sequence of tool calls. It still starts the local MCP server and reads the bundled sample ticket and runbook. Start with ticket 43, which has a successful retry.

**macOS and Linux**

```sh
python plain_python/main.py --ticket 43
python langgraph_version/main.py --ticket 43
```

**Windows PowerShell**

```powershell
.\.venv\Scripts\python.exe plain_python/main.py --ticket 43
.\.venv\Scripts\python.exe langgraph_version/main.py --ticket 43
```

Both should show calls to `get_ticket` and `get_runbook` and finish with **No escalation needed.** Next, try ticket 42. At the approval prompt, type `n` to decline, or `y` to record a demo escalation. The server keeps it in memory for that run.

To see how the agent reached its decision, run one of these commands and open the resulting HTML file in your browser.

**macOS and Linux**

```sh
python plain_python/main.py --ticket 42 --context-chars 100 --trace trace-python.html
python langgraph_version/main.py --ticket 42 --context-chars 100 --trace trace-langgraph.html
```

**Windows PowerShell**

```powershell
.\.venv\Scripts\python.exe plain_python/main.py --ticket 42 --context-chars 100 --trace trace-python.html
.\.venv\Scripts\python.exe langgraph_version/main.py --ticket 42 --context-chars 100 --trace trace-langgraph.html
```

The small context budget makes it easy to see which facts survive when the raw tool results are shortened. You can also download and open the [sample trace](trace-demo.html) without running Python.

## 4. Start the browser UI with OpenAI

Create an [OpenAI API key](https://platform.openai.com/api-keys) for an API project with model access. The UI makes live API requests, which may incur usage charges. Paste your key only into the hidden terminal prompt shown below. Keep it out of source files, Git commits, and messages to a coding assistant.

Run the commands in the same terminal. They set the key for that terminal session and start the local server.

**macOS and Linux**

```sh
printf 'Paste your OpenAI API key, then press Enter: '
read -rs OPENAI_API_KEY
printf '\n'
export OPENAI_API_KEY
python gradio_ui/app.py
```

**Windows PowerShell**

```powershell
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'Paste your OpenAI API key' -AsSecureString)).Password
.\.venv\Scripts\python.exe gradio_ui/app.py
```

Keep the terminal open and visit [http://127.0.0.1:7860/](http://127.0.0.1:7860/) in a browser. If the terminal prints a different local URL, open that one. Press **Ctrl+C** in the terminal when you're done. The default model is `gpt-4.1-mini`. If your API project uses a different compatible model, set `OPENAI_MODEL` in the same terminal before starting the app.

You can also use the live model in either command-line implementation. After setting the key, add `--live` to one of the step 3 commands.

## 5. Try the UI

1. **Architecture** shows how a request moves between Gradio, the model, and MCP. It also shows where a human decision can pause the run.
2. **Investigate** lets you select either workflow and a ticket. Start with **#43**, then try **#42** to see the approval panel. Under **Trace explorer**, use **Stage** to switch between Model, MCP, Context, and Approval. Open **Full request body** in a Model event to inspect the instructions, inputs, and tool schemas.
3. **Compare** runs both workflows with the same ticket and context budget. It shows time to result, token usage, and differences in model and tool outputs. Each run stops at an answer or an approval proposal.

| Ticket | What it demonstrates |
| --- | --- |
| **42 · Checkout incident** | A sustained spike that can be escalated to `payments-oncall` after approval |
| **43 · Recovered timeout** | A successful retry and a triage answer without escalation |
| **44 · Checkout at the threshold** | Exactly 5%, when the runbook calls for escalation above 5% |
| **45 · Multi-region auth outage** | A different runbook and escalation team, `platform-oncall` |
| **46 · Webhook queue recovered** | Recovery after the queue drains |
| **47 · Missing export runbook** | An MCP error and a triage answer explaining what is missing |

The tickets and runbooks are bundled fixtures. Live model wording and tool choices can vary. Use the scripted command-line demo if you want to reproduce a particular path in class.

## Where to look in the code

| Question | Files to open |
| --- | --- |
| How does the agent decide what happens next? | [Plain Python loop](plain_python/workflow.py) and [LangGraph nodes and edges](langgraph_version/workflow.py) |
| What do we send to OpenAI? | [Model request and response](plain_python/models.py) |
| Where does an MCP tool call go? | [MCP client](plain_python/tools.py) and [local MCP server](plain_python/support_server.py) |
| What happens when context gets too large? | [State and context compaction](plain_python/state.py) |
| What can the model propose, and what needs my approval? | [Tool handling and approval](plain_python/steps.py) and [LangGraph pause and resume](langgraph_version/main.py) |
| How do traces reach the browser? | [Event recorder](plain_python/trace_report.py), [worker](gradio_ui/worker.py), and [UI runner](gradio_ui/runner.py) |

To run the offline checks for both workflows and all six tickets, use `python eval_workflows.py` on macOS/Linux or `.\.venv\Scripts\python.exe eval_workflows.py` in PowerShell. The run should finish with `OK`.

## Common setup problems

- **Python command not found.** Install Python and reopen your terminal. On Windows, if `py` is unavailable but `python --version` reports 3.12 or 3.13, use `python -m venv .venv`.
- **Can't find a file such as `gradio_ui/app.py`.** Open a terminal in the extracted repository folder. Check that it contains all three project folders.
- **No module named `mcp`, `langgraph`, or `gradio`.** Repeat the package install with the same virtual environment Python you use to run the lab.
- **Run investigation is disabled.** Stop the server with **Ctrl+C**, set the API key in that terminal, and start it again.
- **OpenAI returns an error.** Check the key, the API project's model access, and its usage limits. The offline demo in step 3 is available while you troubleshoot.
