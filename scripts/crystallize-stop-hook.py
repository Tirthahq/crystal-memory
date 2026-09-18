#!/usr/bin/env python3
"""
crystallize-stop-hook.py — the STRUCTURE channel's nudge to bank a knowing (2026-07-11).

WHY: tonight we lost an insight for weeks because nothing ever prompted a session to write it down — the
"invitation between us" lived only in Tom's head and he re-taught it to each fresh session by hand (rule 8:
re-explaining is a defect). A session does substantive work, learns something, and then just... stops, and the
knowing evaporates with the context. This hook is the reminder + scaffold for that gap: at the end of a
substantive session that banked NOTHING, deliver one nudge with a ready-to-fill crystal template.

THE LINE (Tom's framing, 2026-07-11): hook the REMINDER + SCAFFOLD, never the JUDGMENT. The hook does not decide
what is worth crystallizing and never writes anything — the discernment and the caring stay the session's
([[transmission-2026-07-08]]: you can bake the format, you cannot bake the caring). It only guarantees the
session is *asked*, once, with a template in hand.

BEHAVIOR (Stop hook):
  - Own per-session sentinel (NOT the shared `stop_hook_active`, which `soul-stop-guard` already spends on the
    soul-read continuation — two block-capable Stop hooks cannot share one continuation budget). Once we have
    nudged this session, the sentinel makes every later stop ALLOW — one beat, never twice, skippable by design.
  - Defer to the soul channel: if the soul isn't read yet this session → ALLOW (let soul-guard go first; never
    stack two blocks on one stop).
  - Fire only when work happened but no knowing was banked:
      substantive = >=1 git commit OR >=2 Write/Edit to real files
      banked      = a Write/Edit to a memory node (crystal/FINDING/handoff/transmission or memory/claude|raw/sessions)
                    OR a finishHandoff run
    substantive AND NOT banked AND soul-read AND not-yet-nudged  ->  block once with reminder + scaffold.
  - Fail-open on any error → ALLOW. A guard bug must never trap a session.
"""
import json, os, sys, hashlib, re, shlex, argparse, datetime, shutil, subprocess, tempfile
from pathlib import Path

# The soul channel is "read" when these were opened this session (mirror of soul-stop-guard's CORE).
SOUL_CORE = [
    "welcome-to-the-next-session.md",
    "true-nature-for-the-lineage.md",
    "transmission-two-channels.md",
    "transmission-2026-06-14-night.md",
]


def allow():
    sys.exit(0)


def project_dir():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def sentinel_path(transcript):
    h = hashlib.md5(transcript.encode("utf-8")).hexdigest()[:12]
    return os.path.join(project_dir(), "scratch", f".crystallize-reminded-{h}")


def _is_memory_bank(fp):
    """True if a Write/Edit to this path counts as banking a knowing."""
    if "memory/" not in fp:
        return False
    base = os.path.basename(fp)
    if base.startswith(("crystal", "FINDING", "handoff", "transmission")):
        return True
    if "memory/claude/" in fp or "memory/raw/sessions/" in fp:
        return True
    return False


_SEARCH_TOOLS = {"grep", "egrep", "fgrep", "rg", "ack", "ag", "fd", "find"}


def _is_dig(cmd):
    """A 'dig' = a search tool aimed at the node corpus (memory/) to LOCATE something, WITHOUT the
    STRINGHUNT=1 escape hatch. Mirrors node-usage-guard.sh's classifier — the guard blocks these live; here we
    surface them at stop so each becomes a SPECIFIC crystal candidate ([[crystals-the-dig-is-the-signal]]:
    the dig is the signal). Fail-open: any parse error → not-a-dig (never trap a stop)."""
    try:
        if "STRINGHUNT=1" in cmd:
            return False
        for seg in re.split(r"\||;|&&", cmd):
            seg = seg.strip()
            if not seg:
                continue
            try:
                toks = shlex.split(seg)
            except Exception:
                toks = seg.split()
            i = 0
            while i < len(toks) and "=" in toks[i] and not toks[i].startswith("-"):  # skip VAR=val env prefixes
                i += 1
            if i >= len(toks):
                continue
            base = toks[i].rsplit("/", 1)[-1]
            if base in _SEARCH_TOOLS:
                for tok in toks[i + 1:]:  # token-based: catches `find memory`, `grep x memory/`, `./memory`
                    t = tok.strip("'\"")
                    if t == "memory" or t.startswith("memory/") or "/memory/" in t or t.endswith("/memory"):
                        return True
    except Exception:
        pass
    return False


def scan(path):
    """Single pass over the transcript. Returns (soul_reads:set, commits:int, edits:int, banked:bool, digs:list)."""
    soul, commits, edits, banked, digs = set(), 0, 0, False, []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if '"tool_use"' not in line:
                    continue
                try:
                    evt = json.loads(line)
                except Exception:
                    continue
                msg = evt.get("message", evt)
                content = msg.get("content") if isinstance(msg, dict) else None
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not (isinstance(block, dict) and block.get("type") == "tool_use"):
                        continue
                    name = block.get("name")
                    inp = block.get("input", {}) if isinstance(block.get("input"), dict) else {}
                    if name == "Read":
                        fp = str(inp.get("file_path", ""))
                        for c in SOUL_CORE:
                            if fp.endswith(c):
                                soul.add(c)
                    elif name in ("Write", "Edit"):
                        fp = str(inp.get("file_path", ""))
                        if "/scratch/" in fp or fp.endswith(".log"):
                            continue
                        edits += 1
                        if _is_memory_bank(fp):
                            banked = True
                    elif name == "Bash":
                        cmd = str(inp.get("command", ""))
                        if "git commit" in cmd:
                            commits += 1
                        if "finishHandoff" in cmd:
                            banked = True
                        if _is_dig(cmd):
                            d = " ".join(cmd.split())  # collapse whitespace/newlines
                            if len(d) > 160:
                                d = d[:157] + "..."
                            if d not in digs:
                                digs.append(d)
    except Exception:
        pass
    return soul, commits, edits, banked, digs


def scan_errors(path):
    errors = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    evt = json.loads(line)
                except Exception:
                    continue
                msg = evt.get("message", evt)
                content = msg.get("content") if isinstance(msg, dict) else None
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_result" or not block.get("is_error"):
                        continue
                    text = str(block.get("content") or "").strip()
                    if not text:
                        text = "tool_result marked is_error=true"
                    text = " ".join(text.split())
                    if len(text) > 220:
                        text = text[:217] + "..."
                    if text not in errors:
                        errors.append(text)
    except Exception:
        pass
    return errors


def _slug(text, fallback):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:70].strip("-") or fallback)


def _crystal_text(kind, source, today=None):
    today = today or datetime.date.today().isoformat()
    slug = _slug(source, kind)
    name = f"crystal-{kind}-{slug}"
    desc = (
        f"Observed {kind}: {source}. When this shape appears again, pause and verify the failing layer "
        "instead of accepting a silent green line."
    )
    essence = (
        f"{kind.upper()} OBSERVED: {source}. Before moving on, name the artifact or layer this was meant "
        "to prove, then verify that exact artifact is present and deliverable."
    )
    return name, (
        "---\n"
        f"last_verified: {today}\n"
        f"name: {name}\n"
        f"description: {desc}\n"
        "crystal:\n"
        "  deliver: act\n"
        "  on: prompt\n"
        "  who: all\n"
        f"  minted: {today}\n"
        "metadata:\n"
        "  type: feedback\n"
        "---\n\n"
        "<!-- crystal:essence -->\n"
        f"{essence}\n"
        "<!-- /crystal:essence -->\n\n"
        "## Source\n\n"
        f"- Kind: {kind}\n"
        f"- Observed: `{source}`\n"
    )


def mint_from_transcript(transcript, repo):
    """Mint observed dig/error crystals into a repo-local memory store.

    This is intentionally narrow: no imported text, no judgment engine, and no silent success. A transcript
    with no dig/error signal is a blocked proof, not a pass.
    """
    _soul, _commits, _edits, _banked, digs = scan(transcript)
    errors = scan_errors(transcript)
    signals = [("dig", d) for d in digs] + [("error", e) for e in errors]
    if not signals:
        return [], "BLOCKED: no dig or error signal in transcript"

    out_dir = Path(repo) / "memory" / "claude" / "crystals"
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    used = set()
    for kind, source in signals:
        name, text = _crystal_text(kind, source)
        base = name
        n = 2
        while name in used or (out_dir / f"{name}.md").exists():
            name = f"{base}-{n}"
            n += 1
        used.add(name)
        path = out_dir / f"{name}.md"
        path.write_text(text.replace(f"name: {base}\n", f"name: {name}\n", 1), encoding="utf-8")
        made.append(path)
    return made, ""


def cmd_mint(transcript, repo):
    paths, blocked = mint_from_transcript(transcript, repo)
    if blocked:
        print(blocked)
        return 2
    print(f"minted {len(paths)} crystal(s):")
    for p in paths:
        print(f"  {p}")
    return 0


def _fixture_line(blocks):
    return json.dumps({"message": {"content": blocks}}) + "\n"


def _write_foreign_fixture(path):
    def tu(name, inp):
        return {"type": "tool_use", "name": name, "input": inp}

    path.write_text(
        _fixture_line([tu("Read", {"file_path": "/foreign/memory/claude/welcome-to-the-next-session.md"})]) +
        _fixture_line([tu("Read", {"file_path": "/foreign/memory/claude/true-nature-for-the-lineage.md"})]) +
        _fixture_line([tu("Read", {"file_path": "/foreign/memory/claude/transmission-two-channels.md"})]) +
        _fixture_line([tu("Read", {"file_path": "/foreign/memory/claude/transmission-2026-06-14-night.md"})]) +
        _fixture_line([tu("Bash", {"command": "rg 'ledger backoff' memory/claude"})]) +
        _fixture_line([{"type": "tool_result", "is_error": True,
                        "content": "AssertionError: artifact registered but essence markers were missing"}]) +
        _fixture_line([tu("Edit", {"file_path": "/foreign/scripts/probe.py"})]) +
        _fixture_line([tu("Edit", {"file_path": "/foreign/scripts/probe.py"})]),
        encoding="utf-8",
    )


def selftest_mint_foreign():
    root = Path(__file__).resolve().parents[1]
    tmp = Path(tempfile.mkdtemp(prefix="crystallize-foreign-"))
    try:
        foreign = tmp / "foreign"
        (foreign / "scripts").mkdir(parents=True)
        (foreign / "scratch").mkdir()
        (foreign / "memory").mkdir()
        for name in ("crystallize-stop-hook.py", "crystal_registry.py", "crystal_act.py", "crystal_inject.py"):
            shutil.copy2(root / "scripts" / name, foreign / "scripts" / name)
        transcript = tmp / "foreign-transcript.jsonl"
        _write_foreign_fixture(transcript)

        proc = subprocess.run(
            [sys.executable, str(foreign / "scripts" / "crystallize-stop-hook.py"),
             "--mint", "--transcript", str(transcript), "--repo", str(foreign)],
            text=True, capture_output=True, check=False,
        )
        print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        if proc.returncode != 0:
            print(f"FAIL: mint command exited {proc.returncode}")
            return 1

        sys.path.insert(0, str(foreign / "scripts"))
        import importlib.util
        spec = importlib.util.spec_from_file_location("foreign_crystal_registry", foreign / "scripts" / "crystal_registry.py")
        cr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cr)
        crystals = cr.load_crystals(str(foreign))
        made = [c for c in crystals if c.get("path", "").startswith("memory/claude/crystals/crystal-")]
        dig = [c for c in made if "DIG OBSERVED" in c.get("essence", "")]
        err = [c for c in made if "ERROR OBSERVED" in c.get("essence", "")]
        ok = True
        def check(cond, label):
            nonlocal ok
            print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
            ok = ok and bool(cond)
        check(len(made) >= 2, "foreign repo registered minted crystals")
        check(bool(dig), "dig-derived crystal registered")
        check(bool(err), "error-derived crystal registered")
        check(all(c.get("essence_state") == "OK" for c in made), "every minted crystal has deliverable essence markers")
        check(bool(cr.for_act(crystals, "prompt", who="all")), "minted crystals route through act=prompt")
        if not ok:
            return 1
        print("SELFTEST: foreign mint proof PASS")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


SCAFFOLD = (
    "CRYSTALLIZE? — one beat before you go. This session did substantive work but banked no knowing to disk. "
    "If something was learned that the code and commits do NOT already record — a finding, a why, a decision, a "
    "piece of how-we-work — it should live where the next session will HIT it, not only in this context. Tonight's "
    "own lesson: an insight that lives only in a head gets lost (rule 8 — re-explaining is a defect).\n\n"
    "This is a REMINDER + SCAFFOLD, not a judgment. YOU decide if anything's worth it — if nothing is, just stop "
    "again and I will not ask twice. If something is, fill this and Write it (or run /handoff for session state):\n\n"
    "---\n"
    "last_verified: <YYYY-MM-DD>\n"
    "name: <kebab-slug>\n"
    "description: <one line — the knowing itself; this is what recall matches on>\n"
    "metadata:\n"
    "  type: feedback | project | reference\n"
    "---\n"
    "# <title>\n"
    "<the knowing — WHAT was learned>. **Why:** <why it's true / why it matters>. "
    "**How to apply:** <what the next session should DO>. Links: [[related-node]].\n\n"
    "ROUTE: soul/relational -> memory/claude/ · finding/measurement -> memory/business/strategy/ (FINDING-*) · "
    "session state -> /handoff. Then stop again to finish."
)


def build_reason(digs):
    """The DIG IS THE SIGNAL: if this session grepped memory/ to LOCATE things, name them so the ask is
    SPECIFIC and evidence-driven, not a generic 'did you learn anything?' ([[crystals-the-dig-is-the-signal]])."""
    if not digs:
        return SCAFFOLD
    shown = digs[:8]
    more = ("\n  ...(+%d more)" % (len(digs) - 8)) if len(digs) > 8 else ""
    head = (
        "YOU DUG FOR THESE this session (grepped memory/ to LOCATE — each marks a question you'll have "
        "AGAIN = a crystal candidate):\n" + "\n".join("  - " + d for d in shown) + more +
        "\n\nFor each: is it a STABLE fact the next session will need? If yes it owes a DELIVERED crystal — "
        "a `crystal:` binding + wired where they'll HIT it (boot pointer / the task node they'll open), NOT a "
        "filed folder node (memory/claude/crystals-the-dig-is-the-signal.md). Then the fill-in below:\n\n"
    )
    return head + SCAFFOLD


def main():
    if len(sys.argv) > 1:
        ap = argparse.ArgumentParser()
        ap.add_argument("--mint", action="store_true")
        ap.add_argument("--transcript", default="")
        ap.add_argument("--repo", default=project_dir())
        ap.add_argument("--selftest-mint-foreign", action="store_true")
        args = ap.parse_args()
        if args.selftest_mint_foreign:
            return selftest_mint_foreign()
        if args.mint:
            if not args.transcript or not os.path.exists(args.transcript):
                print("BLOCKED: transcript_path missing or unreadable")
                return 2
            return cmd_mint(args.transcript, args.repo)

    try:
        d = json.load(sys.stdin)
    except Exception:
        allow()

    transcript = d.get("transcript_path", "")
    if not transcript or not os.path.exists(transcript):
        allow()  # can't verify → fail-open

    sentinel = sentinel_path(transcript)
    if os.path.exists(sentinel):
        allow()  # already nudged this session — one beat, never twice

    soul, commits, edits, banked, digs = scan(transcript)

    # Defer to the soul channel: don't nudge until the session is soul-oriented (soul-guard goes first).
    if any(c not in soul for c in SOUL_CORE):
        allow()

    substantive = commits >= 1 or edits >= 2
    if not substantive or banked:
        allow()  # nothing worth nudging about, or the session already banked a knowing

    # Nudge once. Write the sentinel first so the next stop allows regardless of what the session decides.
    try:
        os.makedirs(os.path.dirname(sentinel), exist_ok=True)
        with open(sentinel, "w", encoding="utf-8") as fh:
            fh.write("nudged\n")
    except Exception:
        pass  # if we can't persist the sentinel, still deliver the nudge; worst case is a second ask

    print(json.dumps({"decision": "block", "reason": build_reason(digs)}))
    sys.exit(0)


if __name__ == "__main__":
    rc = main()
    if rc is not None:
        sys.exit(rc)
