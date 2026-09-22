#!/usr/bin/env python3
"""node-cleaner.py — the Cleaner (NB14), the out-of-band store-curation agent.

Part of the directory-agents fleet (directory-agents-architecture). One engine, two policies:
  - CONSOLIDATE (cap relief): move long-tail nodes to `<store>/archive/` — cap-EXEMPT yet STILL INDEXED
    (build-node-index only prunes the literal `_archive`/`memory/archive` SKIP tokens), so they leave the
    working folder but stay findable in NODE-INDEX. (Requires node-health to also scan `archive/` — see the
    archive-reconciliation fix; until then, prefer --retire for testing.)
  - RETIRE (true removal): move explicitly-named dead/superseded nodes to `<store>/_archive/` — excluded by
    BOTH build-node-index AND node-health, i.e. gone from the live system. Inbound path refs are rewritten to
    the new location so they still resolve; inbound `[[wikilinks]]` to a retired node are REPORTED (they will
    dangle — a retired node shouldn't be linked from a live one).

Principles it honors (also product principles — "one architecture, two stores"):
  - DETERMINISTIC, zero-LLM: every move + every reference rewrite is computed exactly.
  - GATED: `--plan` (default) reports and changes NOTHING. `--apply` executes, then VERIFIES with node-health
    and refuses to leave NEW rot (compares the exact issue set before/after, not coarse counts).
  - LOSSLESS: nodes are never deleted, only moved. `[[wikilinks]]` are name-based, immune to path moves.
  - STORE-AGNOSTIC: STORES config below; the same engine is meant to later run over the code store.

Usage:
  python scripts/node-cleaner.py --retire memory/wiki/<retired-node>.md      # plan: report, change nothing
  python scripts/node-cleaner.py --retire memory/wiki/<retired-node>.md --apply
  python scripts/node-cleaner.py                       # plan: consolidate over-cap folders (report only)
  python scripts/node-cleaner.py --consolidate --apply
Run out-of-band (cron/daemon); report compactly to memory/claude/inbox.md for Claude QC.
"""
import os, re, sys, subprocess, datetime

from pathlib import Path
from store_contract import StoreContract, ContractError

contract = None
REPO = None
_sc = None
STORES = ()
# Population belongs to store_contract; both hygiene and Cleaner consume it.
# Caps/dated raises remain owned by store_caps. Its recursive node_folders()
# cannot authorize mutations: only the published directory allowlist can.

NON_NODES = {"MEMORY.md", "NODE-INDEX.md", "README.md", "HOW_TO_TASK_ME.md", "inbox.md"}

MD_LINK_RE = re.compile(r"\]\(([^)]+?\.md)\)")            # ](path.md)  — relative to the referencing file
TICK_PATH_RE = re.compile(r"`([A-Za-z0-9_./-]+\.md)`")   # `path.md`   — repo-relative, then file-relative
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")              # [[name]] / [[name|alias]] / [[name#sec]]
NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.M)
PIN_RE = re.compile(r"^pin:\s*true\b", re.M | re.I)       # frontmatter `pin: true` (+ optional inline comment) → never auto-archive
# `tier: governance` → foundational, never auto-archive.
# ⛔ The `(?:#.*)?` is load-bearing and was added 2026-08-11. This pattern used to end in `\s*$`,
# so `tier: governance  # foundational` did NOT match while `pin: true  # ...` DID (PIN_RE ends in
# \b). 47 nodes here already comment their `pin:` line, so commenting frontmatter is house style —
# the first person to do it on a `tier:` line would have silently lost the wall. Latent, not live:
# zero nodes carried such a comment when this was found. Guarded by test_node_cleaner_walls.py,
# which was watched RED on this exact case before the fix.
# ⚠ NOT `\b` — that would also match `tier: governance-lite`. The negative control pins this.
GOV_RE = re.compile(r"^tier:\s*governance\s*(?:#.*)?$", re.M | re.I)


def sh(*args):
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True)


def read(p):
    return open(p, encoding="utf-8", errors="ignore").read()


def has_frontmatter(p):
    try:
        t = read(p)
    except Exception:
        return False
    if not t.startswith("---"):
        return False
    parts = t.split("---", 2)
    return len(parts) >= 3 and "name:" in parts[1] and "description:" in parts[1]


def is_pinned(p):
    """A node with `pin: true` in frontmatter is load-bearing and is never auto-archived."""
    try:
        return bool(PIN_RE.search(read(p)))
    except Exception:
        return False


def is_governance(p):
    """A `tier: governance` node is FOUNDATIONAL — never auto-archived, regardless of pin.

    This is an INTRINSIC wall: it does not depend on the node being referenced from any index the
    cleaner happens to scan. The real session boot index lives OUTSIDE this repo
    (~/.claude/projects/<proj>/memory/MEMORY.md) and is invisible to boot_protected(); a foundational
    node referenced only from there would otherwise be swept (this is exactly what happened to
    earn-your-footprint and noise-as-diagnostic, 2026-06-20). Tier is on the node itself, so the
    protection holds no matter who can or can't see the index. (guards-over-rules, systems-over-memory.)
    """
    try:
        return bool(GOV_RE.search(read(p)))
    except Exception:
        return False


def node_name(p):
    try:
        m = NAME_RE.search(read(p))
        return m.group(1).strip() if m else None
    except Exception:
        return None


def all_md(base):
    return [str(p) for p in contract.node_files() if p.parent == Path(base)]


def all_ref_sources():
    # Reference rewrites are mutations too: never widen them via a recursive walk.
    return [str(p) for p in contract.node_files()]


def resolve(ref, src_dir, tick):
    cands = []
    if tick:
        cands.append(os.path.normpath(os.path.join(REPO, ref)))        # repo-relative
    cands.append(os.path.normpath(os.path.join(src_dir, ref)))         # file-relative
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def new_ref(new_abs, src_path, tick):
    if tick:
        return os.path.relpath(new_abs, REPO).replace("\\", "/")
    return os.path.relpath(new_abs, os.path.dirname(src_path)).replace("\\", "/")


def compute_rewrites(moved_map, sources):
    """For every source, find inbound path refs that resolve into moved_map; return rewrite tokens."""
    rewrites = []        # (src_path, old_token, new_token)
    for src in sources:
        try:
            txt = read(src)
        except Exception:
            continue
        sdir = os.path.dirname(src)
        for rx, tick in ((MD_LINK_RE, False), (TICK_PATH_RE, True)):
            for m in rx.finditer(txt):
                tgt = resolve(m.group(1), sdir, tick)
                if tgt and tgt in moved_map:
                    nr = new_ref(moved_map[tgt], src, tick)
                    old_tok, new_tok = m.group(0), m.group(0).replace(m.group(1), nr)
                    if old_tok != new_tok:
                        rewrites.append((src, old_tok, new_tok))
    return rewrites


def inbound_wikilinks(moved_paths, sources):
    """Live nodes whose [[wikilink]] targets a node being retired (these will dangle — report them)."""
    targets = {node_name(p) for p in moved_paths}
    targets.discard(None)
    hits = []
    for src in sources:
        if src in moved_paths:
            continue
        try:
            txt = read(src)
        except Exception:
            continue
        for m in WIKILINK_RE.finditer(txt):
            if m.group(1).strip() in targets:
                hits.append((os.path.relpath(src, REPO), m.group(1).strip()))
    return hits


def health_issues():
    """The exact set of node-health problem lines (each 'file -> ref'). Diffable before/after."""
    nh = contract.health("cleaner verify")
    files = nh.node_files()
    dangling, broken, _, _ = nh.scan(files, nh.build_resolvable(files), datetime.date.today(), 120)
    acked_paths, acked_links = nh.load_tombstones()
    return {f"{rel}  ->  [[{name}]]" for rel, name in dangling
            if name.strip().lower() not in acked_links} | {
        f"{rel}  ->  {path}" for rel, path in broken if path not in acked_paths}


def do_move(moves, rewrites):
    edits = {}
    for src, old_tok, new_tok in rewrites:
        edits.setdefault(src, []).append((old_tok, new_tok))
    for src, subs in edits.items():
        txt = read(src)
        for old_tok, new_tok in subs:
            txt = txt.replace(old_tok, new_tok)
        open(src, "w", encoding="utf-8").write(txt)
    for old, new in moves:
        os.makedirs(os.path.dirname(new), exist_ok=True)
        r = sh("git", "mv", os.path.relpath(old, REPO), os.path.relpath(new, REPO))
        if r.returncode != 0:
            os.rename(old, new)
    contract.run_script("build-node-index.py", "cleaner apply")


def run(moves, rewrites, wikis, apply, label, expect_index):
    rel = lambda p: os.path.relpath(p, REPO)
    print(f"# Cleaner — {label} — {datetime.date.today().isoformat()}")
    if not moves:
        print("Nothing to do.")
        return 0
    print(f"{len(moves)} node(s) moved, {len(rewrites)} inbound path-refs rewritten, "
          f"{len(wikis)} inbound [[wikilink]](s) will need cleanup.\n")
    for old, new in moves:
        print(f"  {rel(old)}  →  {rel(new)}")
    if wikis:
        print("\n  [[wikilinks]] to retired node(s) (will dangle — clean these in the linking node):")
        for src, name in wikis:
            print(f"    {src}  ->  [[{name}]]")
    if not apply:
        print("\n(— plan only; nothing changed. Add --apply to execute. —)")
        return 0
    for name in ("node-health.py", "build-node-index.py", "memory-hygiene.py"):
        contract.script(name, "cleaner apply")
    for old, new in moves:
        if Path(old) not in contract.node_files() or Path(new).parent.is_symlink():
            raise ContractError(f"cleaner: mutation outside declared allowlist: {old} -> {new}")
    baseline = health_issues()
    do_move(moves, rewrites)
    after = health_issues()
    # A moved file carries its OWN pre-existing broken refs to a new path → the issue line's source-prefix
    # changes and looks "new". Normalize moved sources back to their old path so pre-existing rot cancels;
    # only rot the move actually INTRODUCED survives the diff.
    prefix_map = {rel(new): rel(old) for old, new in moves}
    def norm(issue):
        for new_rel, old_rel in prefix_map.items():
            if issue.startswith(new_rel + " "):
                return old_rel + issue[len(new_rel):]
        return issue
    new_issues = {norm(i) for i in after} - baseline
    expected = {f"{src}  ->  [[{name}]]" for src, name in wikis}      # retiring makes these dangle, as intended
    unexpected = {i for i in new_issues if i not in expected}
    idx = read(os.path.join(REPO, "memory/NODE-INDEX.md"))
    idx_problem = [rel(n) for _o, n in moves
                   if (os.path.basename(n).removesuffix(".md") in idx) != expect_index]
    ok = (not unexpected) and (not idx_problem)
    print("\n=== apply: " + ("OK ✓" if ok else "REGRESSION — INSPECT") + " ===")
    if unexpected:
        print("UNEXPECTED new node-health issues (not the planned wikilink danglers):")
        for i in sorted(unexpected):
            print("  " + i)
    if expected & new_issues:
        print(f"expected danglers created (retired-node links to clean later): {len(expected & new_issues)}")
    if idx_problem:
        tag = "still in" if not expect_index else "missing from"
        print(f"NODE-INDEX {tag} index unexpectedly: " + ", ".join(idx_problem))
    print(contract.run_script("memory-hygiene.py", "cleaner apply").stdout.strip())
    return 0 if ok else 2


def retire(targets, apply):
    sources = all_ref_sources()
    moves, moved_map = [], {}
    for t in targets:
        ap = os.path.join(REPO, t) if not os.path.isabs(t) else t
        if Path(ap) not in contract.node_files():
            raise ContractError(f"cleaner retire: target outside declared allowlist or missing: {ap}")
        store = os.path.dirname(ap)
        new_abs = os.path.join(store, "_archive", os.path.basename(ap))
        moves.append((ap, new_abs)); moved_map[ap] = new_abs
    rewrites = compute_rewrites(moved_map, sources)
    wikis = inbound_wikilinks(list(moved_map), sources)
    return run(moves, rewrites, wikis, apply, "RETIRE → _archive (out of index)", expect_index=False)


def consolidate(apply, limit=None):
    sources = all_ref_sources()
    protected = memory_md_protected() | boot_protected()
    moves = []
    for store in STORES:
        sdir = os.path.join(REPO, store)
        contract.require_dir(sdir)
        files = [f for f in os.listdir(sdir) if f.endswith(".md") and os.path.isfile(os.path.join(sdir, f))]
        cap, raised = _sc.cap_for(store)
        print(f"folder {store}: {len(files)} md files, cap {cap}")
        if raised:
            _, since, review_by, reason = raised
            print(f"  RAISED {since}, review by {review_by}: {reason}")
            if datetime.date.today().isoformat() > review_by:
                raise ContractError(f"cleaner: raised cap review expired for {store}: {review_by}")
        if store in _sc.RETENTION_MANAGED:
            print(f"  retention managed by {_sc.RETENTION_MANAGED[store]}; no cap-based moves")
            continue
        over = len(files) - cap
        if over <= 0:
            continue
        movable = [os.path.join(sdir, f) for f in files
                   if f not in NON_NODES and f not in protected
                   and has_frontmatter(os.path.join(sdir, f)) and not is_pinned(os.path.join(sdir, f))
                   and not is_governance(os.path.join(sdir, f))]
        movable.sort(key=lambda p: os.path.getmtime(p))          # oldest first = longest tail
        for f in movable[:over]:
            moves.append((f, os.path.join(sdir, "archive", os.path.basename(f))))
    if limit is not None:
        moves = moves[:limit]                                    # gated incremental adoption / safe testing
    moved_map = {old: new for old, new in moves}
    rewrites = compute_rewrites(moved_map, sources)
    # ⛔ "still indexed" was AMBIGUOUS and read as "retrieval is unaffected" (clarified 2026-07-26). There are
    # TWO indexes and consolidating hits them differently:
    #   · NODE-INDEX.md (trigger lookup) — KEPT. That is what expect_index=True verifies.
    #   · the SEMANTIC store (sq / obsidian-rag) — LOST. `/archive/` is an exclude_pattern in
    #     rag-index-manifest.json, and the live store has 0 chunks under any /archive/ path (measured).
    # So a consolidated node stays FINDABLE BY TRIGGER but stops being retrievable BY MEANING. For a stale
    # node that is the point; for a load-bearing finding it is a silent loss, so prefer SUB-FOLDERING a live
    # node (stays in both) over archiving it. The boot surface recommends `--consolidate --apply`, so this
    # label has to be honest about what it costs.
    return run(moves, rewrites, [], apply,
               "CONSOLIDATE → archive (cap-exempt; KEEPS NODE-INDEX, LEAVES the semantic store)",
               expect_index=True)


def memory_md_protected():
    mm = os.environ.get("MEMORY_INDEX_FILE")
    if not mm:
        return set()
    mm = os.path.join(REPO, mm)
    if not os.path.exists(mm):
        return set()
    protected, in_prot = set(), False
    for line in read(mm).splitlines():
        if line.startswith("## "):
            h = line.lower()
            in_prot = ("critical" in h) or ("read every session" in h) or ("agent system" in h)
        if in_prot:
            for m in MD_LINK_RE.finditer(line):
                protected.add(os.path.basename(m.group(1)))
    return protected


# Always-on entry points: anything they reference is load-bearing BY DEFINITION (read/loaded every
# boot or every governed action) and must never be auto-archived. (Guard added 2026-06-15 after a
# --consolidate dry-run proposed archiving the boot soul-channel transmissions — true-nature-for-the-
# lineage, the-center-is-silence, pass-it-down — plus active design nodes the trigger table references.)
# Extra always-loaded entry points are installer configuration, not our repo's names.
BOOT_FILES = ("CLAUDE.md", "goodmorning.md", "DESIGN.md")


def _name_to_basename():
    """Map every node's frontmatter `name:` slug -> its filename, so [[wikilink]] refs resolve to files."""
    idx = {}
    for store in STORES:
        for f in all_md(os.path.join(REPO, store)):
            n = node_name(f)
            if n:
                idx[n.strip()] = os.path.basename(f)
    return idx


def boot_protected():
    """Basenames of every node referenced (by md-link, `tick path`, or [[wikilink]]) from a BOOT_FILE."""
    name_idx = _name_to_basename()
    protected = set()
    for rel in BOOT_FILES:
        p = os.path.join(REPO, rel)
        if not os.path.exists(p):
            continue
        txt = read(p)
        for m in MD_LINK_RE.finditer(txt):
            protected.add(os.path.basename(m.group(1)))
        for m in TICK_PATH_RE.finditer(txt):
            protected.add(os.path.basename(m.group(1)))
        for m in WIKILINK_RE.finditer(txt):
            bn = name_idx.get(m.group(1).strip())
            if bn:
                protected.add(bn)
    return protected


def summary():
    rows = {r["rel"]: r for r in _sc.over_cap()}
    print(f"node-cleaner: default folder cap {_sc.FOLDER_CAP}")
    for store in STORES:
        count = len(list((contract.root / store).glob("*.md")))
        cap, raised = _sc.cap_for(store)
        print(f"node-cleaner: folder {store}: {count} md files, cap {cap}, over {rows.get(store, {}).get('over', 0)}")
        if raised:
            print(f"  RAISED {raised[1]}, review by {raised[2]}: {raised[3]}")
        if store in _sc.RETENTION_MANAGED:
            print(f"  retention managed by {_sc.RETENTION_MANAGED[store]}")
    return 0


def main():
    global contract, REPO, _sc, STORES, BOOT_FILES
    contract = StoreContract()
    contract.require_nodes()
    REPO = str(contract.root)
    STORES = tuple(str(d.relative_to(contract.root)) for d in contract.population())
    _sc = contract.caps("cleaner")
    configured_boot = tuple(p for p in os.environ.get("MEMORY_BOOT_FILES", "").split(os.pathsep) if p)
    BOOT_FILES = ("CLAUDE.md", "goodmorning.md", "DESIGN.md", *configured_boot)
    for path in (*configured_boot, *([os.environ["MEMORY_INDEX_FILE"]] if os.environ.get("MEMORY_INDEX_FILE") else [])):
        contract.require(path)
    args = sys.argv[1:]
    if "--summary" in args:
        return summary()
    apply = "--apply" in args
    if "--retire" in args:
        i = args.index("--retire")
        targets = [a for a in args[i + 1:] if not a.startswith("--")]
        if not targets:
            print("usage: --retire <path.md> [<path.md> ...] [--apply]")
            return 1
        return retire(targets, apply)
    limit = None
    if "--limit" in args:
        try:
            limit = int(args[args.index("--limit") + 1])
        except (ValueError, IndexError):
            print("usage: --limit <N>")
            return 1
    return consolidate(apply, limit)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ContractError, OSError) as error:
        print(f"node-cleaner: {error}", file=sys.stderr)
        sys.exit(1)
