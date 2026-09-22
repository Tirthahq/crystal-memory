#!/usr/bin/env python3
"""redact.py — strip credential-shaped strings at DELIVERY. Pure stdlib, no I/O at import.

⛔ WHY THIS EXISTS. Our secret gate is a COMMIT gate: it scans the staged diff and the content of
git-tracked files. Every delivery channel we own sits outside that population:

  · `soul-gardener.py` reads RAW SESSION TRANSCRIPTS, which live outside the repo and are never
    committed, therefore never scanned — and in a stranger's install those transcripts hold THEIR keys.
  · the scratchpad and the crystal essences are injected into a model's context every session; a secret
    pasted into either travels on every future boot until someone notices.
  · an uncommitted or just-edited file is delivered before any commit gate has ever seen it.

**So "the repo is clean" and "the channel is clean" are different claims, and we only checked the
first.** Taken from Memory Crystal (`memorycrystal/memorycrystal`, 2026-09-22), which redacts likely
secrets before returning tool output. Their README is the source of the idea; the implementation and
its controls are ours.

🔑 **THE DESIGN CONSTRAINT THAT MATTERS: A CHANNEL FULL OF `[REDACTED]` IS WORSE THAN NO CHANNEL.**
These essences are prose about engineering, so they legitimately contain hex digests, exit codes,
commit hashes, file paths, base64-looking fragments and the word "key". Over-redaction destroys the
thing being delivered and trains the reader to ignore it. Every pattern here is anchored to a
credential's STRUCTURAL PREFIX (`AKIA`, `sk-ant-`, `ghp_`, `-----BEGIN`) rather than to entropy or to
a keyword, because a prefix cannot match prose by accident and entropy routinely does.

⚠ **THIS IS NOT A SECURITY BOUNDARY AND MUST NOT BE SOLD AS ONE.** It catches KNOWN SHAPES. A novel
credential format, a secret split across lines, or one written in words passes straight through. It
lowers the cost of an accident; it does not make the channel safe to put secrets in.
"""
import re

PLACEHOLDER = "[REDACTED:{kind}]"

# (kind, pattern). Anchored on structural prefixes — see the docstring on why not entropy.
PATTERNS = (
    ("aws-key",      re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("private-key",  re.compile(r"-----BEGIN[ A-Z]*PRIVATE KEY-----.*?-----END[ A-Z]*PRIVATE KEY-----",
                                re.S)),
    ("anthropic",    re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openai",       re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{32,}")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b")),
    ("github-pat",   re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b")),
    ("slack",        re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}")),
    ("google-key",   re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("stripe",       re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("jwt",          re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
    # A URL carrying inline credentials. Deliberately NOT matching bare user@host.
    ("url-cred",     re.compile(r"\b(?P<scheme>[a-z][a-z0-9+.\-]*)://[^\s/:@]+:[^\s/@]+@")),
    # `Authorization: Bearer <token>` — the VALUE only, and only when it is long enough to be one.
    ("bearer",       re.compile(r"(?i)(?P<lead>\bbearer\s+)(?P<tok>[A-Za-z0-9_\-\.=]{24,})")),
)

# ⛔ AN ASSIGNMENT IS NOT A SECRET. `KEY=` matches a shell example, a docs snippet and an env-var NAME
# far more often than a live credential, so an assignment is redacted ONLY when its value also looks
# like one: long, and not an obvious placeholder or a path or a number.
_ASSIGN = re.compile(
    r"(?i)(?P<lead>\b(?:api[_\-]?key|secret|token|passwd|password|access[_\-]?key)\b\s*[:=]\s*)"
    r"(?P<q>[\"']?)(?P<val>[A-Za-z0-9_\-\.+/=]{20,})(?P=q)")
_PLACEHOLDERISH = re.compile(
    r"(?i)^(?:x{3,}|\.{3,}|<.*>|\$\{?[a-z_]+\}?|your[_\-].*|example.*|changeme|redacted|"
    r"[a-z_]*placeholder[a-z_]*|none|null|true|false)$")


def _looks_like_a_value(val):
    """A credential, not a path, a number, an env-var reference or a placeholder."""
    if _PLACEHOLDERISH.match(val):
        return False
    if val.startswith(("/", "./", "~", "$")) or "/" in val and val.count("/") > 1:
        return False          # a path
    if re.fullmatch(r"[0-9.]+", val):
        return False          # a number or a version
    # Needs some variety: a run of one character class is usually a hash we WANT to keep readable
    # (a commit sha, a digest) and those are not credentials.
    return bool(re.search(r"[A-Za-z]", val) and re.search(r"[0-9_\-.+/=]", val))


def redact(text, counter=None):
    """Return `text` with credential-shaped substrings replaced. Never raises on odd input."""
    if not text:
        return text
    if not isinstance(text, str):
        return text
    out = text
    for kind, pattern in PATTERNS:
        def _sub(m, kind=kind):
            if counter is not None:
                counter[kind] = counter.get(kind, 0) + 1
            if kind == "bearer":
                return m.group("lead") + PLACEHOLDER.format(kind=kind)
            if kind == "url-cred":
                return f"{m.group('scheme')}://" + PLACEHOLDER.format(kind=kind) + "@"
            return PLACEHOLDER.format(kind=kind)
        out = pattern.sub(_sub, out)

    def _assign(m):
        if not _looks_like_a_value(m.group("val")):
            return m.group(0)
        if counter is not None:
            counter["assignment"] = counter.get("assignment", 0) + 1
        return m.group("lead") + m.group("q") + PLACEHOLDER.format(kind="assignment") + m.group("q")
    return _ASSIGN.sub(_assign, out)


def redacted_count(text):
    """(redacted_text, {kind: n}) — so a caller can SAY it redacted rather than doing it silently."""
    counter = {}
    return redact(text, counter), counter
