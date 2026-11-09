import json
from copy import deepcopy
from collections.abc import Callable
from dataclasses import dataclass
from html import escape
from pathlib import Path
from types import TracebackType
from typing import Self


@dataclass(frozen=True)
class TraceEvent:
    kind: str
    title: str
    sections: dict[str, object]


class Trace:
    def __init__(
        self,
        path: Path | None = None,
        *,
        sink: Callable[[TraceEvent], None] | None = None,
    ) -> None:
        self.path = path
        self.sink = sink
        self.events: list[TraceEvent] = []

    @property
    def enabled(self) -> bool:
        return self.path is not None or self.sink is not None

    def record(self, kind: str, title: str, sections: dict[str, object]) -> None:
        if not self.enabled:
            return
        event = TraceEvent(kind, title, deepcopy(sections))
        if self.path is not None:
            self.events.append(event)
        if self.sink is not None:
            self.sink(event)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self.record("Run", "Run interrupted", {"Exception type": exc_type.__name__})
        self.write()

    def write(self) -> None:
        if self.path is not None:
            self.path.write_text(render_report(self.events), encoding="utf-8")
            print(f"\nTrace report → {self.path.resolve()}")


def render_section(label: str, value: object) -> str:
    content = value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False)
    return (
        f'<details class="section"><summary>{escape(label)}</summary>'
        f'<pre tabindex="0">{escape(content)}</pre></details>'
    )


def render_event(number: int, event: TraceEvent) -> str:
    sections = "".join(render_section(label, value) for label, value in event.sections.items())
    opened = " open" if number == 1 else ""
    return f"""
    <details class="event {escape(event.kind.lower())}"{opened}>
      <summary><span class="number">{number:02}</span>
        <span class="kind">{escape(event.kind)}</span>
        <span>{escape(event.title)}</span></summary>
      <div class="sections">{sections}</div>
    </details>"""


def render_report(events: list[TraceEvent]) -> str:
    timeline = "\n".join(render_event(index, event) for index, event in enumerate(events, 1))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Support agent trace</title>
  <style>{STYLES}</style>
</head>
<body>
  <main>
    <header>
      <p class="eyebrow">AI System Design · Week 1</p>
      <h1>Support agent trace</h1>
      <p>Follow each model turn from assembled input to tool dispatch, result, and context update.</p>
      <p class="hint">Open an event, then expand a section to inspect its payload.</p>
    </header>
    <section aria-label="Trace timeline">{timeline}</section>
  </main>
</body>
</html>
"""


STYLES = """
:root {
  color-scheme: light;
  font-family: system-ui, sans-serif;
  color: #182732;
  background: #f3f6f8;
}
* { box-sizing: border-box; }
main { max-width: 68rem; margin: auto; padding: 2rem clamp(1rem, 4vw, 3rem) 4rem; }
header {
  border-top: .3rem solid #14816e;
  padding: 1.5rem 0;
  margin-bottom: .75rem;
}
.eyebrow { color: #137060; font-size: .85rem; font-weight: 700; letter-spacing: .05em; }
h1 { margin: .35rem 0; font-size: clamp(2rem, 5vw, 3rem); line-height: 1.1; }
header p { margin: .65rem 0; }
.hint { color: #4a5d6b; font-size: .9rem; }
.event {
  background: #fff;
  border: 1px solid #cfd9df;
  border-left: .25rem solid var(--accent, #718491);
  border-radius: .45rem;
  margin: .55rem 0;
}
.model { --accent: #5056a8; }
.mcp { --accent: #137060; }
.context { --accent: #8f5309; }
.approval { --accent: #9e3e67; }
summary { cursor: pointer; }
summary:focus-visible { outline: 2px solid #137060; outline-offset: 3px; }
.event > summary { padding: .85rem 1rem; font-weight: 650; }
.number, .kind {
  display: inline-block;
  font-size: .75rem;
  font-weight: 700;
  margin-right: .45rem;
}
.number { color: #4a5d6b; font-variant-numeric: tabular-nums; }
.kind {
  color: var(--accent, #4a5d6b);
  min-width: 4.5rem;
}
.sections { padding: 0 1rem .9rem; }
.section { border-top: 1px solid #e1e8ec; padding: .55rem .15rem; }
.section > summary { color: #314655; font-size: .9rem; font-weight: 600; }
@media (min-width: 48rem) {
  .context .sections {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    column-gap: 1rem;
    align-items: start;
  }
  .context .section:first-child, .context .section:last-child { grid-column: 1 / -1; }
}
pre {
  background: #142532;
  color: #e9f1f4;
  border-radius: .35rem;
  padding: .85rem;
  margin: .55rem 0 0;
  max-height: 28rem;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: .85rem;
  line-height: 1.5;
}
"""
