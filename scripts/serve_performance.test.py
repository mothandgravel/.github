"""The lab changes transport bytes, never the source served to the browser."""
from functools import partial
import gzip
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from serve_performance import PerformanceHandler, accepts_gzip


class TransportTest(unittest.TestCase):
    def test_negotiation(self):
        for header in ("gzip", "br, gzip;q=0.8", "*;q=0.5"):
            self.assertTrue(accepts_gzip(header))
        for header in ("", "br", "gzip;q=0", "gzip;q=0, *;q=1", "gzip;q=bad"):
            self.assertFalse(accepts_gzip(header))

    def test_served_bytes(self):
        class QuietHandler(PerformanceHandler):
            def log_message(self, *_args):
                pass

        with TemporaryDirectory() as directory:
            root = Path(directory)
            original = ("<h1>Two shores. Different knowledge.</h1>" * 100).encode()
            (root / "index.html").write_bytes(original)
            (root / "model.mjs").write_bytes(b"export const source = 'unchanged';")
            (root / "capture.png").write_bytes(b"\x89PNG\r\n\x1a\nbinary")
            server = ThreadingHTTPServer(("127.0.0.1", 0),
                                         partial(QuietHandler, directory=directory))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()

            def request(path, encoding, method="GET"):
                connection = HTTPConnection(*server.server_address)
                try:
                    connection.request(method, path, headers={"Accept-Encoding": encoding})
                    response = connection.getresponse()
                    return response.status, dict(response.getheaders()), response.read()
                finally:
                    connection.close()

            try:
                status, headers, encoded = request("/", "gzip")
                self.assertEqual(status, 200)
                self.assertEqual(headers["Content-Encoding"], "gzip")
                self.assertEqual(headers["Vary"], "Accept-Encoding")
                self.assertEqual(int(headers["Content-Length"]), len(encoded))
                self.assertLess(len(encoded), len(original))
                self.assertEqual(gzip.decompress(encoded), original)
                self.assertEqual(request("/", "gzip", "HEAD")[2], b"")
                self.assertEqual(request("/", "gzip", "HEAD")[1]["Content-Length"], str(len(encoded)))
                for encoding in ("identity", "gzip;q=0"):
                    _, headers, body = request("/", encoding)
                    self.assertNotIn("Content-Encoding", headers)
                    self.assertEqual(body, original)
                _, headers, body = request("/model.mjs", "gzip")
                self.assertEqual(headers["Content-Type"], "text/javascript")
                self.assertEqual(gzip.decompress(body), (root / "model.mjs").read_bytes())
                _, headers, body = request("/capture.png", "gzip")
                self.assertNotIn("Content-Encoding", headers)
                self.assertEqual(body, (root / "capture.png").read_bytes())
                self.assertEqual(request("/missing.html", "gzip")[0], 404)
                self.assertEqual((root / "index.html").read_bytes(), original)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()
