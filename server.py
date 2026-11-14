#!/usr/bin/env python3
"""Bible Display Pro local server. Python standard library only."""
import http.server, socketserver, threading, json, os, sys, webbrowser, time, hashlib, urllib.parse
from pathlib import Path

BASE = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = int(os.environ.get("BIBLE_DISPLAY_PORT", "8765"))
CLIENTS = set()
CLIENTS_LOCK = threading.Lock()
STATE = {"live": None, "updated": 0}

def load_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

def ws_frame(payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    n = len(data)
    if n < 126:
        head = bytes([0x81, n])
    elif n < 65536:
        head = bytes([0x81, 126]) + n.to_bytes(2, "big")
    else:
        head = bytes([0x81, 127]) + n.to_bytes(8, "big")
    return head + data

def broadcast(message):
    packet = ws_frame(message)
    dead = []
    with CLIENTS_LOCK:
        clients = list(CLIENTS)
    for sock in clients:
        try:
            sock.sendall(packet)
        except Exception:
            dead.append(sock)
    if dead:
        with CLIENTS_LOCK:
            for sock in dead:
                CLIENTS.discard(sock)

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE), **kwargs)

    def log_message(self, fmt, *args):
        print("[HTTP]", fmt % args)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/bible":
            # Serve the existing JSON bytes directly. Parsing and re-serializing
            # a large KJV database on every request can make the controller look
            # stuck at "Loading scripture database" on slower computers.
            bible_path = BASE / "data" / "kjv.json"
            try:
                if not bible_path.is_file():
                    body = json.dumps({"error":"KJV database is missing","expected":"data/kjv.json","help":"Copy your existing KJV database here or run setup_kjv.py with internet access."}).encode("utf-8")
                    self.send_response(503)
                    self.send_header("Content-Type","application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control","no-store")
                    self.end_headers(); self.wfile.write(body)
                    print(f"[BIBLE] Missing database: {bible_path}")
                    return
                body = bible_path.read_bytes()
                if not body.strip():
                    raise ValueError("database file is empty")
            except (OSError, ValueError) as exc:
                print(f"[BIBLE] Could not read {bible_path}: {exc}")
                body = json.dumps({"error":"KJV database could not be read","detail":str(exc)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control","no-store")
                self.end_headers(); self.wfile.write(body)
                return
            self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control","no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
                print(f"[BIBLE] Served database: {len(body):,} bytes")
            except (ConnectionError, OSError) as exc:
                print(f"[BIBLE] Client disconnected while receiving database: {exc}")
            return
        if parsed.path == "/api/state":
            body = json.dumps(STATE, ensure_ascii=False).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control","no-store")
            self.end_headers(); self.wfile.write(body); return
        if parsed.path == "/api/health":
            bible_path = BASE / "data" / "kjv.json"
            body = json.dumps({"server":"ok","database_exists":bible_path.is_file(),"database_bytes":bible_path.stat().st_size if bible_path.is_file() else 0,"port":PORT}).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control","no-store")
            self.end_headers(); self.wfile.write(body); return
        if parsed.path == "/ws":
            key = self.headers.get("Sec-WebSocket-Key")
            if not key:
                self.send_error(400, "WebSocket key missing"); return
            import base64
            accept = base64.b64encode(hashlib.sha1((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
            self.send_response(101, "Switching Protocols")
            self.send_header("Upgrade","websocket"); self.send_header("Connection","Upgrade")
            self.send_header("Sec-WebSocket-Accept",accept); self.end_headers()
            sock = self.connection
            with CLIENTS_LOCK: CLIENTS.add(sock)
            try:
                sock.sendall(ws_frame({"type":"state","state":STATE}))
                while True:
                    first = sock.recv(2)
                    if not first: break
                    opcode = first[0] & 0x0F
                    masked = first[1] & 0x80
                    length = first[1] & 0x7F
                    if length == 126: length = int.from_bytes(sock.recv(2),"big")
                    elif length == 127: length = int.from_bytes(sock.recv(8),"big")
                    mask = sock.recv(4) if masked else b""
                    payload = b""
                    while len(payload) < length:
                        chunk = sock.recv(length-len(payload))
                        if not chunk: break
                        payload += chunk
                    if opcode == 8: break
                    if opcode == 9:
                        try: sock.sendall(bytes([0x8A, len(payload)])+payload)
                        except Exception: pass
                        continue
                    if not payload: continue
                    if masked: payload = bytes(b ^ mask[i%4] for i,b in enumerate(payload))
                    try: msg = json.loads(payload.decode("utf-8"))
                    except Exception: continue
                    if msg.get("type") == "live":
                        STATE["live"] = msg.get("verse")
                        STATE["updated"] = time.time()
                        broadcast({"type":"live","verse":STATE["live"],"updated":STATE["updated"]})
                    elif msg.get("type") == "clear":
                        STATE["live"] = None; STATE["updated"] = time.time()
                        broadcast({"type":"live","verse":None,"updated":STATE["updated"]})
                    elif msg.get("type") == "settings":
                        save_json(BASE/"settings.json", msg.get("settings",{}))
                    elif msg.get("type") == "queue":
                        broadcast(msg)
            except (ConnectionError, OSError):
                pass
            finally:
                with CLIENTS_LOCK: CLIENTS.discard(sock)
            return
        return super().do_GET()

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:"+str(PORT))
        super().end_headers()

class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def main():
    print("="*58)
    print(" BIBLE DISPLAY PRO — local offline presentation server")
    print(" Controller: http://127.0.0.1:%d/index.html" % PORT)
    print(" OBS output: http://127.0.0.1:%d/output.html" % PORT)
    print(" Keep this window open while presenting.")
    bible_path = BASE / "data" / "kjv.json"
    if bible_path.is_file():
        print(" KJV database: present (%s bytes)" % format(bible_path.stat().st_size, ","))
    else:
        print(" WARNING: data/kjv.json is missing; the controller will explain how to fix it.")
    print(" Health check: http://127.0.0.1:%d/api/health" % PORT)
    print("="*58)
    try:
        server = ThreadedServer((HOST, PORT), Handler)
    except OSError as exc:
        print("Could not start server on port %d: %s" % (PORT, exc))
        input("Press Enter to close..."); return
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\\nShutting down...")
        server.shutdown()

if __name__ == "__main__":
    main()
