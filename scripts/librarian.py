#!/usr/bin/env python3
"""librarian.py — the Librarian: the self-reference organ for the MEMORY store.

Mirror of the watchdog (the self-reference organ for the LOOPS). Where the watchdog keeps the
fleet's loops from going dark, the Librarian keeps the knowledge store NAVIGABLE — so a session is
GUIDED, never has to reconstruct the picture, and never trusts a rotted sign. (the-heart-of-the-system
vimarśa; spec: WAYFINDING-signs-all-over.)

It does NOT reimplement detection — it is the ONE RUNNER over MANY single-responsibility eyes (one source of
truth per dimension, no scanner drift). Coverage + per-step come from the runner, so nothing gets "missed a lot"
the way the one-off wiki/sources-only backfill did (the maintainer, 2026-07-08: node management on each step, not an
afterthought; a librarian over more area):
  - node-health.py       → links/paths (dangling [[links]], broken backtick paths, stale/unstamped)
  - node-corrector.py    → repair (CONFIDENT path relocations auto; dangling links = human-adopted hints)
  - node-cleaner.py      → prune (folder caps → archive, cap-exempt, still indexed)
  - build-node-index.py  → catalog (regenerate NODE-INDEX.md, the card catalog)
  - node-lifecycle.py    → lifecycle (active/superseded/deprecated + last_verified freshness)   [SIBLING_CHECKS]
  - check-node-hex-drift.py → token rot (active nodes teaching gate-banned pre-warm hexes as current)
  - node-indexability.py → findability (design nodes w/o frontmatter) + size (oversize → silent RAG-skip)
status + run REPORT every eye; guard --staged BLOCKS new rot across every eye (added-lines / new nodes only).

Subcommands:
  status              catalog health at a glance (counts; exit 1 if dangling/broken present)
  repair [--apply]    node-corrector pass (propose → board; --apply applies CONFIDENT relocations)
  guard  --staged     COMMIT-GATE mode: block a commit that ADDS a new dangling link / broken path
                      (added-lines only, like the hex/font gates — pre-existing rot never blocks)
  run                 the scheduled pass: status + repair-propose + refresh catalog → report to stdout

The guard reuses node-health's resolvable set + regexes so the wall and the report can never disagree.
"""
import argparse, datetime, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from store_contract import StoreContract, ContractError

contract = None
nh = None
REPO = None

# Core work is REQUIRED; the repository-specific extra eyes are OPTIONAL.
# Every dependency appears here exactly once, including guard-only checks.
SCRIPT_REQUIREMENTS = {
    "node-health.py": True,
    "node-corrector.py": True,
    "build-node-index.py": True,
    "rag-refresh.py": False,
    "node-lifecycle.py": False,
    "check-node-hex-drift.py": False,
    "node-indexability.py": False,
    "crystal-freshness.py": False,
    "crystal_delivery_audit.py": False,
    "reconcile-working-memory.py": False,
    "check-task-status-vs-folder.py": False,
    "check-crystal-twin.py": False,
}
COMMAND = "librarian"


def _script_run(script, *args):
    return contract.run_script(script, COMMAND, *args, required=SCRIPT_REQUIREMENTS[script])


def _run(args):
    result = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    if result.returncode:
        raise ContractError(f"{COMMAND}: command failed (exit {result.returncode}): {result.stderr.strip()}")
    return result


# ── The MANY EYES the Librarian composes (single-responsibility sibling checks) ────────────────
# The Librarian is the ONE RUNNER: it invokes each eye over the WHOLE store (status/run) and at
# commit-time (guard) — so no dimension gets "missed a lot" the way the one-off, wiki/sources-only,
# dead-Windows-path backfill did. Add an eye = one entry here; coverage + per-step come for free.
# (the maintainer, 2026-07-08: "node management on each step, not an afterthought" + "a librarian over more area".)
SIBLING_CHECKS = [
    ("node-lifecycle.py", "lifecycle (status/freshness)"),
    ("check-node-hex-drift.py", "token rot (gate-banned hexes taught as current)"),
    ("node-indexability.py", "indexability (frontmatter findability + oversize RAG-skip)"),
    ("crystal-freshness.py", "crystal drift (contradiction eye v0: essence vs mint_from source)"),
    ("crystal_delivery_audit.py", "crystal delivery (cannot-fire-by-construction + stale never-delivered)"),
    ("reconcile-working-memory.py", "reconciler (working memory holding unfiled/duplicated knowing)"),
    ("check-task-status-vs-folder.py", "phantom-done (completed tasks that still read as pending)"),
]


def _sibling_oneline(script):
    r = _script_run(script, "--oneline")
    return (r.stdout or r.stderr).strip(), r.returncode


def _sibling_staged(script):
    r = _script_run(script, "--staged")
    return (r.stdout or r.stderr).strip(), r.returncode


# ── Signs (the Librarian as the SIGN PERSON) ──────────────────────────────────
# Generated wayfinding that CANNOT rot (the whole lesson of WAYFINDING-signs-all-over:
# an unreliable sign is scarier than no sign — so signs must be generated, not hand-typed).
# The flagship sign: a per-node BACKLINKS footer — "↩ Referenced by …" — so you land on a
# node and instantly see what points AT it (you-are-here in the link graph). Idempotent:
# the block lives between markers and is re-painted each run.
SIGN_OPEN = "<!-- LIBRARIAN:signs (generated — re-run: python scripts/librarian.py signs; do not hand-edit) -->"
SIGN_CLOSE = "<!-- /LIBRARIAN:signs -->"
SIGN_BLOCK_RE = re.compile(re.escape(SIGN_OPEN) + r".*?" + re.escape(SIGN_CLOSE) + r"\n?", re.S)
SIGN_DISPLAY_CAP = 15
# Put signs on LIVE knowledge nodes only — never on history (snapshots), generated indexes,
# root governance, or the pinned soul-channel prose (those are sacred / not navigational nodes).
SIGN_SKIP_SUBSTR = ("raw/sessions", "archive", "tasks/done")
SIGN_SKIP_ROOT = {"CLAUDE.md", "RECOVERY.md", "DESIGN.md", "PIPELINE.md", "goodmorning.md"}


def _node_name(f, txt=None):
    if txt is None:
        txt = open(f, encoding="utf-8", errors="ignore").read()
    m = nh.NAME_RE.search(txt)
    return (m.group(1).strip().strip('"') if m else os.path.splitext(os.path.basename(f))[0])


def _injectable(f, head):
    rel = os.path.relpath(f, REPO)
    if any(s in rel for s in SIGN_SKIP_SUBSTR):
        return False
    if rel in SIGN_SKIP_ROOT:
        return False
    if os.path.basename(f) in ("MEMORY.md",) or f.endswith("_INDEX.md"):
        return False
    if "pin: true" in head:  # pinned soul-channel prose — leave it untouched
        return False
    return True


def cmd_signs():
    files = nh.node_files()
    # canonical lowercased target -> (file, display-name)
    target = {}
    name_of = {}
    for f in files:
        txt = open(f, encoding="utf-8", errors="ignore").read()
        nm = _node_name(f, txt)
        name_of[f] = nm
        m = nh.NAME_RE.search(txt)
        if m:
            target[m.group(1).strip().strip('"').lower()] = f
        target.setdefault(os.path.splitext(os.path.basename(f))[0].lower(), f)
    # reverse graph: target-file -> set(source-files)
    backlinks = {}
    for f in files:
        txt = open(f, encoding="utf-8", errors="ignore").read()
        if "wiki/schema" in os.path.relpath(f, REPO):
            continue
        # CRITICAL: strip our OWN generated sign block before counting outbound links —
        # else the footer's [[backlinks]] are read back as real links and the graph grows
        # every run (the idempotency bug). The sign reflects the graph; it must not feed it.
        txt = SIGN_BLOCK_RE.sub("", txt)
        for link in set(nh.LINK_RE.findall(txt)):
            t = link.strip().lower()
            if t in nh.PLACEHOLDERS or "\\" in t or "'" in t:
                continue
            tf = target.get(t)
            if tf and tf != f:
                backlinks.setdefault(tf, set()).add(f)
    painted, cleared = 0, 0
    for f in files:
        head = open(f, encoding="utf-8", errors="ignore").read(400)
        if not _injectable(f, head):
            continue
        txt = open(f, encoding="utf-8", errors="ignore").read()
        srcs = sorted({name_of[s] for s in backlinks.get(f, ())}, key=str.lower)
        if srcs:
            shown = srcs[:SIGN_DISPLAY_CAP]
            extra = f" · +{len(srcs) - SIGN_DISPLAY_CAP} more" if len(srcs) > SIGN_DISPLAY_CAP else ""
            line = f"↩ **Referenced by** ({len(srcs)}): " + " · ".join(f"[[{s}]]" for s in shown) + extra
            block = f"{SIGN_OPEN}\n{line}\n{SIGN_CLOSE}\n"
            if SIGN_BLOCK_RE.search(txt):
                new = SIGN_BLOCK_RE.sub(block, txt)
            else:
                new = txt.rstrip("\n") + "\n\n" + block
            if new != txt:
                open(f, "w", encoding="utf-8").write(new)
                painted += 1
        else:
            # no backlinks now — remove a stale sign if one is present
            if SIGN_BLOCK_RE.search(txt):
                open(f, "w", encoding="utf-8").write(SIGN_BLOCK_RE.sub("", txt).rstrip("\n") + "\n")
                cleared += 1
    print(f"librarian signs: painted {painted} backlink sign(s); cleared {cleared} stale; "
          f"{len(backlinks)} nodes have inbound links.")
    return 0


def _staged_md():
    """Staged memory/*.md + root governance markdown (added/copied/modified)."""
    out = _run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"]).stdout
    keep = []
    for rel in out.splitlines():
        rel = rel.strip()
        if not rel.endswith(".md"):
            continue
        if rel.endswith("NODE-INDEX.md"):
            continue
        if any(s in rel for s in nh.SKIP):
            continue
        if rel.startswith("memory/") or rel in (
            "CLAUDE.md", "RECOVERY.md", "DESIGN.md", "PIPELINE.md", "goodmorning.md"):
            keep.append(rel)
    return keep


def _added_lines(rel):
    """The '+' lines a commit ADDS to one file (no context, no +++ header)."""
    out = _run(["git", "diff", "--cached", "-U0", "--", rel]).stdout
    return [ln[1:] for ln in out.splitlines() if ln.startswith("+") and not ln.startswith("+++")]


def cmd_guard(staged):
    if not staged:
        print("librarian guard: only --staged mode is supported", file=sys.stderr)
        return 2
    # ⛔ A MERGE ADDS NO LINES, IT MOVES COMMITS (2026-09-03, merging a 1955-commit lane into main).
    # `_added_lines` diffs against the CURRENT branch, so every line the lane ever wrote reads as added
    # the moment it reaches main — here, 22 dangling links and ~40 broken `scratch/` paths, all of them
    # already gated on the commits that wrote them. Same population defect as the new-guard gate fixed
    # in c81d4a1f. ⚠ Announced, never silent: a skip nobody can see is an off switch.
    if subprocess.run(["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"],
                      cwd=REPO, capture_output=True, text=True, check=False).returncode == 0:
        print("pre-commit: wayfinding gate SKIPPED — merge commit "
              "(these lines were gated on the commits that wrote them)")
        return 0
    files = _staged_md()
    if not files:
        return 0
    resolvable = nh.build_resolvable(nh.node_files())
    new_dangling, new_broken = [], []
    for rel in files:
        # wiki/schema documents the [[ ]] convention by example — node-health skips it; match that.
        check_links = "wiki/schema" not in rel
        # task specs (memory/tasks/) name their not-yet-created OUTPUT files — forward-refs, skip broken-path.
        check_broken = not rel.replace(os.sep, "/").startswith("memory/tasks/")
        fdir = os.path.dirname(os.path.join(REPO, rel))
        for line in _added_lines(rel):
            if check_links:
                for link in nh.LINK_RE.findall(line):
                    t = link.strip().lower()
                    if t in nh.PLACEHOLDERS or "\\" in t or "'" in t:
                        continue
                    if t not in resolvable:
                        new_dangling.append((rel, link.strip()))
            if check_broken:
                for path in nh.PATH_RE.findall(line):
                    if ("/" in path
                            and not os.path.exists(os.path.join(REPO, path))
                            and not os.path.exists(os.path.join(fdir, path))):
                        new_broken.append((rel, path))
    # tombstones: a commit that re-touches KNOWN historical rot (acknowledged baseline) must not block;
    # only genuinely NEW rot does. node-health owns the list so the wall + the report can't disagree.
    acked_paths, acked_links = nh.load_tombstones()
    new_broken = [(r, p) for r, p in new_broken if p not in acked_paths]
    new_dangling = [(r, l) for r, l in new_dangling if l.strip().lower() not in acked_links]
    blocked = 0
    if new_dangling or new_broken:
        blocked = 1
        print("")
        print("  COMMIT BLOCKED -- this commit ADDS rotted signs (a Librarian guard, rule 6):")
        for rel, l in new_dangling:
            print(f"    dangling [[{l}]]  in {rel}  (matches no node name/slug)")
        for rel, p in new_broken:
            print(f"    broken path `{p}`  in {rel}  (no such file from repo root or the file's own dir)")
        print("  Fix: point each to a real node/path, or remove it. New nodes? write the target first.")
    else:
        print("pre-commit: wayfinding gate PASS (no new dangling links / broken paths)")
    # the composed staged eyes — each blocks only on NEW rot it owns (added-lines / new nodes)
    # check-crystal-twin is ADVISORY BY DESIGN — it prints and never sets `blocked` (its own rc is
    # always 0). A similarity gate that BLOCKS would punish dense, well-linked writing, where a
    # genuinely distinct knowing is lexically close to its neighbour. It speaks; the author decides.
    for script in ("check-node-hex-drift.py", "node-indexability.py", "check-crystal-twin.py",
                   "crystal_delivery_audit.py"):
        line, rc = _sibling_staged(script)
        if line:
            print("  " + line if rc else line)
        if rc:
            blocked = 1
    if blocked:
        print("  (False positive? git commit --no-verify after verifying.)")
    return 1 if blocked else 0


def cmd_status():
    # Run the original scanner with contract-bound inputs and unchanged decisions.
    status = 0
    old_argv = sys.argv
    try:
        sys.argv = ["node-health.py"]
        try:
            nh.main()
        except SystemExit as result:
            status = result.code or 0
    finally:
        sys.argv = old_argv
    for script, _desc in SIBLING_CHECKS:
        line, rc = _sibling_oneline(script)
        status = status or rc
        if line:
            print("  " + line)
    return status


def cmd_repair(apply):
    args = []
    if apply:
        args.append("--apply")
    r = _script_run("node-corrector.py", *args)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    return r.returncode


def cmd_tombstone_prune(apply):
    """Drop acknowledgements that have HEALED — the target now resolves, or the file now exists.

    ⛔ WHY THIS IS NOT COSMETIC: an acknowledged entry is EXEMPT FROM THE COMMIT GATE. Once its target
    is real again, the exemption stops describing history and becomes a live hole — that exact name can
    break tomorrow and the gate will stay silent, because it is on the amnesty list.
    Measured 2026-08-10, right after archived nodes became resolvable: 11 of 21 acked links and 63 of
    205 acked paths had healed. A tombstone is a record of what CANNOT be fixed; anything fixed must
    leave it, or the amnesty outlives the crime."""
    paths, links = nh.load_tombstones()
    resolvable = nh.build_resolvable(nh.node_files())
    healed_links = {l for l in links if l.strip().lower() in resolvable}
    healed_paths = {p for p in paths if os.path.exists(os.path.join(REPO, p))}
    if not (healed_links or healed_paths):
        print("librarian tombstone --prune: nothing healed; every acknowledgement still describes real rot")
        return 0
    print(f"librarian tombstone --prune: {len(healed_paths)} path(s) + {len(healed_links)} link(s) have healed")
    for l in sorted(healed_links):
        print(f"    [[{l}]]  now resolves")
    for p in sorted(healed_paths)[:10]:
        print(f"    {p}  now exists")
    if len(healed_paths) > 10:
        print(f"    … and {len(healed_paths) - 10} more path(s)")
    if not apply:
        print("  (dry run — re-run with --apply to remove them from the tombstone)")
        return 0
    kept = []
    for line in open(nh.TOMBSTONE_FILE, encoding="utf-8").read().splitlines():
        s = line.strip()
        if s.startswith("[[") and s.endswith("]]") and s[2:-2].strip().lower() in healed_links:
            continue
        if s and not s.startswith("#") and not s.startswith("[[") and s in healed_paths:
            continue
        kept.append(line)
    stamp = datetime.date.today().isoformat()
    kept.append(f"\n# pruned {len(healed_paths)} healed paths + {len(healed_links)} healed links ({stamp})")
    with open(nh.TOMBSTONE_FILE, "w", encoding="utf-8") as fh:
        fh.write("\n".join(kept) + "\n")
    after_paths, after_links = nh.load_tombstones()
    print(f"  pruned. acknowledged now {len(after_paths)} paths + {len(after_links)} links "
          f"(was {len(paths)} + {len(links)})")
    return 0


def cmd_tombstone(ack_current):
    """List acknowledged rot, or --ack-current to fold the CURRENT broken-path + dangling baseline
    into the tombstone, so status/guard then surface only NEW regressions (not historical noise)."""
    paths, links = nh.load_tombstones()
    if not ack_current:
        print(f"librarian tombstones: {len(paths)} paths + {len(links)} links acknowledged")
        print(f"  file: {nh.TOMBSTONE_FILE}")
        return 0
    files = nh.node_files()
    resolvable = nh.build_resolvable(files)
    dangling, broken, _, _ = nh.scan(files, resolvable, datetime.date.today(), 120)
    new_paths = {p for _, p in broken} - paths
    new_links = {l.strip().lower() for _, l in dangling} - links
    if not (new_paths or new_links):
        print("librarian tombstone: nothing new — the baseline is already acknowledged")
        return 0
    os.makedirs(os.path.dirname(nh.TOMBSTONE_FILE), exist_ok=True)
    fresh = not os.path.exists(nh.TOMBSTONE_FILE)
    with open(nh.TOMBSTONE_FILE, "a", encoding="utf-8") as fh:
        if fresh:
            fh.write("# Librarian tombstones — KNOWN, un-fixable rot (the historical baseline).\n")
            fh.write("# Excluded from the ACTIONABLE node-health counts + the commit gate so only NEW\n")
            fh.write("# regressions surface. Plain path = broken backtick path; [[name]] = dangling link.\n")
            fh.write("# Re-seed with: python3 scripts/librarian.py tombstone --ack-current\n")
        stamp = datetime.date.today().isoformat()
        if new_paths:
            fh.write(f"\n# acknowledged {len(new_paths)} broken paths ({stamp})\n")
            for p in sorted(new_paths):
                fh.write(p + "\n")
        if new_links:
            fh.write(f"\n# acknowledged {len(new_links)} dangling links ({stamp})\n")
            for l in sorted(new_links):
                fh.write(f"[[{l}]]\n")
    print(f"librarian tombstone: acknowledged {len(new_paths)} paths + {len(new_links)} links "
          f"-> {nh.TOMBSTONE_FILE}")
    return 0


def cmd_run():
    print("=== LIBRARIAN run ===")
    print("\n[1/5] catalog health")
    status = cmd_status()
    print(f"\n[2/5] repair: auto-apply CONFIDENT relocations (board -> {contract.memory_dir / 'corrector-inbox.md'})")
    status = cmd_repair(apply=True) or status
    print("\n[3/5] put up the signs (generated backlinks — can't rot)")
    status = cmd_signs() or status
    print("\n[4/5] refresh the card catalog (NODE-INDEX.md)")
    r = _script_run("build-node-index.py")
    sys.stdout.write(r.stdout[-500:] if len(r.stdout) > 500 else r.stdout)
    # [5/5] added 2026-08-14. The SEMANTIC catalog was the one the Librarian never tended: the store
    # is a card catalog too, and nothing on this machine had EVER refreshed it — `semantic-health.py`
    # asked "auto-refresh dead?" for weeks against a refresher that was never born, and the store went
    # 2.8 days stale in the open. The lexical index (step 4) and the semantic one now age together.
    # rag-refresh pushes its own alert on failure and verifies by the store's artifact, not our exit
    # code; a raise here must never take the rest of the Librarian's daily pass down with it.
    print("\n[5/5] refresh the semantic catalog (the RAG store)")
    try:
        r = _script_run("rag-refresh.py")
        sys.stdout.write(r.stdout[-800:] if len(r.stdout) > 800 else r.stdout)
    except Exception as e:
        raise ContractError(f"librarian run: semantic refresh failed: {e}") from e
    print("=== LIBRARIAN run complete ===")
    return status


def main():
    ap = argparse.ArgumentParser(description="The Librarian — keeps the memory store navigable.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    pr = sub.add_parser("repair"); pr.add_argument("--apply", action="store_true")
    pg = sub.add_parser("guard"); pg.add_argument("--staged", action="store_true")
    sub.add_parser("signs")
    pt = sub.add_parser("tombstone")
    pt.add_argument("--ack-current", action="store_true")
    pt.add_argument("--prune", action="store_true",
                    help="drop acknowledgements whose target now resolves/exists (they are live gate holes)")
    pt.add_argument("--apply", action="store_true", help="with --prune: actually rewrite the tombstone")
    sub.add_parser("run")
    a = ap.parse_args()
    global contract, nh, REPO, COMMAND
    COMMAND = f"librarian {a.cmd}"
    contract = StoreContract()
    contract.require_nodes()
    nh = contract.health(COMMAND)
    REPO = str(contract.root)
    if a.cmd in ("repair", "run"):
        contract.script("node-corrector.py", COMMAND)
    if a.cmd == "run":
        contract.script("build-node-index.py", COMMAND)
    if a.cmd == "status":
        sys.exit(cmd_status())
    elif a.cmd == "repair":
        sys.exit(cmd_repair(a.apply))
    elif a.cmd == "guard":
        sys.exit(cmd_guard(a.staged))
    elif a.cmd == "signs":
        sys.exit(cmd_signs())
    elif a.cmd == "tombstone":
        sys.exit(cmd_tombstone_prune(a.apply) if a.prune else cmd_tombstone(a.ack_current))
    elif a.cmd == "run":
        sys.exit(cmd_run())


if __name__ == "__main__":
    try:
        main()
    except (ContractError, OSError) as error:
        print(f"librarian: {error}", file=sys.stderr)
        sys.exit(1)
