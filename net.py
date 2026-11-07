# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Online play for built tabs that are allowed it ("online": true in their meta.json).

The tab itself stays walled off. It hands its game messages to the app page, which seals each one
(AES-256-GCM, key made from the private invite code) before it reaches here. This file only carries
those sealed messages through a public MQTT relay, over TLS, on a channel name also made from the
code. It never sees the code or the key, so neither it nor the relay can read what is sent.

What it checks: the channel name's shape, message size, how many messages a second, and how many
links are open. It only ever connects to the relays listed in RELAYS.
"""
import os
import queue
import re
import socket
import ssl
import threading
import time

RELAYS = {"E": ("broker.emqx.io", 8883), "H": ("broker.hivemq.com", 8883), "M": ("test.mosquitto.org", 8886)}
ORDER = "EHM"                         # tried in this order when hosting; the invite code names the one used
CHANNEL = re.compile(r"ruds/[0-9a-f]{32}")
SEALED = re.compile(r"[A-Za-z0-9+/=]{1,24000}")
MAX_LINKS = 3
RATE, BURST = 60.0, 120.0             # messages a second each link may send


def _varint(n):
    out = bytearray()
    while True:
        b, n = n % 128, n // 128
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _str(b):
    return len(b).to_bytes(2, "big") + b


class Link:
    """One MQTT 3.1.1 connection to one relay, subscribed to one channel."""

    def __init__(self, relay, channel, timeout=8):
        if relay not in RELAYS or not CHANNEL.fullmatch(channel):
            raise ValueError("not a valid relay or channel")
        host, port = RELAYS[relay]
        self.channel = channel.encode()
        self.inbox = queue.Queue(maxsize=500)
        self.open = True
        self._lock = threading.Lock()
        self._tokens, self._t = BURST, time.time()
        raw = socket.create_connection((host, port), timeout=timeout)
        self._s = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        cid = b"ruds" + os.urandom(8).hex().encode()
        self._packet(0x10, _str(b"MQTT") + b"\x04\x02\x00\x3c" + _str(cid))
        kind, body = self._read()
        if kind != 2 or len(body) < 2 or body[1] != 0:
            raise OSError("the relay refused the connection")
        self._packet(0x82, b"\x00\x01" + _str(self.channel) + b"\x00")
        kind, body = self._read()
        if kind != 9 or body[-1:] == b"\x80":
            raise OSError("the relay refused the channel")
        self._s.settimeout(None)
        threading.Thread(target=self._reader, daemon=True).start()
        threading.Thread(target=self._pinger, daemon=True).start()

    def _packet(self, first, body):
        with self._lock:
            self._s.sendall(bytes([first]) + _varint(len(body)) + body)

    def _exact(self, n):
        buf = b""
        while len(buf) < n:
            part = self._s.recv(n - len(buf))
            if not part:
                raise OSError("the relay closed the connection")
            buf += part
        return buf

    def _read(self):
        first = self._exact(1)[0]
        n, mult = 0, 1
        for _ in range(4):
            b = self._exact(1)[0]
            n += (b & 0x7F) * mult
            mult *= 128
            if not b & 0x80:
                break
        if n > 70000:
            raise OSError("the relay sent something too big")
        return first >> 4, self._exact(n) if n else b""

    def _reader(self):
        try:
            while self.open:
                kind, body = self._read()
                if kind != 3 or len(body) < 2:
                    continue
                tl = int.from_bytes(body[:2], "big")
                topic, rest = body[2:2 + tl], body[2 + tl:]
                if topic != self.channel:
                    continue
                text = rest.decode("ascii", "replace")
                if SEALED.fullmatch(text):
                    try:
                        self.inbox.put_nowait(text)
                    except queue.Full:
                        pass
        except (OSError, ValueError):
            pass
        self.close()

    def _pinger(self):
        while self.open:
            time.sleep(25)
            try:
                self._packet(0xC0, b"")
            except OSError:
                self.close()

    def send(self, sealed):
        if not self.open or not isinstance(sealed, str) or not SEALED.fullmatch(sealed):
            return False
        now = time.time()
        self._tokens = min(BURST, self._tokens + (now - self._t) * RATE)
        self._t = now
        if self._tokens < 1:
            return False
        self._tokens -= 1
        try:
            self._packet(0x30, _str(self.channel) + sealed.encode("ascii"))
            return True
        except OSError:
            self.close()
            return False

    def recv(self, wait=1.0):
        """Waits up to `wait` seconds for messages, then returns all that have come."""
        out = []
        try:
            out.append(self.inbox.get(timeout=wait))
            while len(out) < 200:
                out.append(self.inbox.get_nowait())
        except queue.Empty:
            pass
        return out

    def close(self):
        if not self.open:
            return
        self.open = False
        try:
            self._packet(0xE0, b"")
        except OSError:
            pass
        try:
            self._s.close()
        except OSError:
            pass
        try:
            self.inbox.put_nowait(None)          # wakes a waiting recv
        except queue.Full:
            pass


class Hub:
    """The open links, by an id the page gets back."""

    def __init__(self):
        self._links = {}
        self._lock = threading.Lock()

    def open(self, relay, channel):
        with self._lock:
            for k in [k for k, l in self._links.items() if not l.open]:
                del self._links[k]
            if len(self._links) >= MAX_LINKS:
                return {"error": "Too many online games are open. Leave one first."}
        tries = [relay] if relay else list(ORDER)
        last = "no relay answered"
        for r in tries:
            try:
                link = Link(r, channel)
            except ValueError as e:
                return {"error": str(e)}
            except OSError as e:
                last = str(e) or type(e).__name__
                continue
            sid = os.urandom(8).hex()
            with self._lock:
                self._links[sid] = link
            return {"sid": sid, "relay": r}
        return {"error": f"Couldn't reach the relay server ({last}). Check your internet connection."}

    def send(self, sid, sealed):
        link = self._links.get(sid)
        return bool(link and link.send(sealed))

    def recv(self, sid, wait=1.0):
        link = self._links.get(sid)
        if not link:
            return {"msgs": [], "open": False}
        msgs = [m for m in link.recv(wait) if m]
        return {"msgs": msgs, "open": link.open}

    def close(self, sid):
        link = self._links.pop(sid, None)
        if link:
            link.close()

    def close_all(self):
        for sid in list(self._links):
            self.close(sid)
