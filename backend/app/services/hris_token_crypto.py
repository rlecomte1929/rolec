"""
AES-256-GCM token encryption/decryption for HRIS access tokens.  (AIQ-33-A/C)

Key source : HRIS_TOKEN_ENCRYPTION_KEY env var (64 hex chars = 32 bytes).
Wire format: base64( 12-byte IV || ciphertext || 16-byte GCM tag )
             — compatible with the TypeScript token-crypto.ts counterpart.

Usage
-----
    from backend.app.services.hris_token_crypto import encrypt_token, decrypt_token

    enc = encrypt_token("my_access_token")   # store in hris_connections.access_token
    dec = decrypt_token(enc)                 # call before any Personio API request
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _get_key() -> bytes:
    key_hex = os.getenv("HRIS_TOKEN_ENCRYPTION_KEY", "")
    if not key_hex or len(key_hex) != 64:
        raise RuntimeError(
            "HRIS_TOKEN_ENCRYPTION_KEY must be set to 64 hex chars (32 bytes). "
            "Generate with: openssl rand -hex 32"
        )
    return bytes.fromhex(key_hex)


def encrypt_token(plaintext: str) -> str:
    """
    Encrypt a token string.

    Returns
    -------
    str
        Base64-encoded blob: IV (12 bytes) || ciphertext || GCM tag (16 bytes).
    """
    key = _get_key()
    iv = os.urandom(12)          # 96-bit nonce — recommended for AES-GCM
    aesgcm = AESGCM(key)
    ciphertext_with_tag = aesgcm.encrypt(iv, plaintext.encode(), None)
    return base64.b64encode(iv + ciphertext_with_tag).decode()


def decrypt_token(ciphertext_b64: str) -> str:
    """
    Decrypt a token string.

    Parameters
    ----------
    ciphertext_b64 : str
        Base64-encoded blob produced by :func:`encrypt_token`.

    Returns
    -------
    str
        The original plaintext token.

    Raises
    ------
    cryptography.exceptions.InvalidTag
        If the ciphertext has been tampered with or the wrong key is used.
    """
    key = _get_key()
    raw = base64.b64decode(ciphertext_b64)
    iv = raw[:12]
    ciphertext_with_tag = raw[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, ciphertext_with_tag, None).decode()
