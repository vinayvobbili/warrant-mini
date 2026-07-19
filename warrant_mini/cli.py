"""warrant-mini command-line interface.

    warrant-mini check <text | file.txt | https://url>   # rich report
    warrant-mini check <src> --json                       # machine-readable
    warrant-mini rules                                    # list the rule library
"""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import checker
from .input_loader import load_input
from .models import ReviewResult
from .rules import load_rules

app = typer.Typer(add_completion=False, help="A miniature AI marketing-compliance checker.")
console = Console()
err = Console(stderr=True)

_SEVERITY_STYLE = {"P1": "bold white on red", "P2": "bold red", "P3": "yellow", "P4": "cyan"}
_SEVERITY_LABEL = {
    "P1": "P1 · critical",
    "P2": "P2 · high",
    "P3": "P3 · moderate",
    "P4": "P4 · review suggested",
}


def _load_dotenv() -> None:
    """Best-effort load of ANTHROPIC_API_KEY from a local .env (no extra dep)."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip("'\""))


def _render(result: ReviewResult) -> None:
    counts = result.counts
    total = len(result.findings)

    summary = Text()
    summary.append(f"{result.source}", style="dim")
    summary.append(f"   ·   {result.char_count} chars   ·   model {result.model}\n", style="dim")
    if total == 0:
        summary.append("No compliance issues found against the rule library.", style="bold green")
    else:
        summary.append(f"{total} finding(s):  ", style="bold")
        for sev in ("P1", "P2", "P3", "P4"):
            if counts[sev]:
                summary.append(f" {counts[sev]}×", style=_SEVERITY_STYLE[sev])
                summary.append(f"{sev} ", style="dim")
    console.print(Panel(summary, title="warrant-mini review", border_style="blue"))

    for i, f in enumerate(result.findings, 1):
        style = _SEVERITY_STYLE[f.severity]
        body = Text()
        body.append("regulation  ", style="dim")
        body.append(f"{f.regulation}\n")
        body.append("offending   ", style="dim")
        body.append(f"“{f.quote}”\n", style="italic")
        body.append("why         ", style="dim")
        body.append(f"{f.reasoning}\n")
        body.append("fix         ", style="dim")
        body.append(f"{f.suggested_rewrite}", style="green")

        title = Text()
        title.append(f" {_SEVERITY_LABEL[f.severity]} ", style=style)
        title.append(f"  {f.rule_name}", style="bold")
        console.print(Panel(body, title=title, title_align="left", border_style=style.split()[-1]))


@app.command()
def check(
    src: str = typer.Argument(..., help="Marketing copy: literal text, a .txt/.md path, or a URL."),
    json_out: bool = typer.Option(False, "--json", help="Emit findings as JSON instead of a report."),
    model: str = typer.Option(checker.DEFAULT_MODEL, "--model", help="Anthropic model id."),
) -> None:
    """Review marketing copy against the compliance rule library."""
    _load_dotenv()
    try:
        loaded = load_input(src)
    except Exception as exc:  # noqa: BLE001 — surface any load error cleanly to the user
        err.print(f"[bold red]Could not load input:[/] {exc}")
        raise typer.Exit(code=2)

    try:
        result = checker.review(loaded.text, source=loaded.source_label, model=model)
    except checker.MissingAPIKey as exc:
        err.print(f"[bold red]{exc}[/]")
        raise typer.Exit(code=3)
    except Exception as exc:  # noqa: BLE001
        err.print(f"[bold red]Review failed:[/] {exc}")
        raise typer.Exit(code=1)

    if json_out:
        console.print_json(result.model_dump_json(indent=2))
    else:
        _render(result)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(8000, help="Bind port."),
) -> None:
    """Launch the single-page web UI (textarea + results panel)."""
    _load_dotenv()  # so the server process inherits the key from .env
    import uvicorn

    console.print(f"[bold]warrant-mini[/] web UI → [cyan]http://{host}:{port}[/]")
    uvicorn.run("warrant_mini.web:app", host=host, port=port)


@app.command()
def rules() -> None:
    """List the compliance rules warrant-mini checks against."""
    table = Table(title="warrant-mini rule library", show_lines=False, border_style="blue")
    table.add_column("id", style="cyan", no_wrap=True)
    table.add_column("group", style="magenta")
    table.add_column("default", justify="center")
    table.add_column("regulation")
    for r in load_rules():
        table.add_row(r.id, r.group.value, r.severity_default, r.regulation)
    console.print(table)


if __name__ == "__main__":
    app()
