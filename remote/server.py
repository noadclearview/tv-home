#!/usr/bin/env python3
"""Phone remote for a Sony Bravia TV (e.g. KD-65X8500C).

Run this on any computer on the same Wi-Fi as the TV, then open the printed
address on your phone. No installs needed: Python 3 standard library only.

    python3 server.py --tv 192.168.1.115 --psk 0000
"""
import argparse, json, os, socket, sys, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))

# Standard Bravia IRCC codes. Replaced by the TV's own list when it answers.
CODES = {
    "Power": "AAAAAQAAAAEAAAAVAw==", "PowerOff": "AAAAAQAAAAEAAAAvAw==",
    "Input": "AAAAAQAAAAEAAAAlAw==", "Home": "AAAAAQAAAAEAAABgAw==",
    "Up": "AAAAAQAAAAEAAAB0Aw==", "Down": "AAAAAQAAAAEAAAB1Aw==",
    "Left": "AAAAAQAAAAEAAAA0Aw==", "Right": "AAAAAQAAAAEAAAAzAw==",
    "Confirm": "AAAAAQAAAAEAAABlAw==", "Return": "AAAAAgAAAJcAAAAjAw==",
    "Options": "AAAAAgAAAJcAAAA2Aw==",
    "VolumeUp": "AAAAAQAAAAEAAAASAw==", "VolumeDown": "AAAAAQAAAAEAAAATAw==",
    "Mute": "AAAAAQAAAAEAAAAUAw==",
    "ChannelUp": "AAAAAQAAAAEAAAAQAw==", "ChannelDown": "AAAAAQAAAAEAAAARAw==",
    "Play": "AAAAAgAAAJcAAAAaAw==", "Pause": "AAAAAgAAAJcAAAAZAw==",
    "Stop": "AAAAAgAAAJcAAAAYAw==", "Rewind": "AAAAAgAAAJcAAAAbAw==",
    "Forward": "AAAAAgAAAJcAAAAcAw==",
    "Num1": "AAAAAQAAAAEAAAAAAw==", "Num2": "AAAAAQAAAAEAAAABAw==",
    "Num3": "AAAAAQAAAAEAAAACAw==", "Num4": "AAAAAQAAAAEAAAADAw==",
    "Num5": "AAAAAQAAAAEAAAAEAw==", "Num6": "AAAAAQAAAAEAAAAFAw==",
    "Num7": "AAAAAQAAAAEAAAAGAw==", "Num8": "AAAAAQAAAAEAAAAHAw==",
    "Num9": "AAAAAQAAAAEAAAAIAw==", "Num0": "AAAAAQAAAAEAAAAJAw==",
    "Hdmi1": "AAAAAgAAABoAAABaAw==", "Hdmi2": "AAAAAgAAABoAAABbAw==",
    "Hdmi3": "AAAAAgAAABoAAABcAw==", "Hdmi4": "AAAAAgAAABoAAABdAw==",
    "Netflix": "AAAAAgAAABoAAAB8Aw==", "YouTube": "AAAAAgAAAMQAAABHAw==",
}

IRCC_BODY = ('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
             's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
             '<u:X_SendIRCC xmlns:u="urn:schemas-sony-com:service:IRCC:1"><IRCCCode>{}</IRCCCode>'
             '</u:X_SendIRCC></s:Body></s:Envelope>')


class TV:
    def __init__(self, host, psk):
        self.host, self.psk = host, psk

    def _post(self, path, body, headers, port=80, timeout=4):
        req = urllib.request.Request(f"http://{self.host}:{port}{path}", data=body.encode(), method="POST")
        for k, v in headers.items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode(errors="replace")

    def rpc(self, service, method, params=None):
        body = json.dumps({"method": method, "params": params or [], "id": 1, "version": "1.0"})
        out = json.loads(self._post(f"/sony/{service}", body,
                                    {"Content-Type": "application/json", "X-Auth-PSK": self.psk}))
        if "error" in out:
            raise RuntimeError(f"TV said: {out['error']}")
        return out.get("result", [])

    def ircc(self, name):
        code = CODES.get(name)
        if not code:
            raise KeyError(f"Unknown button {name}")
        self._post("/sony/IRCC", IRCC_BODY.format(code), {
            "Content-Type": 'text/xml; charset=UTF-8',
            "SOAPACTION": '"urn:schemas-sony-com:service:IRCC:1#X_SendIRCC"',
            "X-Auth-PSK": self.psk})

    def power_status(self):
        return self.rpc("system", "getPowerStatus")[0]["status"]  # "active" / "standby"

    def toggle_power(self):
        try:
            on = self.power_status() == "active"
            self.rpc("system", "setPowerStatus", [{"status": not on}])
            return "off" if on else "on"
        except Exception:
            self.ircc("Power")
            return "toggled"

    def launch_app(self, app):
        # DIAL: works for Netflix / YouTube without any pairing.
        self._post(f"/ws/apps/{app}", "", {"Content-Type": "text/plain"}, port=8080)

    def load_codes(self):
        try:
            res = self.rpc("system", "getRemoteControllerInfo")
            got = {c["name"]: c["value"] for c in res[1]}
            CODES.update(got)
            return len(got)
        except Exception as e:
            return f"using built-in buttons ({e})"


class Handler(BaseHTTPRequestHandler):
    tv: TV = None

    def log_message(self, fmt, *args):
        sys.stderr.write("  " + (fmt % args) + "\n")

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "remote.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if self.path == "/api/status":
            try:
                return self._send(200, {"ok": True, "power": self.tv.power_status(), "tv": self.tv.host})
            except Exception as e:
                return self._send(200, {"ok": False, "error": str(e), "tv": self.tv.host})
        self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            msg = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/api/key":
                self.tv.ircc(msg["name"])
                return self._send(200, {"ok": True})
            if self.path == "/api/power":
                return self._send(200, {"ok": True, "power": self.tv.toggle_power()})
            if self.path == "/api/app":
                app = msg["id"]
                try:
                    self.tv.launch_app(app)
                except Exception:
                    self.tv.ircc(app)  # fall back to the remote's app button
                return self._send(200, {"ok": True})
            self._send(404, {"ok": False, "error": "not found"})
        except urllib.error.HTTPError as e:
            hint = " - check the Pre-Shared Key on the TV" if e.code in (401, 403) else ""
            self._send(502, {"ok": False, "error": f"TV returned {e.code}{hint}"})
        except Exception as e:
            self._send(502, {"ok": False, "error": str(e)})


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    p = argparse.ArgumentParser(description="Phone remote for a Sony Bravia TV")
    p.add_argument("--tv", default=os.environ.get("TV_IP", "192.168.1.115"), help="TV's IP address")
    p.add_argument("--psk", default=os.environ.get("TV_PSK", "0000"), help="Pre-Shared Key set on the TV")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    a = p.parse_args()

    Handler.tv = TV(a.tv, a.psk)
    print(f"TV at {a.tv}: loaded buttons -> {Handler.tv.load_codes()}")
    srv = ThreadingHTTPServer(("0.0.0.0", a.port), Handler)
    print(f"\n  On your phone (same Wi-Fi), open:  http://{local_ip()}:{a.port}\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
