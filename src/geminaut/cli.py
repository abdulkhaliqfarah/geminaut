"""Command line interface for geminaut."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from geminaut.gemtext import extract_links, parse_gemtext
from geminaut.protocol import GeminiError, request, resolve_link

app = typer.Typer(
    name="geminaut",
    help="A terminal client for the Gemini protocol \u2014 small web, smaller footprint.",
    no_args_is_help=True,
)
console = Console()

_STYLE = {
    "heading": "bold cyan",
    "link": "blue",
    "quote": "italic yellow",
    "list": "green",
    "preformatted": "dim",
    "text": "",
}


@app.command()
def get(
    url: str = typer.Argument(..., help="A gemini:// URL to fetch."),
    max_redirects: int = typer.Option(5, help="Maximum redirects to follow."),
) -> None:
    """Fetch a Gemini URL (following redirects) and print its rendered gemtext."""
    current_url = url
    redirects = 0
    while True:
        try:
            response = request(current_url)
        except GeminiError as exc:
            console.print(f"[bold red]error:[/bold red] {exc}")
            raise typer.Exit(code=1) from exc

        if response.is_redirect:
            redirects += 1
            if redirects > max_redirects:
                console.print(f"[bold red]error:[/bold red] too many redirects starting at {url}")
                raise typer.Exit(code=1)
            current_url = resolve_link(current_url, response.meta)
            continue
        break

    if response.is_input_request:
        console.print(f"[yellow]input requested ({response.status}):[/yellow] {response.meta}")
        return
    if not response.is_success:
        console.print(f"[bold red]error {response.status}:[/bold red] {response.meta}")
        raise typer.Exit(code=1)

    lines = parse_gemtext(response.text())
    for line in lines:
        style = _STYLE.get(line.kind, "")
        prefix = {"list": "\u2022 ", "quote": "\u258e "}.get(line.kind, "")
        console.print(Text(prefix + line.text, style=style))

    links = extract_links(lines)
    if links:
        table = Table(title="Links", header_style="bold cyan")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Label")
        table.add_column("URL", style="blue", overflow="fold")
        for index, (label, target) in enumerate(links, start=1):
            table.add_row(str(index), label[:60], resolve_link(current_url, target))
        console.print(table)


@app.command()
def tui(url: str = typer.Argument(None, help="Optional starting gemini:// URL.")) -> None:
    """Launch the interactive Gemini browser."""
    from geminaut.tui import GeminautApp

    GeminautApp(start_url=url).run()


if __name__ == "__main__":
    app()
