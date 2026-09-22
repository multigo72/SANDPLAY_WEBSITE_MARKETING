"""Static server for the SandPlay site with HTTP Range support.

Python's built-in http.server ignores Range headers, and Safari/iOS refuse to
play <video> without 206 Partial Content responses. Usage:

    python3 serve.py [port]   # default 8772, serves this folder
"""

import os
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)$")


class RangeHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        path = self.translate_path(self.path)
        range_header = self.headers.get("Range")
        if not range_header or os.path.isdir(path) or not os.path.isfile(path):
            return super().send_head()

        match = RANGE_RE.match(range_header.strip())
        size = os.path.getsize(path)
        if not match or (match.group(1) == "" and match.group(2) == ""):
            return super().send_head()

        if match.group(1) == "":  # suffix range: last N bytes
            start = max(0, size - int(match.group(2)))
            end = size - 1
        else:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else size - 1
        end = min(end, size - 1)

        if start >= size or start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None

        f = open(path, "rb")
        f.seek(start)
        self._remaining = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(self._remaining))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, "_remaining", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        self._remaining = None
        while remaining > 0:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)

    def end_headers(self):
        if self.command in ("GET", "HEAD") and "Accept-Ranges" not in self._headers_sent():
            self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def _headers_sent(self):
        return b"".join(getattr(self, "_headers_buffer", [])).decode("latin-1", "ignore")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8772
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f"Serving SandPlay site on http://localhost:{port}/", flush=True)
    ThreadingHTTPServer(("", port), RangeHandler).serve_forever()
