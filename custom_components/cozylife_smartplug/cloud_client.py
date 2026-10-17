"""Persistent vendor WSS relay with subscriptions and correlated commands."""

import asyncio
import json
import re
import time
from urllib.parse import unquote

import aiohttp

from .account import valid_wss_domain
from .const import CLOUD_TIMEOUT, CLOUD_USER_AGENT, CMD_QUERY, CMD_SET


class CloudError(Exception):
    """A cloud operation failed; command_sent means delivery is ambiguous."""

    def __init__(self, message, *, command_sent=False):
        super().__init__(message)
        self.command_sent = command_sent


class CozyLifeCloudClient:
    def __init__(self, session, device_id, device_key, wss_domain, on_data, on_disconnect):
        if not valid_wss_domain(wss_domain):
            raise CloudError("Invalid vendor WSS domain")
        if not all(isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_-]+", v)
                   for v in (device_id, device_key)):
            raise CloudError("Invalid control credentials")
        self._session = session
        self._device_id = device_id
        self._device_key = device_key
        self._url = f"wss://{wss_domain}/ws"
        self._on_data = on_data
        self._on_disconnect = on_disconnect
        self._ready = asyncio.Event()
        self._request_lock = asyncio.Lock()
        self._pending = {}
        self._subscribe = None
        self._ws = None
        self._task = None
        self._stopping = False
        self._sn = 0

    @property
    def connected(self):
        return self._ready.is_set() and self._ws is not None and not self._ws.closed

    def async_start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def async_close(self):
        self._stopping = True
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    def _fail_pending(self):
        for _, future in self._pending.values():
            if not future.done():
                future.set_exception(CloudError("Cloud connection lost", command_sent=True))

    async def _run(self):
        delay = 2
        while not self._stopping:
            reader = None
            try:
                async with asyncio.timeout(CLOUD_TIMEOUT):
                    self._ws = await self._session.ws_connect(
                        self._url, headers={"User-Agent": CLOUD_USER_AGENT},
                        heartbeat=30, max_msg_size=65536,
                    )
                # aiohttp follows handshake redirects. Check the final secure
                # vendor endpoint before sending any control credentials.
                final_url = self._ws._response.url
                if final_url.scheme not in ("https", "wss") or not valid_wss_domain(final_url.host):
                    raise CloudError("WebSocket redirected to an untrusted endpoint")
                self._subscribe = asyncio.get_running_loop().create_future()
                reader = asyncio.create_task(self._read_messages(self._ws))
                await self._ws.send_str(
                    f"cmd=subscribe&topic=device_{self._device_id}&from=control"
                    f"&device_id={self._device_id}&device_key={self._device_key}"
                )
                async with asyncio.timeout(CLOUD_TIMEOUT):
                    await self._subscribe
                self._ready.set()
                delay = 2
                await reader
            except (aiohttp.ClientError, TimeoutError, CloudError, OSError):
                # Never log raw URLs, envelopes, keys, or server error text.
                pass
            finally:
                self._ready.clear()
                self._fail_pending()
                if reader:
                    reader.cancel()
                    await asyncio.gather(reader, return_exceptions=True)
                if self._ws:
                    await self._ws.close()
                self._ws = None
                self._subscribe = None
                if not self._stopping:
                    self._on_disconnect()
            if not self._stopping:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)

    async def _read_messages(self, ws):
        async for message in ws:
            if message.type == aiohttp.WSMsgType.TEXT:
                for line in message.data.splitlines():
                    self._handle_line(line)
            elif message.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE,
                                  aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                break
        if self._subscribe is not None and not self._subscribe.done():
            self._subscribe.set_exception(CloudError("Subscription connection lost"))

    def _handle_line(self, line):
        fields = {}
        for part in line.split("&"):
            key, sep, value = part.partition("=")
            if sep:
                fields[key] = unquote(value)
        if fields.get("device_id", self._device_id) != self._device_id:
            return
        topic = fields.get("topic")
        if fields.get("cmd") == "subscribe" and topic == f"device_{self._device_id}":
            if self._subscribe is not None and not self._subscribe.done():
                if fields.get("res") == "1":
                    self._subscribe.set_result(None)
                else:
                    self._subscribe.set_exception(CloudError("Subscription rejected"))
            return
        if fields.get("cmd") != "publish":
            return
        if topic == f"control_{self._device_id}":
            if fields.get("num") == "0" or fields.get("res") != "1":
                for _, future in self._pending.values():
                    if not future.done():
                        future.set_exception(CloudError("Relay did not deliver command", command_sent=True))
            return
        if topic != f"device_{self._device_id}":
            return
        try:
            reply = json.loads(fields.get("message", ""))
        except (ValueError, TypeError):
            return
        if not isinstance(reply, dict):
            return
        pending = self._pending.get(str(reply.get("sn")))
        successful = type(reply.get("res")) is int and reply["res"] == 0
        if pending and pending[0] == reply.get("cmd") and not pending[1].done():
            if successful:
                pending[1].set_result(reply)
            else:
                pending[1].set_exception(CloudError("Device rejected command", command_sent=True))
        msg = reply.get("msg")
        data = msg.get("data") if isinstance(msg, dict) else None
        if successful and reply.get("cmd") in (2, 3, 10) and isinstance(data, dict):
            self._on_data(data)
        elif reply.get("cmd") == 7:
            self._on_disconnect()

    async def _exchange(self, cmd, msg):
        self.async_start()
        async with self._request_lock:
            sent = False
            try:
                async with asyncio.timeout(CLOUD_TIMEOUT):
                    await self._ready.wait()
                    if not self.connected:
                        raise CloudError("Cloud is disconnected")
                    self._sn = max(self._sn + 1, time.time_ns() // 1_000_000)
                    sn = str(self._sn)
                    frame = json.dumps({"cmd": cmd, "pv": 0, "sn": sn, "msg": msg}, separators=(",", ":"))
                    if any(char in frame for char in ("&", "\r", "\n")):
                        raise CloudError("Unsupported payload delimiter")
                    future = asyncio.get_running_loop().create_future()
                    self._pending[sn] = (cmd, future)
                    # After entering send, delivery is conservatively ambiguous.
                    sent = True
                    await self._ws.send_str(
                        f"cmd=publish&device_id={self._device_id}&topic=control_{self._device_id}"
                        f"&device_key={self._device_key}&message={frame}"
                    )
                    reply = await future
                    message = reply.get("msg")
                    data = message.get("data") if isinstance(message, dict) else None
                    if not isinstance(data, dict):
                        raise CloudError("Device reply has no data", command_sent=True)
                    return data
            except (TimeoutError, aiohttp.ClientError, OSError):
                raise CloudError("Cloud operation failed", command_sent=sent) from None
            finally:
                if "sn" in locals():
                    pending = self._pending.pop(sn, None)
                    if pending:
                        future = pending[1]
                        if not future.done():
                            future.cancel()
                        elif not future.cancelled():
                            future.exception()  # consume abandoned errors on cancellation

    async def async_query_state(self, attrs):
        return await self._exchange(CMD_QUERY, {"attr": attrs})

    async def async_set_state(self, attrs, data):
        # Deliberately no write retries, including after a reconnect.
        return await self._exchange(CMD_SET, {"attr": attrs, "data": data})
