"""CozyLife TCP client."""

import socket
import json
import time
import logging
import threading
from .const import (
    SWITCH_ID,
    ON_STATE_ID,
    CURRENT_ID,
    POWER_ID,
    VOLTAGE_ID,
    OVERCURRENT_PROTECT_ID,
    ENERGY_ID,
    CMD_SET,
    CMD_QUERY,
)

_LOGGER = logging.getLogger(__name__)


class CozyLifeClient:
    def __init__(self, ip, port=5555):
        self.ip = ip
        self.port = port
        self._lock = threading.Lock()
        self._connect_timeout = 3
        self._read_timeout = 2

    def _connect(self) -> socket.socket:
        """Create new connection."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self._connect_timeout)
        sock.connect((self.ip, self.port))
        return sock

    def _close(self, sock: socket.socket) -> None:
        """Close connection with proper shutdown."""
        try:
            sock.shutdown(socket.SHUT_RDWR)  # beritahu device koneksi ditutup
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    @staticmethod
    def _get_sn() -> str:
        return str(int(time.time() * 1000))

    def _send_message(self, command: dict) -> dict | None:
        """Open connection, send command, read response, close connection."""
        sock = None
        try:
            sock = self._connect()
            payload = (json.dumps(command) + "\r\n").encode()
            sock.sendall(payload)
            return self._read_response(sock)
        except OSError as e:
            _LOGGER.debug("Communication failed with %s: %s", self.ip, e)
            return None
        finally:
            if sock:
                self._close(sock)

    def _read_response(self, sock: socket.socket) -> dict | None:
        sock.settimeout(self._read_timeout)
        buffer = ""
        try:
            while True:
                try:
                    chunk = sock.recv(1024).decode("utf-8")
                except UnicodeDecodeError:
                    _LOGGER.debug("Invalid UTF-8 from %s", self.ip)
                    continue

                if not chunk:
                    break

                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        _LOGGER.debug("Invalid JSON from %s, skipping", self.ip)

        except socket.timeout:
            _LOGGER.debug("Read timeout from %s", self.ip)
        except ConnectionResetError:
            _LOGGER.debug("Connection reset by %s", self.ip)
        except OSError as e:
            _LOGGER.debug("Socket error from %s: %s", self.ip, e)

        return None

    def test_connection(self) -> bool:
        try:
            data = self.query_state()
            return data is not None
        except Exception:
            return False

    def query_state(self) -> dict | None:
        with self._lock:
            command = {
                "cmd": CMD_QUERY,
                "pv": 0,
                "sn": self._get_sn(),
                "msg": {
                    "attr": [
                        SWITCH_ID, ON_STATE_ID, CURRENT_ID, POWER_ID, 
                        VOLTAGE_ID, OVERCURRENT_PROTECT_ID, ENERGY_ID,
                    ]
                },
            }
            response = self._send_message(command)
        if response and response.get("msg"):
            return response["msg"].get("data", {})
        return None

    def set_state(self, attr, data) -> dict | None:
        with self._lock:
            command = {
                "cmd": CMD_SET,
                "pv": 0,
                "sn": self._get_sn(),
                "msg": {"attr": attr, "data": data},
            }
            response = self._send_message(command)
        if response and response.get("msg"):
            return response["msg"].get("data", {})
        return None