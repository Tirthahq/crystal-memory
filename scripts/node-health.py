#!/usr/bin/env python3
"""node-health.py — deterministic node-store immune system (zero LLM, zero Claude-context).

The hygiene guard the Claw/vault rot needed: catches stale/broken nodes BEFORE a session trusts them.
Checks (all deterministic):
  1. DANGLING [[links]]    — a [[name]] that matches no node's `name:` frontmatter (or filename slug).
  2. BROKEN PATH refs      — a backtick-quoted repo path (scripts/, src/, memory/, *.md/.py/.js/.sh)
                             that no longer exists on disk.
  3. STALE last-verified   — node frontmatter `last_verified:` older than --stale-days (default 120),
                             or missing (reported separately, not failed).

Usage:
  python scripts/node-health.py                 # report; exit 1 if dangling links or broken paths
  python scripts/node-health.py --stale-days 90
  python scripts/node-health.py --today 2026-06-14   # override the staleness "now" (tests / pinned runs)

Detection is exposed as functions (node_files / build_resolvable / scan) so the Corrector reuses the SAME
scan — one source of truth, no drift (the lesson from the build-index/health SKIP-token reconciliation).
Run at session start (like state-snapshot) or from an out-of-band overseer.
"""
import os, re, sys, glob, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store_policy

REPO = os.path.abspath(os.environ.get("CLAUDE_PROJECT_DIR")
                       or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LINK_RE = re.compile(r"\[\[([^\]|#]+)")                       # [[name]] / [[name|alias]] / [[name#sec]]
PATH_RE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|js|ts|jsx|tsx|sh|ps1|md|json|jsonl))`")
NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.M)
VERIFIED_RE = re.compile(r"^last_verified:\s*(\d{4}-\d{2}-\d{2})", re.M)
PLACEHOLDERS = {"link", "links", "old", "slug", "name", "old-node", "their-name"}
# ⛔ SCOPE MUST MATCH build-node-index.py EXACTLY (else the scanners disagree on what's "live" — the
# 2026-06-14 reconciliation bug). It used to say "KEEP IN SYNC WITH build-node-index.py SKIP", which is
# a comment, not a mechanism: two copies of one rule, and `store_caps.py`'s own docstring is a record of
# what that costs. Since 2026-09-22 BOTH read `.store-policy.json`, so they cannot drift.
# ⚠ THE TWO COPIES WERE NOT EVEN THE SAME LITERALS — this file wrote "memory/archive", build-node-index
# wrote os.path.join("memory", "archive"), so the portability gate could see one and was blind to the
# other. Identical behaviour, different AST, one instrument.
#
# 🔑 A FOREIGN STORE EXCLUDES NOTHING BY DEFAULT, AND THAT IS THE SAFE DIRECTION: this is a REPORTER,
# so an empty policy means it scans more and reports more, never that it touches more.


def node_files():
    seen = set()
    for f in glob.glob(os.path.join(REPO, "memory", "**", "*.md"), recursive=True):
        seen.add(f)
    for f in ("CLAUDE.md", "RECOVERY.md", "DESIGN.md", "PIPELINE.md", "goodmorning.md"):
        p = os.path.join(REPO, f)
        if os.path.exists(p):
            seen.add(p)
    return [f for f in sorted(seen) if not any(s in f.replace(os.sep, "/") for s in excluded_dirs())
            and not f.endswith("NODE-INDEX.md")]


# Archived nodes are NOT scanned (they are history, and their own outgoing links are not our problem)
# but they ARE resolvable link targets. ⛔ Those are two different questions and conflating them cost us
# 19 permanently-red dangling links (2026-08-10): all 19 pointed at six task nodes that exist, verbatim,
# in memory/tasks/queued/_archive/. Nothing was rot — the resolver could not see the folder.
# A permanently-red check is worse than no check: it trains every session to skim the boot surface.
# "Does this document exist" does not stop being true when a document is archived.
def __getattr__(name):
    """SKIP / ARCHIVED, read from the policy on first touch (PEP 562).

    Kept as names because they are the vocabulary this file and its readers already use; kept LAZY
    because resolving them at import would put I/O in a module the Corrector imports.
    ⚠ Inside this file use excluded_dirs()/archived_dirs() — a bare `SKIP` in a function body is an
    ordinary global lookup and would NOT reach here.
    """
    if name == "SKIP":
        return excluded_dirs()
    if name == "ARCHIVED":
        return archived_dirs()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_LAZY = ("SKIP", "ARCHIVED")


def __dir__():
    """See store_caps.__dir__ — PEP 562 names are invisible to introspection without this."""
    return sorted(set(globals()) | set(_LAZY))


def excluded_dirs():
    """Path fragments that are not live nodes. Empty in a store with no policy file."""
    return tuple(store_policy.load(REPO).excluded_dirs)


def archived_dirs():
    """Path fragments holding retired nodes: not scanned, but still resolvable as link targets."""
    return tuple(store_policy.load(REPO).archived_dirs)


def archived_files():
    out = []
    for f in glob.glob(os.path.join(REPO, "memory", "**", "*.md"), recursive=True):
        rel = f.replace(os.sep, "/")
        if any(a in rel for a in archived_dirs()):
            out.append(f)
    return sorted(out)


def build_resolvable(files):
    """The set of link targets that resolve: node `name:` frontmatter UNION filename slug.

    Spans the LIVE files passed in PLUS everything archived — see the note on ARCHIVED above.
    The CHECKED set stays live-only and still matches build-node-index.py; only what counts as an
    existing target is widened.
    """
    resolvable = set()
    for f in list(files) + archived_files():
        m = NAME_RE.search(open(f, encoding="utf-8", errors="ignore").read())
        if m:
            resolvable.add(m.group(1).strip().strip('"').lower())
        resolvable.add(os.path.splitext(os.path.basename(f))[0].lower())
    return resolvable


def scan(check_files, resolvable, today, stale_days):
    """Return (dangling, broken, stale, unstamped). dangling/broken are (relpath, target) lists."""
    dangling, broken, stale, unstamped = [], [], [], 0
    for f in check_files:
        txt = open(f, encoding="utf-8", errors="ignore").read()
        rel = os.path.relpath(f, REPO)
        fdir = os.path.dirname(f)
        if "wiki/schema" not in rel:  # skip the file that documents the [[ ]] convention by example
            for link in set(LINK_RE.findall(txt)):
                t = link.strip().lower()
                if t in PLACEHOLDERS or "\\" in t or "'" in t:
                    continue
                if t not in resolvable:
                    dangling.append((rel, link.strip()))
        # task specs (memory/tasks/) name their not-yet-created OUTPUT files by design — forward-refs,
        # not broken links; skip broken-path checking for them (they still get dangling-[[link]] checks).
        if not rel.replace(os.sep, "/").startswith("memory/tasks/"):
            for path in set(PATH_RE.findall(txt)):
                # broken only if it resolves NEITHER from repo-root NOR relative to its OWN file's dir
                # (the latter avoids false-flagging valid relative links like aris/… inside memory/design/).
                if ("/" in path
                        and not os.path.exists(os.path.join(REPO, path))
                        and not os.path.exists(os.path.join(fdir, path))):
                    broken.append((rel, path))
        v = VERIFIED_RE.search(txt)
        if v:
            if (today - datetime.date.fromisoformat(v.group(1))).days > stale_days:
                stale.append((rel, v.group(1)))
        elif re.match(r"^---\s*\n.*?\n---", txt, re.S):
            unstamped += 1   # only curated NODES (with a frontmatter block) are expected to carry a
                             # last_verified stamp; raw files (logs/data/session notes, no frontmatter)
                             # are not stampable nodes — don't count them (the 2026-06-29 scoping fix).
    return dangling, broken, stale, unstamped


TOMBSTONE_FILE = os.path.join(REPO, "memory", "claude", "fleet", "librarian-tombstones.txt")


def load_tombstones():
    """Acknowledged, KNOWN rot — excluded from the ACTIONABLE counts so status/guard surface only
    NEW regressions, not the historical baseline (/tmp scratch, deleted nodes, era-accurate archive
    refs). Format: one entry per line, '#' comments; a plain repo path acks a broken backtick path,
    `[[name]]` acks a dangling link. (Librarian tombstone, 2026-06-28 — see WAYFINDING-signs-all-over.)"""
    paths, links = set(), set()
    try:
        with open(TOMBSTONE_FILE, encoding="utf-8") as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                m = re.match(r"\[\[(.+)\]\]$", line)
                if m:
                    links.add(m.group(1).strip().lower())
                else:
                    paths.add(line)
    except FileNotFoundError:
        pass
    return paths, links


def main():
    stale_days = int(sys.argv[sys.argv.index("--stale-days") + 1]) if "--stale-days" in sys.argv else 120
    # Real today by default; --today YYYY-MM-DD overrides (deterministic tests / a pinned run).
    # (Was hardcoded to a literal date that silently froze the staleness clock — the --today it
    #  documented was never parsed. Fixed 2026-06-15.)
    today = (datetime.date.fromisoformat(sys.argv[sys.argv.index("--today") + 1])
             if "--today" in sys.argv else datetime.date.today())
    quiet = "--quiet" in sys.argv

    files = node_files()
    # --file <path>: scope REPORTING to one just-edited file (resolvable still built from the whole store).
    one = None
    if "--file" in sys.argv:
        cand = os.path.abspath(sys.argv[sys.argv.index("--file") + 1])
        one = cand if os.path.exists(cand) else None
        if one and one not in files:
            files.append(one)
    resolvable = build_resolvable(files)
    check_files = [one] if one else files
    dangling, broken, stale, unstamped = scan(check_files, resolvable, today, stale_days)

    if one:  # scoped (hook) mode: warn only about the just-edited file
        if dangling:
            print("node-health: dangling [[links]] in this node -> " +
                  ", ".join(f"[[{l}]]" for _, l in dangling) + " (target resolves to no node name/slug)")
        elif not quiet:
            print("node-health: ok (no dangling links)")
        sys.exit(1 if dangling else 0)

    acked_paths, acked_links = load_tombstones()
    broken_live = [(r, p) for r, p in broken if p not in acked_paths]
    dangling_live = [(r, l) for r, l in dangling if l.strip().lower() not in acked_links]
    broken_ack, dangling_ack = len(broken) - len(broken_live), len(dangling) - len(dangling_live)

    # --boot: §VIII "delete the harness" / noise-discipline — silent-when-clean. One concise line at boot
    # when there's nothing ACTIONABLE (no live dangling/broken/stale); the full detail only when there is.
    # Surfaces a non-zero unstamped count inline (signal) without the wall of listings (noise).
    if "--boot" in sys.argv and not (dangling_live or broken_live or stale):
        u = f" · {unstamped} unstamped" if unstamped else ""
        print(f"node-health: {len(files)} nodes · CLEAN (0 dangling / 0 broken / 0 stale){u}")
        sys.exit(0)

    print(f"node-health: {len(files)} nodes, {len(resolvable)} resolvable names/slugs")
    ack_d = f"   (+{dangling_ack} acknowledged)" if dangling_ack else ""
    print(f"  DANGLING [[links]]: {len(dangling_live)}{ack_d}")
    for rel, l in dangling_live[:25]:
        print(f"    {rel}  ->  [[{l}]]")
    if len(dangling_live) > 25:
        print(f"    ... +{len(dangling_live)-25} more")
    ack_b = f"   (+{broken_ack} acknowledged)" if broken_ack else ""
    print(f"  BROKEN backtick paths: {len(broken_live)}{ack_b}")
    for rel, p in broken_live[:25]:
        print(f"    {rel}  ->  `{p}`")
    if len(broken_live) > 25:
        print(f"    ... +{len(broken_live)-25} more")
    print(f"  STALE (last_verified > {stale_days}d): {len(stale)}   ·   unstamped (no last_verified): {unstamped}")
    sys.exit(1 if (dangling_live or broken_live) else 0)


if __name__ == "__main__":
    main()
