"""Agent-independent, read-only act matching. No shell, model or service required."""
from pathlib import Path

__version__ = "0.1.0"
ACTS = ("bash", "write", "commit", "prompt", "boot", "delegate")


def match(act, text, *, store=None, target="", who="all"):
    """Return matching knowing dictionaries, before delivery budgets/backoff.

    store is the project directory containing memory/. Defaults to the working
    directory; CRYSTAL_STORE_ROOT retains the legacy explicit store override.
    No ledger is read or written, and discriminator commands are never executed.
    The result includes path, bindings, essence and any expiry marker.
    """
    from .act import candidates, _redacted
    if act not in ACTS:
        raise ValueError("act must be one of: " + ", ".join(ACTS))
    if not isinstance(text, str) or not isinstance(target, str):
        raise TypeError("text and target must be strings")
    if who not in ("all", "frontier", "7b", "resident"):
        raise ValueError("invalid reader")
    root = Path(store or Path.cwd()).resolve()
    if not (root / "memory").is_dir():
        import os
        if not os.environ.get("CRYSTAL_STORE_ROOT"):
            raise ValueError(f"store has no memory directory: {root}")
    return [dict(c, essence=_redacted(c["essence"]))
            for c in candidates(act, ctx=text, target=target, who=who, repo=root)]
