"""Validate destinations without exposing credentials or accessing private hosts."""
from __future__ import annotations

import http.client
import ipaddress
import json
import re
import socket
import ssl
from urllib.parse import urlsplit


def validate_target(channel: str, target: str) -> str:
    target = target.strip()
    if channel == "sms":
        raise ValueError("SMS alerts are planned and are not available yet. Use email or Slack.")
    if channel == "email":
        if (len(target) > 320 or not re.fullmatch(r"[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+", target)
                or target.lower().startswith("shopify-admin+")
                or target.lower() in {"alerts@example.com", "example@example.com"}):
            raise ValueError("Enter a real email address where you can receive alerts.")
        return target
    if channel not in {"slack", "webhook"}:
        raise ValueError("Unsupported alert channel.")
    try:
        parsed = urlsplit(target)
        hostname = parsed.hostname or ""
        if (parsed.scheme != "https" or not hostname or parsed.port not in {None, 443}
                or parsed.username or parsed.password or parsed.fragment
                or any(char.isspace() for char in target)):
            raise ValueError
        if channel == "slack" and (hostname != "hooks.slack.com" or not parsed.path.startswith("/services/")):
            raise ValueError
        if hostname.lower() in {"localhost", "metadata.google.internal"} or "." not in hostname:
            raise ValueError
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError
    except ValueError:
        raise ValueError("Use a public HTTPS " + ("Slack incoming-webhook URL." if channel == "slack" else "webhook URL on port 443.")) from None
    return target


def post_public_json(target: str, payload: dict, *, timeout: int = 10) -> int:
    """Pin a public resolved address, retain TLS hostname checks, and never follow redirects."""
    target = validate_target("webhook", target)
    parsed = urlsplit(target)
    hostname = parsed.hostname or ""
    addresses = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise ValueError("Webhook destinations must resolve only to public internet addresses.")
    connection = http.client.HTTPSConnection(hostname, timeout=max(1, min(timeout, 30)))
    raw_socket = socket.create_connection((addresses[0][4][0], 443), timeout=connection.timeout)
    try:
        connection.sock = ssl.create_default_context().wrap_socket(raw_socket, server_hostname=hostname)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        connection.request("POST", path, body=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        if not 200 <= response.status < 300:
            raise NotificationHttpError(response.status)
        return response.status
    finally:
        connection.close()
        raw_socket.close()


class NotificationHttpError(RuntimeError):
    def __init__(self, status: int):
        self.status = status
        super().__init__(f"Notification endpoint returned HTTP {status}.")
