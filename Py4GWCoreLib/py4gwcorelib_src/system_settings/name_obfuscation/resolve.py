"""Resolve (possibly obfuscated) display names back to their real value.

Name obfuscation rewrites INCOMING names to aliases, so anything the user sees can be a fake. But
some game actions are sent BY NAME and the server needs the REAL name — e.g. party invite
(``/invite <name>``). Call :func:`require_real_name` on such a name right before sending it.

Kept dependency-free (no controller / model / store / Settings imports) so hot paths can resolve a
name with a single lazy native call and no package overhead. ``PyNameObfuscator`` is imported lazily,
so this is import-safe offline.
"""


def require_real_name(name: str) -> str:
    """Return the real name for a display name, or the input unchanged.

    Uses the obfuscator's own reverse mapping (observed cache, then alias reverse). Safe in every
    case: obfuscation off / name not aliased / obfuscator unavailable (offline) all return the input.
    """
    try:
        import PyNameObfuscator

        resolved = PyNameObfuscator.require_real_name(str(name))
        return resolved if resolved else str(name)
    except Exception:
        return str(name)
