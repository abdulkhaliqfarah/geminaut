"""Interactive terminal browser UI for the Gemini protocol, built with Textual."""

from __future__ import annotations

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from geminaut.gemtext import GemtextLine, extract_links, parse_gemtext
from geminaut.protocol import GeminiError, request, resolve_link

MAX_REDIRECTS = 5


class LinkItem(ListItem):
    """A single navigable link entry in the link list."""

    def __init__(self, index: int, label: str, url: str) -> None:
        super().__init__(Label(f"[dim]{index:>3}.[/dim] {label}  [blue]{url}[/blue]"))
        self.url = url


class GeminautApp(App[None]):
    """A terminal browser for gemini:// capsules."""

    CSS = """
    #address { dock: top; height: 3; }
    #body { height: 1fr; }
    #content { width: 2fr; border: round $primary; padding: 0 2; }
    #links { width: 1fr; border: round $secondary; }
    """

    BINDINGS = [
        Binding("o", "focus_address", "Open URL"),
        Binding("b", "go_back", "Back"),
        Binding("f", "go_forward", "Forward"),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("g", "scroll_home", "Top", show=False),
        Binding("G", "scroll_end", "Bottom", show=False),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, start_url: str | None = None) -> None:
        super().__init__()
        self._start_url = start_url
        self._history: list[tuple[str, list[GemtextLine]]] = []
        self._position = -1

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Input(placeholder="Enter a gemini:// URL and press Enter\u2026", id="address")
        with Horizontal(id="body"):
            with Vertical(id="content"):
                yield Static("Press [b]o[/b] to open a gemini:// URL.", id="page")
            yield ListView(id="links")
        yield Footer()

    def on_mount(self) -> None:
        if self._start_url:
            self.fetch(self._start_url)
        else:
            self.query_one("#address", Input).focus()

    def action_focus_address(self) -> None:
        self.query_one("#address", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.value.strip():
            self.fetch(event.value.strip())

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, LinkItem):
            self.fetch(event.item.url)

    def fetch(self, url: str) -> None:
        if not url.startswith("gemini://"):
            url = f"gemini://{url}"
        self.sub_title = f"Loading {url}\u2026"
        self._load(url)

    @work(exclusive=True, thread=True)
    def _load(self, url: str) -> None:
        current_url = url
        redirects = 0
        while True:
            try:
                response = request(current_url)
            except GeminiError as exc:
                self.call_from_thread(self._on_error, str(exc))
                return

            if response.is_redirect:
                redirects += 1
                if redirects > MAX_REDIRECTS:
                    self.call_from_thread(
                        self._on_error, f"Too many redirects starting at {url}"
                    )
                    return
                current_url = resolve_link(current_url, response.meta)
                continue

            if not response.is_success:
                self.call_from_thread(
                    self._on_error,
                    f"{current_url} responded with status {response.status}: {response.meta}",
                )
                return

            lines = parse_gemtext(response.text())
            self.call_from_thread(self._on_loaded, current_url, lines)
            return

    def _on_error(self, message: str) -> None:
        self.sub_title = f"error: {message}"

    def _on_loaded(self, url: str, lines: list[GemtextLine]) -> None:
        del self._history[self._position + 1 :]
        self._history.append((url, lines))
        self._position = len(self._history) - 1
        self._render(url, lines)

    def _render(self, url: str, lines: list[GemtextLine]) -> None:
        self.title = url
        self.sub_title = url
        rendered = []
        for line in lines:
            prefix = {"list": "\u2022 ", "quote": "\u258e ", "heading": "\u258c "}.get(
                line.kind, ""
            )
            rendered.append(prefix + line.text)
        self.query_one("#page", Static).update("\n".join(rendered))

        link_list = self.query_one("#links", ListView)
        link_list.clear()
        for index, (label, target) in enumerate(extract_links(lines), start=1):
            link_list.append(LinkItem(index, label, resolve_link(url, target)))
        self.query_one("#address", Input).value = url

    def action_go_back(self) -> None:
        if self._position > 0:
            self._position -= 1
            self._render(*self._history[self._position])

    def action_go_forward(self) -> None:
        if self._position < len(self._history) - 1:
            self._position += 1
            self._render(*self._history[self._position])

    def action_scroll_down(self) -> None:
        self.query_one("#content").scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#content").scroll_up()

    def action_scroll_home(self) -> None:
        self.query_one("#content").scroll_home(animate=False)

    def action_scroll_end(self) -> None:
        self.query_one("#content").scroll_end(animate=False)
