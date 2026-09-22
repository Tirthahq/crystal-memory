#!/usr/bin/env python3
"""
memory-hygiene.py — keeps the memory system findable AND bounded. Wired into state-snapshot.

Two failure modes it guards (the 2026-06-13 design):
  1. UNFINDABLE — a node with no/broken frontmatter never makes the generated NODE-INDEX → invisible.
  2. UNBOUNDED — the ALWAYS-LOADED index (MEMORY.md) grows forever as pointers are added but never retired,
     and node folders sprawl. The long tail belongs in the *generated* NODE-INDEX (queried on demand),
     NOT in the always-loaded MEMORY.md. So MEMORY.md must stay under budget and roll off stale pointers.

Run: python3 scripts/memory-hygiene.py   (exit 0; prints OK or <<< flags for state-snapshot to surface)
"""
import re, sys
from datetime import date
from pathlib import Path

import os
from store_contract import StoreContract, ContractError


def main():
    TODAY = date.today().isoformat()   # ISO strings compare correctly as strings; no parsing needed

    contract = StoreContract()
    contract.require_nodes()
    REPO = contract.root
    MEM = contract.memory_dir
    MEMORY_MD = Path(os.environ["MEMORY_INDEX_FILE"]) if os.environ.get("MEMORY_INDEX_FILE") else None
    if MEMORY_MD and not MEMORY_MD.is_absolute():
        MEMORY_MD = REPO / MEMORY_MD
    if MEMORY_MD:
        contract.require(MEMORY_MD)

    MEMORY_MD_BUDGET = 240   # always-loaded index — over this, roll stale pointers off (they stay in NODE-INDEX)
    # ⛔ CAPS AND POPULATION NOW LIVE IN ONE PLACE: scripts/store_caps.py (the maintainer's call 2026-09-01,
    # "give the one script ownership"). They used to be duplicated here and in node-cleaner.py, whose
    # copy carried `# must match scripts/memory-hygiene.py`. The caps DID match; the POPULATIONS did not,
    # and node-cleaner reported "all node folders within cap ✓" while three folders were over.
    _sc = contract.caps("memory-hygiene")
    FOLDER_CAP = _sc.FOLDER_CAP

    # ── RAISED CAPS — per folder, dated, reasoned, and REVIEWED ────────────────────────────────────────
    # The 2026-08-06 queue review set the standard this implements: when a folder is over cap, either it
    # "passes honestly or is raised with a dated reason rather than by moving files."
    #
    # ⛔ PER-FOLDER, NEVER GLOBAL. Raising FOLDER_CAP itself is the wrong act and it was the first thing
    # tried on 2026-08-15: queued/ needed 49, and moving the global 45 -> 50 would ALSO have silenced
    # memory/business/strategy at 46 — a folder nobody had looked at. **A raise must not travel.**
    #
    # ⛔ AND A RAISE MUST STAY VISIBLE. An off switch nobody can see gets used: a silently raised cap is
    # the same defect as a guard keyed on a field nobody fills — it reports clean forever and no one knows
    # why (crystal-a-guard-keyed-on-a-field-nobody-fills-is-a-silent-no-op). So a raised folder still
    # prints a line every boot, naming the raise, its date and its reason; and it EXPIRES — past review_by
    # the raise flags for re-decision rather than quietly holding.
    #
    # (cap, since, review_by, reason)
    CAP_RAISED = _sc.CAP_RAISED   # owner: scripts/store_caps.py

    flags = []
    notes = []


    def has_frontmatter(p):
        t = p.read_text(encoding="utf-8", errors="ignore")
        if not t.startswith("---"):
            return False
        parts = t.split("---", 2)
        return len(parts) >= 3 and "name:" in parts[1] and "description:" in parts[1]


    # Non-node docs/channels that live in the node folder but intentionally have no frontmatter.
    NON_NODES = {"MEMORY.md", "NODE-INDEX.md", "README.md", "HOW_TO_TASK_ME.md", "inbox.md",
                 # scratchpad.md is WORKING MEMORY, not a node (it carries hypotheses to re-check, not
                 # governed truth) and is surfaced by scripts/scratchpad-boot.py, never by NODE-INDEX.
                 # Giving it frontmatter would make it a node it deliberately is not. Flagged at every
                 # boot since ~2026-07-15; it was always a false positive. IDEA-session-scratchpad-working-memory
                 "scratchpad.md"}
    # Pattern-skipped: generated artifacts (re-rendered from source — frontmatter would be overwritten) and
    # inbox/board channels (kept plain on purpose so they don't themselves trip node-health). These are NOT
    # nodes; flagging them as "unfindable" is a false positive. A board/generated file added later is covered.
    def is_non_node(name):
        return name in NON_NODES or name.endswith(".generated.md") or name.endswith("-inbox.md")

    # 1. FINDABILITY — every node in the primary store must have frontmatter (else build-node-index skips it)
    for p in contract.node_files():
        if is_non_node(p.name):
            continue
        if not has_frontmatter(p):
            flags.append(f"unfindable node (no/invalid frontmatter → skipped by NODE-INDEX): {p.relative_to(REPO)}")

    # 2. DEAD POINTERS — MEMORY.md links that point at a file that no longer exists
    mem_txt = MEMORY_MD.read_text(encoding="utf-8", errors="ignore") if MEMORY_MD else ""
    for m in re.finditer(r"\]\(([^)]+\.md)\)", mem_txt):
        tp = (MEMORY_MD.parent / m.group(1))
        if not tp.exists():
            flags.append(f"MEMORY.md dead pointer → {m.group(1)} (target missing)")

    # 3. BUDGET — the always-loaded index must stay bounded; roll off when over
    nlines = len(mem_txt.splitlines())
    if nlines > MEMORY_MD_BUDGET:
        flags.append(
            f"MEMORY.md is {nlines} lines (budget {MEMORY_MD_BUDGET}) — ROLL OFF: retire stale/superseded pointers "
            f"(node files stay on disk + in the generated NODE-INDEX; they just leave the always-loaded index). "
            f"Use the consolidate-memory skill."
        )

    # 4. FOLDER SPRAWL — too many files in one node folder → consolidate / sub-folder / archive
    #
    # ⛔ EXCEPT where a BETTER instrument already bounds the folder. A flat count is the right guard for
    # hand-written node piles (they become unnavigable). It is the WRONG guard for a folder of REGENERABLE
    # output whose real bound is "obligations we still owe + a rolling window" — there the count is a
    # function of how much live work is open, and no action can lower it. MEASURED 2026-08-09:
    # dev-crystals/replies sat at 52 with `dev-crystal-retention.py` reporting **prune=0** — 41 protected
    # by a mention in a live hand-written node, 5 owed a reply, 6 inside the window. Nothing was rot, and
    # the flat cap had been red for weeks with no action that could clear it.
    # ⚠ A PERMANENTLY-RED CHECK IS WORSE THAN NO CHECK — it trains every session to skim past the surface.
    # So for these folders we ask the OWNING TOOL for its verdict instead of counting. It still FAILS: if
    # the tool finds anything prunable, or cannot be asked, that is a flag in the tool's own words.
    # ⛔ Do NOT add a folder here to silence it. The bar is: a named tool bounds it AND that tool can say no.
    RETENTION_MANAGED = _sc.RETENTION_MANAGED   # owner: scripts/store_caps.py

    _retention_plan = None


    def retention_prunable(rel):
        """(prunable_count, note) from the OWNING tool named by the policy, or (None, why).

        ⛔ THE OWNER IS DATA, NOT A HARDCODED FILENAME (2026-09-22). This used to load
        `scripts/dev-crystal-retention.py` by name — a dev.to-specific tool that has no place in a
        stranger's install, and the last edge tying the maintenance layer to this repo's own scripts.
        `retention_managed` already maps each folder to the script that bounds it, so ask THAT.
        🔑 A foreign store names its own owner, or names none and the whole branch never runs.
        """
        nonlocal _retention_plan
        owner = RETENTION_MANAGED.get(rel)
        if not owner:
            return None, "no retention owner declared for this folder"
        if _retention_plan is None:
            _retention_plan = {}
        if owner not in _retention_plan:
            try:
                import importlib.util
                target = REPO / owner
                if not target.is_file():
                    raise FileNotFoundError(f"retention owner not installed: {owner}")
                spec = importlib.util.spec_from_file_location("_retention_owner", target)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                prune, kept, reasons = mod.plan()
                _retention_plan[owner] = (prune, reasons)
            except Exception as e:                                  # noqa: BLE001 — any failure must FLAG, not pass
                _retention_plan[owner] = (None, f"{type(e).__name__}: {e}")
        prune, reasons = _retention_plan[owner]
        if prune is None:
            return None, reasons
        mine = [p for p in prune if rel in str(Path(p).as_posix())]
        return len(mine), None


    for d in contract.population():
        n = len(list(d.glob("*.md")))
        if n <= FOLDER_CAP:
            continue
        rel = d.relative_to(REPO).as_posix()

        # A RAISED CAP IS A DECISION WITH AN EXPIRY, NOT A MUTE BUTTON. Three outcomes, all of them audible:
        # under the raise ⇒ a note naming the raise + its reason · past review_by ⇒ a flag to re-decide ·
        # over the raise ⇒ the normal flag, showing the raised number so nobody thinks the cap is still 45.
        raised = CAP_RAISED.get(rel)
        if raised:
            cap, since, review_by, reason = raised
            if n <= cap:
                if TODAY > review_by:
                    flags.append(
                        f"folder {rel} has {n} md files under a RAISED cap of {cap} whose review date "
                        f"{review_by} has PASSED — re-decide (raised {since}: {reason})")
                else:
                    notes.append(
                        f"folder {rel}: {n} md files, cap RAISED to {cap} on {since}, review by {review_by} "
                        f"— {reason}")
                continue
            flags.append(
                f"folder {rel} has {n} md files (RAISED cap {cap}, set {since}) — over even the raised cap; "
                f"consolidate / archive stale, or re-decide the raise")
            continue

        owner = RETENTION_MANAGED.get(rel)
        if not owner:
            flags.append(f"folder {rel} has {n} md files (cap {FOLDER_CAP}) — consolidate / sub-folder / archive stale")
            continue
        prunable, why = retention_prunable(rel)
        if prunable is None:
            flags.append(f"folder {rel} has {n} md files and its bound ({owner}) COULD NOT BE ASKED — {why}")
        elif prunable > 0:
            flags.append(f"folder {rel} has {n} md files and {prunable} are prunable — run `python3 {owner} --apply`")

    print("memory-hygiene: OK" if not flags else "memory-hygiene: FLAGS")
    for f in flags:
        print("  <<< " + f)
    # Raised caps print EVERY run, green or not. A raise that stopped being visible would be a mute button,
    # and the whole argument for allowing one is that it is a dated decision somebody can still see and revoke.
    for nline in notes:
        print("  ~~~ " + nline)


if __name__ == "__main__":
    try:
        main()
    except (ContractError, OSError) as error:
        print(f"memory-hygiene: {error}", file=sys.stderr)
        sys.exit(1)
