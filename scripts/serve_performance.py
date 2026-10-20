#!/usr/bin/env python3
"""Loopback-only static lab server with the public site's gzip text transport."""
import argparse
import gzip
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit


def accepts_gzip(header):
    weights = {}
    for entry in header.lower().split(","):
        coding, *params = entry.strip().split(";")
        weight = 1.0
        for param in params:
            key, _, value = param.strip().partition("=")
            if key == "q":
                try:
                    weight = float(value)
                except ValueError:
                    weight = 0
        weights[coding] = weight if 0 <= weight <= 1 else 0
    return weights.get("gzip", weights.get("*", 0)) > 0


class PerformanceHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".mjs": "text/javascript",
    }
    text_suffixes = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".svg", ".xml", ".txt"}

    def end_headers(self):
        self.send_header("Vary", "Accept-Encoding")
        super().end_headers()

    def send_head(self):
        path = Path(self.translate_path(self.path))
        if path.is_dir():
            # Preserve the standard server's trailing-slash redirect.
            if not urlsplit(self.path).path.endswith("/"):
                return super().send_head()
            path = next((path / name for name in ("index.html", "index.htm")
                         if (path / name).is_file()), path)
        if (path.suffix.lower() not in self.text_suffixes or not path.is_file()
                or not accepts_gzip(self.headers.get("Accept-Encoding", ""))):
            return super().send_head()
        try:
            with path.open("rb") as source:
                body = gzip.compress(source.read(), compresslevel=6, mtime=0)
        except OSError:
            return super().send_head()
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        return BytesIO(body)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", type=int)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not directory.is_dir():
        parser.error("--directory must exist")
    from functools import partial
    with ThreadingHTTPServer(("127.0.0.1", args.port),
                             partial(PerformanceHandler, directory=str(directory))) as server:
        server.serve_forever()
