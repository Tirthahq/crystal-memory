#!/usr/bin/env python3
"""store_caps.py — THE ONE OWNER of "which folders count, and what is their cap".

⛔ WHY THIS EXISTS (the maintainer's call, 2026-09-01: "give the one script ownership").
`memory-hygiene.py` and `node-cleaner.py` both carried `FOLDER_CAP = 45`, and node-cleaner's line
even said `# must match scripts/memory-hygiene.py`. The caps DID match. **The populations did not**,
and the matching comment is what stopped anyone checking:

    node-cleaner   STORES = ["memory/claude","memory/design","memory/research"], os.listdir,
                   NON-recursive  ->  37 / 20 / 25 files, all genuinely under 45  ->  "within cap ✓"
    memory-hygiene MEM.rglob("*"), every sub-directory
                   ->  memory/tasks/queued 60, memory/claude/crystals 83,
                       memory/business/strategy 49  ->  three OVER cap

Every over-cap folder sat OUTSIDE the Cleaner's population: `memory/tasks` and `memory/business` are
not in STORES at all, and `memory/claude/crystals` is a SUB-directory a non-recursive listdir cannot
reach. So the Cleaner's green tick was **true and useless** — it has never once been the thing that
told us a folder was over.

🔑 **THE GENERAL FORM, and it is why this module is a module and not a constant:** sharing a RULE does
not share a POPULATION, and a shared rule makes the disagreement look impossible. Two instruments
described the same folders differently for weeks; the disagreement WAS the diagnosis.

⚠ **THIS MODULE MUST STAY PURE.** No I/O at import, no side effects, no `main()`. Both consumers
import it, and one of them (`node-cleaner.py`) can DELETE AND ARCHIVE FILES under `--apply`. A module
that acts at import time cannot safely be imported by a destructive tool.
"""
import os
from pathlib import Path

import store_policy

REPO = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[1]).resolve()
MEM = REPO / "memory"

# md files per node folder before consolidate/sub-folder (conventions say ~30; headroom)
FOLDER_CAP = 45

# ── RAISED CAPS — per folder, dated, reasoned, and REVIEWED ────────────────────────────────────────
# The 2026-08-06 queue review set the standard this implements: when a folder is over cap it either
# "passes honestly or is raised with a dated reason rather than by moving files."
#
# ⛔ PER-FOLDER, NEVER GLOBAL. Raising FOLDER_CAP itself is the wrong act and it was the first thing
# tried on 2026-08-15: queued/ needed 49, and moving the global 45 -> 50 would ALSO have silenced
# memory/business/strategy at 46 — a folder nobody had looked at. **A raise must not travel.**
#
# ⛔ AND A RAISE MUST STAY VISIBLE. An off switch nobody can see gets used: a silently raised cap is
# the same defect as a guard keyed on a field nobody fills — it reports clean forever and no one knows
# why. So a raised folder still prints a line every boot, naming the raise, its date and its reason;
# and it EXPIRES — past review_by the raise flags for re-decision rather than quietly holding.
#
# ⛔ THE RAISES THEMSELVES NOW LIVE IN `.store-policy.json`, NOT HERE (2026-09-22). They were the
# single largest reason this module could not run in a foreign store: `memory/tasks/queued` is a
# directory THIS repo happens to have, and a raise reasoned about a 2026-08-06 queue review is a
# statement about our history, not about caps. The RULE (per-folder, dated, reasoned, expiring,
# always printed) is the code below and travels; the ROWS are local and do not.
# ⚠ The validator enforces the discipline at the door: a raise with no reason, a `cap: 0`, or a
# malformed date is REFUSED rather than loaded, so the invisible off-switch stays unreachable.
#
# Shape is unchanged for consumers: (cap, since, review_by, reason).


# ── RETENTION-MANAGED FOLDERS — capped by a retention policy, NOT by this cap ──────────────────────
# ⛔ THESE ARE NOT EXEMPT, THEY ARE MEASURED BY A DIFFERENT INSTRUMENT. dev-crystals/replies sat at 52
# with `dev-crystal-retention.py` reporting prune=0 and 41 protected — so a raw cap flag on it is noise
# that trains the reader to ignore the line. The retention script is the authority for these.
# ⚠ FOUND THE HARD WAY 2026-09-01: my first cut of this module omitted them and reported FOUR over-cap
# folders where memory-hygiene reports THREE — `memory/claude/dev-crystals/replies` at 132, over by 87,
# the largest of the lot. I only caught it because I captured memory-hygiene's output as a GOLDEN
# before rewiring anything. A refactor that "obviously preserves behaviour" is a claim, not a fact.
# ⛔ THE ROWS MOVED TO `.store-policy.json` (2026-09-22) FOR THE SAME REASON AS THE RAISES: naming
# `memory/claude/dev-crystals/*` and the script that owns them is a claim about THIS store. The
# distinction they encode — capped by a retention policy rather than by a count — is general and stays.


def __getattr__(name):
    """CAP_RAISED / RETENTION_MANAGED, read on first touch instead of at import.

    ⚠ WHY A MODULE-LEVEL __getattr__ AND NOT TWO CONSTANTS: this module's contract is "no I/O at
    import" (node-cleaner.py imports it and can DELETE under --apply), and its consumers already read
    `_sc.CAP_RAISED` / `_sc.RETENTION_MANAGED` as attributes. PEP 562 lets both hold at once — the
    read happens at first ACCESS, and every existing caller is untouched.
    ⛔ These names must NOT also exist as module globals, or normal lookup wins and this never fires.
    """
    if name == "CAP_RAISED":
        return store_policy.load(REPO).cap_raised
    if name == "RETENTION_MANAGED":
        return store_policy.load(REPO).retention_managed
    if name == "POLICY":
        return store_policy.load(REPO)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_LAZY = ("CAP_RAISED", "RETENTION_MANAGED", "POLICY")
__all__ = ["FOLDER_CAP", "is_node_folder", "node_folders", "cap_for", "over_cap", *_LAZY]


def __dir__():
    """⚠ WITHOUT THIS THE LAZY NAMES ARE INVISIBLE to dir(), tab completion, inspect.getmembers,
    pydoc and every static analyser — PEP 562 hides them from introspection even though attribute
    access works. Flagged in review 2026-09-22; a name that only exists when you already know to ask
    for it is not a public API."""
    return sorted(set(globals()) | set(_LAZY))


def is_node_folder(d: Path, root: Path = None) -> bool:
    """The discovery rule, in ONE place. Mirrors what memory-hygiene has always used.

    ⛔ THE ARCHIVE TEST READS THE WHOLE RELATIVE PATH, NOT THE LEAF NAME (fixed 2026-09-22).
    It used to check `d.name`, so `memory/_archive` was correctly excluded while its CHILDREN —
    `memory/_archive/claw`, `.../ken-era-2026-06`, ten of them — were not, because their leaf names
    are ordinary. Archived history therefore sat inside the population `node-cleaner --apply` acts on.
    📏 Latent, not firing when found: all ten hold 0-9 md files against a cap of 45, and `over_cap`
    listed none of them. That is luck about file counts, not a property of the guard.
    🔑 Found by `test_policy_does_not_widen_mutators.py`, which was written to answer a DIFFERENT
    objection (that an empty policy widens mutators — it does not). The control aimed at one mechanism
    and caught another, which is the argument for writing the control instead of the argument.
    """
    root = root or REPO
    try:
        rel = d.relative_to(root).as_posix()
    except ValueError:
        rel = d.as_posix()
    parts = rel.split("/")
    return (
        d.is_dir()
        and not any(p.startswith("_") for p in parts)
        and not any("archive" in p.lower() for p in parts)
    )


def node_folders(mem: Path = MEM):
    """Every node folder under `mem`, recursively. Yields (path, rel, n_md) sorted by rel."""
    out = []
    for d in mem.rglob("*"):
        if not is_node_folder(d):
            continue
        n = len(list(d.glob("*.md")))
        out.append((d, str(d.relative_to(REPO).as_posix()), n))
    return sorted(out, key=lambda t: t[1])


def cap_for(rel: str):
    """(cap, raise_info_or_None) for a repo-relative folder path.

    ⚠ Reads the policy through the loader, NOT through the module attribute. A module-level
    __getattr__ (PEP 562) is only consulted for attribute access from OUTSIDE; a bare `CAP_RAISED`
    here is an ordinary global lookup and would raise NameError. The two look identical in the source.
    """
    raised = store_policy.load(REPO).cap_raised.get(rel)
    return (raised[0], raised) if raised else (FOLDER_CAP, None)


def over_cap(mem: Path = MEM, include_retention_managed: bool = False):
    """Folders genuinely over their OWN cap. The single answer both consumers must agree with."""
    rows = []
    retention = store_policy.load(REPO).retention_managed   # see cap_for on why not the attribute
    for path, rel, n in node_folders(mem):
        cap, raised = cap_for(rel)
        if n <= cap:
            continue
        managed = retention.get(rel)
        if managed and not include_retention_managed:
            # Not silently dropped — the caller can ask for these, and they are still countable.
            continue
        rows.append({"path": path, "rel": rel, "n": n, "cap": cap, "raised": raised,
                     "over": n - cap, "retention_managed": managed})
    return rows
