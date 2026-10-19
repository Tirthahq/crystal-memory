"""Windows-safe I/O conventions, using only the standard library."""
import os
import subprocess

_RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {
    prefix + digit for prefix in ("COM", "LPT") for digit in "123456789¹²³"
}


def reserved_name(name):
    """Device names remain reserved even with extensions, on every host."""
    return name.rstrip(" .").split(".", 1)[0].rstrip(" ").upper() in _RESERVED


def subprocess_options():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
