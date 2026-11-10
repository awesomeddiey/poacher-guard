import http.server
import io
import json
import sys
import threading
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import update as U  # noqa: E402


def make_zip(files: dict[str, bytes]) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for k, v in files.items():
            z.writestr("poacher-guard-main/" + k, v)
    return b.getvalue()


class Fake:
    def __init__(self, sha, files):
        self.sha, self.zip, self.downloads = sha, make_zip(files), 0
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body = outer.sha.encode() if self.path == "/sha" else outer.zip
                if self.path == "/zip": outer.downloads += 1
                self.send_response(200); self.end_headers(); self.wfile.write(body)
            def log_message(self, *a): pass

        self.srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.api, self.url = f"http://127.0.0.1:{self.srv.server_port}/sha", f"http://127.0.0.1:{self.srv.server_port}/zip"


def run(root, fake, **kw):
    out = []
    return U.update(root, fake.api, fake.url, run_pip=False, say=out.append, **kw), "\n".join(out)


def test_update_cycle(tmp_path):
    (tmp_path / "app").mkdir(); (tmp_path / "app/x.py").write_text("old")
    (tmp_path / "config.yaml").write_text("site: old\n"); (tmp_path / "requirements.txt").write_text("a\n")
    (tmp_path / "run-poacher-guard.bat").write_bytes(b"old bat\r\n"); (tmp_path / "INSTALL.bat").write_bytes(b"old install\r\n")
    (tmp_path / "tools").mkdir(); (tmp_path / "tools/node-settings.json").write_text('{"phones": "mine"}')
    (tmp_path / ".venv").mkdir(); (tmp_path / ".venv/keep.txt").write_text("venv")
    new = {"app/x.py": b"new", "app/y.py": b"added", "config.yaml": b"site: new\n", "requirements.txt": b"a\n",
           "run-poacher-guard.bat": b"new bat\r\n", "INSTALL.bat": b"new install\r\n", "tools/node-settings.json": b"{}",
           "firmware/flame_gsm_node/flame_gsm_node.ino": b"// v2", ".venv/keep.txt": b"overwritten?"}
    fake = Fake("sha-2", new)

    status, msg = run(tmp_path, fake, skip=("run-poacher-guard.bat",))
    assert status == "updated" and fake.downloads == 1
    assert (tmp_path / "app/x.py").read_text() == "new" and (tmp_path / "app/y.py").read_text() == "added"
    assert (tmp_path / "run-poacher-guard.bat").read_bytes() == b"old bat\r\n"          # the running batch file is not touched
    assert (tmp_path / "INSTALL.bat").read_bytes() == b"new install\r\n"                # CRLF bytes kept as they are
    assert (tmp_path / "tools/node-settings.json").read_text() == '{"phones": "mine"}'  # local settings kept
    assert (tmp_path / ".venv/keep.txt").read_text() == "venv"
    assert "ESP32 node program changed" in msg                                          # sketch is new on this PC
    assert (tmp_path / "config.yaml").read_text() == "site: old\n" and (tmp_path / "config.yaml.new").exists()   # first time: kept
    assert "kept" in msg

    status, _ = run(tmp_path, fake)                                                     # same commit again: nothing to do
    assert status == "current" and fake.downloads == 1

    fake.sha, fake.zip = "sha-3", make_zip({**new, "config.yaml": b"site: newer\n"})
    (tmp_path / "config.yaml").write_text("site: old\n")                                # user's file still differs from last upstream
    status, msg = run(tmp_path, fake)
    assert status == "updated" and (tmp_path / "config.yaml").read_text() == "site: old\n" and "kept" in msg

    (tmp_path / "config.yaml").write_bytes(b"site: newer\n")                            # user never changed it: gets replaced
    fake.sha, fake.zip = "sha-4", make_zip({**new, "config.yaml": b"site: newest\n"})
    run(tmp_path, fake)
    assert (tmp_path / "config.yaml").read_text() == "site: newest\n"


def test_offline_changes_nothing(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    out = []
    assert U.update(tmp_path, "http://127.0.0.1:9/none", "http://127.0.0.1:9/none", say=out.append) == "offline"
    assert (tmp_path / "a.txt").read_text() == "x" and "skipped" in out[0]
