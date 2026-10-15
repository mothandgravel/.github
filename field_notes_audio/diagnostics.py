"""Bounded, inert provider-error text extraction. Never persist headers or raw HTML."""

import re
from html import unescape
from html.parser import HTMLParser


class _ErrorText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template", "svg", "noscript"}:
            self.hidden.append(tag)

    def handle_endtag(self, tag):
        if tag in self.hidden:
            self.hidden = self.hidden[: self.hidden.index(tag)]

    def handle_data(self, text):
        if not self.hidden:
            self.parts.append(text)


def provider_text(raw: str, token: str = "") -> str:
    """Strip non-text payloads before truncating, then redact recognized secrets.

    The caller already bounds HTTP bodies to 8192 bytes. Also bound this entry
    point so malformed or separately supplied diagnostics cannot grow the parser.
    Unclosed script/style content stays hidden. No markup is evaluated or fetched.
    """
    raw = raw[:8192]
    if token:
        raw = raw.replace(token, "[redacted]")
    parser = _ErrorText()
    parser.feed(raw)
    parser.close()
    text = " ".join(parser.parts)
    # Encoded values can become visible only after the inert HTML parse.
    if token:
        text = text.replace(unescape(token), "[redacted]")
    text = re.sub(r"(?i)Bearer\s+\S+", "Bearer [redacted]", text)
    text = re.sub(
        r"""(?ix)(access_token|refresh_token|api_key|authorization)
            ["']?\s*[:=]\s*(?:"[^"]*"|'[^']*'|[^\s,;&]+)""",
        r"\1=[redacted]",
        text,
    )
    return re.sub(r"\s+", " ", text).strip()[:500]
