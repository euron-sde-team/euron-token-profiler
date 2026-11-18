"""Authenticated encryption for credentials TokenProfiler has to store and use later.

Upstream endpoints (an OpenAI-compatible server, a hosted provider) may need an API key.
It is sealed with AES-256-GCM under a key derived from ENCRYPTION_KEY by HKDF-SHA256, with
the owning record's id as associated data, so a ciphertext copied onto another row does
not decrypt. The stored form is `v1.<base64url(nonce || ciphertext)>`.
"""

from __future__ import annotations

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_VERSION = "v1"
_INFO = b"tokenprofiler/secretbox/v1"


class SecretBoxError(ValueError):
    """A sealed value could not be opened (wrong key, wrong record or tampered)."""


class SecretBox:
    def __init__(self, master: str) -> None:
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_INFO).derive(
            master.encode()
        )
        self._aead = AESGCM(key)

    def seal(self, plaintext: str, *, context: str) -> str:
        nonce = os.urandom(12)
        sealed = self._aead.encrypt(nonce, plaintext.encode(), context.encode())
        return f"{_VERSION}.{base64.urlsafe_b64encode(nonce + sealed).decode()}"

    def open(self, token: str, *, context: str) -> str:
        version, _, body = token.partition(".")
        if version != _VERSION or not body:
            raise SecretBoxError("unknown sealed value format")
        try:
            raw = base64.urlsafe_b64decode(body.encode())
            plaintext = self._aead.decrypt(raw[:12], raw[12:], context.encode())
        except (InvalidTag, ValueError) as exc:
            raise SecretBoxError("sealed value does not open with this key and context") from exc
        return plaintext.decode()
