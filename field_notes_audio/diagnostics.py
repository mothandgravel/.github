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


# Statuses after which Google may have processed (and billed) the request although no
# result was saved. 499 is Google's CANCELLED; AIP-194 says not to retry it automatically.
UNCERTAIN_HTTP = frozenset({408, 429, 499})

_MEANINGS = {
    400: "the service rejected the request as invalid",
    401: "the sign-in was not accepted",
    403: "the project, API, billing or permissions refused the request",
    404: "the service or resource was not found",
    408: "the service gave up waiting for the request",
    429: "the service refused the request for quota or capacity reasons",
    499: "the request was cancelled before a result came back, status CANCELLED",
    500: "the service failed on its side",
    502: "a Google gateway got no valid answer from the service",
    503: "the service was unavailable",
    504: "a Google gateway timed out waiting for the service",
}


def http_uncertain(code: int, provider_status: str = "") -> bool:
    """True when the request may have been processed and billed without a saved result."""
    return code in UNCERTAIN_HTTP or 500 <= code <= 599 or provider_status == "CANCELLED"


def http_meaning(code: int, provider_status: str = "") -> str:
    if provider_status == "CANCELLED" or code == 499:
        return _MEANINGS[499]
    if code in _MEANINGS:
        return _MEANINGS[code]
    if 500 <= code <= 599:
        return _MEANINGS[500]
    return "the service returned an unexpected response"


def stop_and_wait(code: int | None, provider_status: str = "", *, retry: str) -> str:
    """Plain next step for an uncertain paid failure. Never an instruction to loop.

    ``retry`` names the deliberate one-off action, e.g. the CLI flag or Studio control.
    """
    cause = ""
    if code == 429:
        cause = "Check the quota page in the Cloud console; repeating will not add quota. "
    elif code == 499 or provider_status == "CANCELLED":
        cause = (
            "Google advises not retrying a cancelled request automatically. Check whether a "
            "network change, sleep, proxy or another tool ended the connection. "
        )
    elif code is not None and 500 <= code <= 599:
        cause = "This is a fault on Google's side; resending will not fix it. "
    elif code is None:
        cause = "A longer wait is not a known remedy. "
    return (
        "Billing unknown: Google may have processed and charged this attempt. "
        "Stop here and do not repeat the command in a loop or from a script. "
        + cause
        + "Wait at least 30 minutes, check https://status.cloud.google.com and the billing "
        f"report, then, only if you accept another possible charge, {retry} once by hand."
    )
