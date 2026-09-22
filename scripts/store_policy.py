#!/usr/bin/env python3
"""store_policy.py — THE ONE OWNER of "which folders are exceptions, and why".

⛔ WHY THIS EXISTS. The maintenance agents' MECHANISM is portable; their POPULATION EXCEPTIONS are not.
`node-health.py` and `store_caps.py` each carried a table of *this repo's own* directories —
`memory/archive`, `memory/ops/reports`, `memory/tasks/queued`, `memory/claude/dev-crystals/*` — and
those literals are the entire reason three of the four maintenance agents die on a clean install
(measured 2026-09-22). They are not structure. They are THIS install's policy, and another install has
different ones, or none at all.

🔑 **A FOREIGN INSTALL WITH NO POLICY FILE IS THE DEFAULT CASE, NOT AN ERROR.** Empty tables, same
mechanism: nothing excluded, no raised caps, nothing retention-managed. The agent still runs, still
scans, still reports. A **missing** file is normal. A **malformed** one FAILS CLOSED, because a policy
that silently read as empty would quietly re-admit archived history into a live scan, or quietly drop a
cap raise that a human reviewed, dated and signed a reason for.

⛔ **AND IT CLOSES A SYNC HAZARD THAT PREDATES PORTABILITY.** The exclusion list lived in BOTH
`node-health.py` and `build-node-index.py`, held together by a comment reading *"KEEP IN SYNC WITH
build-node-index.py SKIP"*. That is the identical shape `store_caps.py` was written to fix — two
instruments sharing a RULE while quietly disagreeing about a POPULATION — and a comment is not a
mechanism. ⚠ The two copies were not even the same literals: node-health wrote `"memory/archive"`,
build-node-index wrote `os.path.join("memory", "archive")`, so the portability gate could see one and
not the other. **One owner now.**

⚠ **THIS MODULE MUST STAY PURE. No I/O at import, no side effects, no `main()`.** `node-cleaner.py`
reaches this through `store_caps` and can DELETE AND ARCHIVE files under `--apply`; a module that acts
at import time cannot safely be imported by a destructive tool. Reads happen on first `load()`, and are
cached against the file's (path, mtime, size) so a long-running agent cannot be re-keyed underneath
itself without noticing.

RESOLUTION ORDER (first hit wins):
  1. `STORE_POLICY_FILE`            — explicit, and a missing file HERE is an error: you asked for it.
  2. `<root>/.store-policy.json`    — the conventional local policy; absent is fine.
  3. nothing                        — the empty policy.
`<root>` is `CLAUDE_PROJECT_DIR` if set, else the repository above this script, matching the convention
`store_contract.py` and `store_caps.py` already use.
"""
import json
import os
import re
from pathlib import Path

DEFAULT_FILENAME = ".store-policy.json"
ENV_VAR = "STORE_POLICY_FILE"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LIST_KEYS = ("excluded_dirs", "archived_dirs")
_MAP_KEYS = ("cap_raised", "retention_managed")
# ⚠ JSON HAS NO COMMENTS, AND UNKNOWN KEYS FAIL CLOSED — so without these two the first thing a tester
# naturally does (annotate their policy, or stamp a version) BRICKS every agent, while deleting the
# file entirely works fine. That asymmetry is indefensible and was flagged in review (2026-09-22).
# They are IGNORED, never interpreted: `version` is reserved for a future migration, `comment`/`_comment`
# are the tester's. Everything else is still refused, so a typo like `excluded_dir` cannot read as empty.
IGNORED_KEYS = ("version", "comment", "_comment")
KEYS = _LIST_KEYS + _MAP_KEYS + IGNORED_KEYS

# ⛔⛔ THE FLOOR. `_archive` IS STRUCTURE, NOT POLICY, AND LEAVING IT OUT BROKE A MUTATOR.
# `node-cleaner.py --retire` MOVES a node to `<store>/_archive/` — that destination is hardcoded in the
# Cleaner — and then verifies the node has left the index. If nothing excludes `_archive`, the indexers
# keep indexing it, the retire does not achieve what it says, and the Cleaner reports
# `REGRESSION — INSPECT` after having already moved the file. MEASURED 2026-09-22 in a foreign store
# with no policy file: exit 2, one file moved, `NODE-INDEX still in index unexpectedly`.
# 🔑 THIS IS THE HONEST FORM OF AN OBJECTION RAISED IN REVIEW — that "empty policy" is not strictly
# conservative. The proposed mechanism (an empty skip list lets a mutator DELETE more) does not hold
# here; this one does, and it is worse in a subtler way: the mutator's operation becomes INCOHERENT
# rather than over-broad. A convention a tool WRITES TO cannot be optional configuration.
# ⚠ The policy EXTENDS this floor and can never remove it.
BUILTIN_EXCLUDED = ("_archive",)

_CAP_FIELDS = ("cap", "since", "review_by", "reason")

_cache = {}


class PolicyError(Exception):
    """The policy file exists and cannot be trusted. Never raised for a missing file."""


class Policy:
    """An immutable answer to 'what are this install's store exceptions'.

    `source` is the file it came from, or None for the empty policy — consumers print it so a surprising
    exclusion can be traced to a line a human wrote, not to a default nobody chose.
    """

    __slots__ = ("excluded_dirs", "archived_dirs", "cap_raised", "retention_managed", "source")

    def __init__(self, excluded_dirs=(), archived_dirs=(), cap_raised=None,
                 retention_managed=None, source=None):
        # The floor is merged in, never replaced, and de-duplicated so a policy that also names
        # `_archive` (ours does) produces the same tuple it always did.
        self.excluded_dirs = tuple(dict.fromkeys(tuple(excluded_dirs) + BUILTIN_EXCLUDED))
        self.archived_dirs = tuple(dict.fromkeys(tuple(archived_dirs) + BUILTIN_EXCLUDED))
        # (cap, since, review_by, reason) — the shape memory-hygiene and node-cleaner already index.
        self.cap_raised = dict(cap_raised or {})
        self.retention_managed = dict(retention_managed or {})
        self.source = source

    @property
    def is_empty(self):
        """No POLICY, i.e. nothing a human chose. The built-in floor does not count as policy."""
        return not (tuple(d for d in self.excluded_dirs if d not in BUILTIN_EXCLUDED)
                    or tuple(d for d in self.archived_dirs if d not in BUILTIN_EXCLUDED)
                    or self.cap_raised or self.retention_managed)

    def describe(self):
        where = self.source or "no policy file (defaults: nothing excluded, no raised caps)"
        return (f"{where}: {len(self.excluded_dirs)} excluded, {len(self.archived_dirs)} archived, "
                f"{len(self.cap_raised)} raised cap(s), {len(self.retention_managed)} retention-managed")


EMPTY = Policy()


def repo_root(root=None):
    return Path(root or os.environ.get("CLAUDE_PROJECT_DIR")
                or Path(__file__).resolve().parents[1]).resolve()


def resolve(root=None):
    """(path, required) for the policy file. `required` means a missing file is an error."""
    explicit = os.environ.get(ENV_VAR)
    if explicit:
        return Path(explicit).expanduser(), True
    return repo_root(root) / DEFAULT_FILENAME, False


def _fail(path, message):
    raise PolicyError(f"{path}: {message}")


def _strings(path, key, value):
    if not isinstance(value, list):
        _fail(path, f"{key} must be a list, got {type(value).__name__}")
    out = []
    for i, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            _fail(path, f"{key}[{i}] must be a non-empty string")
        out.append(item.strip())
    return tuple(out)


def _cap_raised(path, value):
    if not isinstance(value, dict):
        _fail(path, f"cap_raised must be an object, got {type(value).__name__}")
    out = {}
    for rel, spec in value.items():
        if not isinstance(spec, dict):
            _fail(path, f"cap_raised[{rel!r}] must be an object with {list(_CAP_FIELDS)}")
        missing = [f for f in _CAP_FIELDS if f not in spec]
        extra = [f for f in spec if f not in _CAP_FIELDS]
        if missing or extra:
            _fail(path, f"cap_raised[{rel!r}] missing {missing}, unknown {extra}")
        cap = spec["cap"]
        # bool is an int in Python; a `true` here is a typo, not a cap.
        if isinstance(cap, bool) or not isinstance(cap, int) or cap <= 0:
            _fail(path, f"cap_raised[{rel!r}].cap must be a positive integer, got {cap!r}")
        for field in ("since", "review_by"):
            if not isinstance(spec[field], str) or not _DATE_RE.match(spec[field]):
                _fail(path, f"cap_raised[{rel!r}].{field} must be YYYY-MM-DD, got {spec[field]!r}")
        if not isinstance(spec["reason"], str) or not spec["reason"].strip():
            # ⛔ A raise without a reason is the off-switch nobody can see. Refuse it at the door.
            _fail(path, f"cap_raised[{rel!r}].reason must be a non-empty string")
        out[rel] = (cap, spec["since"], spec["review_by"], spec["reason"])
    return out


def _retention_managed(path, value):
    if not isinstance(value, dict):
        _fail(path, f"retention_managed must be an object, got {type(value).__name__}")
    out = {}
    for rel, owner in value.items():
        if not isinstance(owner, str) or not owner.strip():
            _fail(path, f"retention_managed[{rel!r}] must name the owning script")
        out[rel] = owner.strip()
    return out


def parse(text, path="<policy>"):
    """Validate policy TEXT. Pure: no filesystem access, so the selftest needs no fixture files."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        _fail(path, f"invalid JSON: {error}")
    if not isinstance(data, dict):
        _fail(path, f"top level must be an object, got {type(data).__name__}")
    unknown = sorted(k for k in data if k not in KEYS)
    if unknown:
        # ⛔ NOT ignored. A mistyped key that silently reads as empty is the same defect as a guard
        # keyed on a field nobody fills: it reports clean forever and nobody learns why.
        _fail(path, f"unknown key(s) {unknown}; known keys are {list(KEYS)}")
    return Policy(
        excluded_dirs=_strings(path, "excluded_dirs", data.get("excluded_dirs", [])),
        archived_dirs=_strings(path, "archived_dirs", data.get("archived_dirs", [])),
        cap_raised=_cap_raised(path, data.get("cap_raised", {})),
        retention_managed=_retention_managed(path, data.get("retention_managed", {})),
        source=str(path),
    )


def load(root=None, use_cache=True):
    """The install's policy. Missing conventional file => EMPTY. Malformed => PolicyError."""
    path, required = resolve(root)
    try:
        stat = path.stat()
    except FileNotFoundError:
        if required:
            _fail(path, f"{ENV_VAR} names a policy file that does not exist")
        return EMPTY
    except OSError as error:
        _fail(path, f"cannot stat policy file: {error}")
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if use_cache and key in _cache:
        return _cache[key]
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        _fail(path, f"cannot read policy file: {error}")
    policy = parse(text, path)
    if use_cache:
        _cache.clear()
        _cache[key] = policy
    return policy
