# geminaut 🚀

*A terminal navigator for [Gemini](https://geminiprotocol.net/) capsules — the small web, browsed properly.*

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Gemini is a lightweight, privacy-respecting internet protocol: TLS-only, one
request per connection, no cookies, no JavaScript, no tracking — just
hypertext documents ("gemtext") called **capsules**. `geminaut` is a
from-scratch terminal client for it: a plain `socket`/`ssl` implementation of
the protocol, a gemtext parser, and both a one-shot CLI and an interactive TUI.

## Why this exists

Every general-purpose "AI-native" or "decentralized" browser trending lately
is chasing the big, complicated web. Gemini is the opposite bet — a protocol
simple enough that a client fits in a few hundred lines and still does the
whole spec justice, including the part everyone skips: certificate handling.

## Security note: TLS without a CA, done deliberately

Gemini servers use self-signed certificates by design — there's no CA
authority model. `geminaut` implements **TOFU (Trust On First Use)**, the same
approach SSH uses for host keys: the first time you visit a capsule, its
certificate fingerprint is stored in `~/.config/geminaut/known_hosts`. If a
later visit presents a *different* fingerprint for the same host, `geminaut`
refuses the connection instead of silently accepting whatever certificate
shows up (which is what simply disabling verification would do).

## Install

```bash
git clone https://github.com/abdulkhaliqfarah/geminaut.git
cd geminaut
uv venv && source .venv/bin/activate
uv pip install -e .
```

## Usage

```bash
geminaut get gemini://geminiprotocol.net/     # one-shot fetch + render
geminaut tui                                  # interactive browser
geminaut tui gemini://geminiprotocol.net/     # ...starting on a page
```

Keybindings in the TUI: `o` open URL · `b` back · `f` forward · `j`/`k` scroll
· `g`/`G` top/bottom · `q` quit. Select a link in the right-hand panel and
press Enter to follow it. Redirects are followed automatically (up to 5 hops).

## How it works

1. **`protocol.py`** — opens a TLS socket to port 1965, sends the one-line
   request, reads the `<status> <meta>` header, and enforces TOFU certificate
   pinning before ever touching the body.
2. **`gemtext.py`** — parses the tiny gemtext line format (`=>` links, `#`
   headings, `*` lists, `>` quotes, ` ``` ` preformatted blocks) into
   structured lines.
3. **`cli.py` / `tui.py`** — render those lines as `rich` text on the command
   line, or as a scrollable `textual` app with a live link list.

## Development

```bash
uv pip install -e ".[dev]"
pytest
ruff check .
```

## License

MIT © Abdulkhaliq Farah — see [LICENSE](LICENSE).
