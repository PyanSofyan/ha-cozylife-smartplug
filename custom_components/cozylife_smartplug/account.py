"""Authorization-code exchange and device metadata (no stored session token)."""

from dataclasses import dataclass, field
import ipaddress
import re

import aiohttp

from .const import (
    AUTH_CODE_URL, DEVICE_LIST_URL, CLOUD_USER_AGENT, CLOUD_TIMEOUT,
    DEVICE_TYPE_SMART_PLUG, DEVICE_TYPE_SMART_SWITCH,
)


class AccountError(Exception):
    """The metadata API could not be reached or returned invalid data."""


class InvalidAuthorization(AccountError):
    """The authorization code or session token was rejected."""


def valid_wss_domain(value):
    """Only send control credentials to the vendor's advertised TLS hosts."""
    if not isinstance(value, str):
        return False
    return bool(re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]*\.doiting\.com", value))


def model_device_type(raw):
    """Prefer explicit model type; support both spellings used for sockets."""
    models = {
        "smart switch": DEVICE_TYPE_SMART_SWITCH,
        "metring socket": DEVICE_TYPE_SMART_PLUG,
        "metering socket": DEVICE_TYPE_SMART_PLUG,
        "smart plug": DEVICE_TYPE_SMART_PLUG,
    }
    for key in ("device_model_type", "device_model_name"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip().lower() in models:
            return models[value.strip().lower()]
    return None


@dataclass(frozen=True)
class CloudDevice:
    device_id: str
    device_key: str = field(repr=False)
    name: str
    device_type: str
    model: str
    relay_host: str
    relay_port: int
    wss_domain: str


def parse_devices(response):
    """Select supported bound/shared devices, not virtual device groups."""
    info = response.get("info")
    if not isinstance(info, dict):
        raise AccountError("Invalid device list")
    devices = {}
    for section in ("device_bind", "device_share"):
        group = info.get(section, {})
        rows = group.get("list", []) if isinstance(group, dict) else []
        if not isinstance(rows, list):
            continue
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            device_type = model_device_type(raw)
            did, key = raw.get("device_id"), raw.get("device_key")
            host, domain = raw.get("ip"), raw.get("wss_domain")
            if not device_type or not all(
                isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_-]+", v)
                for v in (did, key)
            ) or not valid_wss_domain(domain):
                continue
            try:
                port = int(raw.get("port"))
                if not ipaddress.ip_address(host).is_global or not 1 <= port <= 65535:
                    continue
            except (TypeError, ValueError):
                continue
            devices.setdefault(did, CloudDevice(
                device_id=did, device_key=key,
                name=str(raw.get("device_name") or did), device_type=device_type,
                model=str(raw.get("device_model_name") or raw.get("device_model_type") or ""),
                relay_host=host, relay_port=port, wss_domain=domain.lower(),
            ))
    return list(devices.values())


class CozyLifeAccount:
    def __init__(self, session):
        self._session = session

    async def _get(self, url, params):
        # Do not propagate/log aiohttp exceptions: their URLs contain credentials.
        try:
            async with self._session.get(
                url, params=params, headers={"User-Agent": CLOUD_USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=CLOUD_TIMEOUT),
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise AccountError("Metadata HTTP request failed")
                body = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            raise AccountError("Metadata request failed") from None
        if not isinstance(body, dict):
            raise AccountError("Invalid metadata response")
        if str(body.get("ret")) != "1":
            if str(body.get("ret")) in {"9", "1001", "2006"}:
                raise InvalidAuthorization("Authorization was rejected")
            raise AccountError("Metadata API rejected request")
        return body

    async def async_devices(self, authorization_code):
        code = authorization_code.strip()
        if not code:
            raise InvalidAuthorization("Authorization code is empty")
        result = await self._get(AUTH_CODE_URL, {"auth_code": code, "lang": "en"})
        info = result.get("info")
        token = info.get("token") if isinstance(info, dict) else None
        if not isinstance(token, str) or not token:
            raise InvalidAuthorization("No session token was returned")
        result = await self._get(DEVICE_LIST_URL, {
            "token": token, "platform": "android", "lang": "en",
        })
        return parse_devices(result)
