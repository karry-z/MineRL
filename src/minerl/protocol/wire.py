from __future__ import annotations

import logging
import os
import socket
import struct
import time

from minerl.runtime.backend import BackendError

logger = logging.getLogger(__name__)


class ProtocolError(BackendError):
    """Malformed or incomplete Malmo socket message."""


def send_message(sock: socket.socket, data: bytes) -> None:
    started = time.monotonic()
    try:
        sock.sendall(struct.pack("!I", len(data)))
        sock.sendall(data)
    except socket.timeout as exc:
        logger.warning(f"Timed out while sending {len(data)} bytes to Minecraft.")
        raise ProtocolError("socket timed out while sending message") from exc
    if _trace_protocol():
        logger.debug(f"Sent {len(data)} bytes to Minecraft in {_duration_ms(started)} ms.")


def recv_message(sock: socket.socket) -> bytes:
    started = time.monotonic()
    length_buf = recvall(sock, 4)
    if not length_buf:
        logger.warning("Minecraft closed the socket while sending a message length.")
        raise ProtocolError("socket closed while reading message length")
    (length,) = struct.unpack("!I", length_buf)
    payload = recvall(sock, length)
    if _trace_protocol():
        logger.debug(f"Received {length} bytes from Minecraft in {_duration_ms(started)} ms.")
    return payload


def recvall(sock: socket.socket, count: int) -> bytes:
    chunks = bytearray()
    while count:
        try:
            chunk = sock.recv(count)
        except socket.timeout as exc:
            logger.warning(f"Timed out while reading from Minecraft; {count} bytes still missing.")
            raise ProtocolError("socket timed out while reading message payload") from exc
        if not chunk:
            logger.warning(f"Minecraft closed the socket with {count} payload bytes still missing.")
            raise ProtocolError("socket closed while reading message payload")
        chunks.extend(chunk)
        count -= len(chunk)
    return bytes(chunks)


def _duration_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _trace_protocol() -> bool:
    return os.environ.get("MINERL_TRACE_PROTOCOL") == "1"
