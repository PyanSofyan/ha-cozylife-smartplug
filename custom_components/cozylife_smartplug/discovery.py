"""Read-only UDP discovery, independent of the unchanged local TCP client."""

import ipaddress
import json
import socket
import time
import logging
_LOGGER = logging.getLogger(__name__)

DISCOVERY_PORT = 6095


async def async_broadcast_targets(hass):
    from homeassistant.components.network import async_get_ipv4_broadcast_addresses

    targets = await async_get_ipv4_broadcast_addresses(hass)
    return [str(address) for address in targets] or ["255.255.255.255"]


def parse_discovery_reply(payload, sender_ip):
    try:
        address = ipaddress.IPv4Address(sender_ip)
        if not address.is_private or address.is_loopback or address.is_unspecified:
            return None
        body = json.loads(payload)
        msg = body.get("msg") if isinstance(body, dict) else None
        did = msg.get("did") if isinstance(msg, dict) else None
        if not isinstance(did, str) or not did:
            return None
        # Use the packet source rather than a stale or forged IP in the body.
        return did, str(address)
    except (ValueError, UnicodeError):
        return None


def discover_devices(targets=("255.255.255.255",), timeout=3):
    """Broadcast metadata command 0; never send control commands over UDP."""
    frame = {"cmd": 0, "pv": 0, "sn": str(time.time_ns() // 1_000_000), "msg": {}}
    payload = json.dumps(frame, separators=(",", ":")).encode()
    found = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for target in targets or ("255.255.255.255",):
            try:
                sock.sendto(payload, (target, DISCOVERY_PORT))
                _LOGGER.debug("Discovery sent to %s", target)
            except OSError:
                _LOGGER.warning("Discovery send to %s failed: %s", target, err)
                continue
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            sock.settimeout(remaining)
            try:
                payload, sender = sock.recvfrom(8192)
            except OSError as err:
                _LOGGER.warning("Discovery recv failed: %s", err)
                break
            _LOGGER.debug("Reply from %s: %r", sender, payload)
            result = parse_discovery_reply(payload, sender[0])
            if result:
                found[result[0]] = result[1]
    return found
