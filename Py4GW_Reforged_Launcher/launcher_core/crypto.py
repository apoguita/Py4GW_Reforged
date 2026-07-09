"""DPAPI (CurrentUser scope) password protection.

Python equivalent of GWxLauncher/Services/DpapiProtector.cs. Uses pywin32's
win32crypt.CryptProtectData/CryptUnprotectData, which call the same Windows DPAPI
CryptProtectData/CryptUnprotectData API that .NET's ProtectedData wraps -- so a blob
encrypted by the C# launcher decrypts fine here, and vice versa, as long as it's the
same Windows user account.

No optional entropy, no description -- matches DpapiProtector.cs exactly so the two
are byte-for-byte interoperable at the DPAPI call level.
"""

from __future__ import annotations

import base64

import win32crypt


def protect_password(plaintext: str) -> str:
    """Encrypt `plaintext` for the current Windows user, return a base64 string.

    Mirrors DpapiProtector.ProtectToBase64: always encrypts, including an empty
    string (no short-circuit on encrypt).
    """
    if plaintext is None:
        raise TypeError("plaintext must not be None")

    data_in = plaintext.encode("utf-8")
    protected_bytes = win32crypt.CryptProtectData(data_in, None, None, None, None, 0)
    return base64.b64encode(protected_bytes).decode("ascii")


def unprotect_password(protected_base64: str) -> str:
    """Decrypt a base64 blob produced by `protect_password` for the current Windows user.

    Mirrors DpapiProtector.UnprotectFromBase64: empty/whitespace-only input returns
    "" without touching DPAPI (that's the "no password stored" case).
    """
    if protected_base64 is None:
        raise TypeError("protected_base64 must not be None")

    if protected_base64.strip() == "":
        return ""

    protected_bytes = base64.b64decode(protected_base64)
    _description, plaintext_bytes = win32crypt.CryptUnprotectData(protected_bytes, None, None, None, 0)
    return plaintext_bytes.decode("utf-8")
