#!/usr/bin/env python3
"""
crystal_registry.py — the binding convention for FROM-WITHIN crystal deployment (Tom, 2026-07-11:
"implement crystals in everyday deployments, so adding them is as natural as everything else").

A crystal is any node whose frontmatter carries a `crystal:` binding block. The delivery channels (boot,
inject, rag, serve, bytes) QUERY this registry instead of hardcoding paths — so the Nth crystal is drop-in:
write the node, declare its binding, done. No per-crystal wiring. The binding encodes the measured 2×2 law
(deliver only where the rule is ABSENT + the carrier has CAPACITY — [[FINDING-crystals-refresh-long-task-drift-2026-07-11]]).

Binding fields (frontmatter `crystal:` block):
  deliver : boot | inject | rag | serve | bytes   which channel carries it
  when    : boot | drift | topic | always         the trigger
  who     : frontier | 7b | resident | all        which mind/tier (the 2×2 capacity axis)
  mint_from : <node name>                          re-mint source (generated, not hand-kept)
Essence payload: the compact text between  <!-- crystal:essence -->  and  <!-- /crystal:essence -->  in the
  body — the bit that lands inline at delivery; the full node is the read-on-demand.

USAGE
  python3 scripts/crystal_registry.py list                              # all crystals + bindings
  python3 scripts/crystal_registry.py emit --channel boot --who frontier  # essence(s) for a channel, to render
Importable: `load_crystals(repo)` -> list[dict]; `for_channel(crystals, channel, who=None)`.
"""
import os, sys, argparse, json, time
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Crystals may live ANYWHERE under memory/ (a binding is a frontmatter block, not a location). Walk memory/
# recursively so a bound crystal in a subdir (dev-crystals/) or an out-of-root node (business/tirtha, tasks/)
# actually reaches its channel — the 2026-07-18 reach-bug fix (was ["memory/claude","memory/business/strategy"]
# top-level only, which silently dropped ~1/3 of bound crystals). Kept cheap for the inject hot-path: prune heavy
# dirs + read only a HEAD to detect the binding, full-read only on a match.
ROOTS = ["memory"]
EXCLUDE_DIRS = {"_archive", "raw", "codex"}  # heavy; ⛔ the claim "no crystals bind here" must stay TRUE
# ⛔ 2026-09-17: "node-rag" WAS in this set, with the comment "no crystals bind here". That claim had
# gone FALSE — two real bindings sat in memory/business/node-rag and could never fire, and the comment
# asserting otherwise is precisely what stopped anyone checking. Same shape as the `ops` note below,
# which was fixed for ONE name and never generalised. A prune list is a POPULATION claim, and a
# population claim rots. ⇒ scripts/test_crystal_excluded_dirs_hold_no_bindings.py now enforces it.
# 2026-08-02: memory/gemini was renamed memory/ops. "ops" must NOT go in EXCLUDE_DIRS — it is a BARE
# DIRECTORY NAME match, and memory/business/ops + memory/business/strategy/findings/ops are real node
# folders that DO hold crystals. Exclude the renamed tree by PATH instead.
EXCLUDE_RELPATHS = {os.path.join("memory", "ops")}
HEAD_BYTES = 4096  # frontmatter (where the crystal: binding lives) is at the top — cheap detection read
ESSENCE_OPEN, ESSENCE_CLOSE = "<!-- crystal:essence -->", "<!-- /crystal:essence -->"

def _frontmatter(text):
    """Return the raw frontmatter block (between the first two --- lines), or ''."""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[3:end] if end != -1 else ""

import re as _re

# A TRAILING YAML COMMENT ON A BINDING VALUE PUT THREE CRYSTALS IN NO CHANNEL AT ALL (found 2026-08-02).
# `deliver: rag   # demoted from boot 2026-07-24` parsed to the LITERAL string
# `"rag   # demoted from boot 2026-07-24 …"`, and `for_channel` compares with `!=`, so the crystal matched
# NO channel — not rag, not boot. Registered, essence-bearing, `who`-clean, and structurally undeliverable;
# `crystal_delivery_audit.py` reported `cannot_fire: 0` because it only checks act/essence, not whether the
# channel name is even a real channel. Silent by construction, which is the worst failure this store has.
# ⚠ Strip ONLY when the `#` is followed by whitespace (the YAML comment convention). `match:` values legally
# contain `#!` — crystal-built-and-lost matches on `#!/usr/bin` and has 34 deliveries; a naive strip at " #"
# would have silently amputated its key list and broken a crystal that works.
_TRAILING_COMMENT_RE = _re.compile(r"\s+#\s.*$")


def _strip_trailing_comment(v):
    return _TRAILING_COMMENT_RE.sub("", v).strip()


def _parse_binding(fm):
    """Minimal parse of an indented `crystal:` mapping — no yaml dep (soul-boot must stay dep-free)."""
    lines = fm.splitlines()
    binding = {}
    for i, ln in enumerate(lines):
        if ln.strip() == "crystal:" or ln.rstrip() == "crystal:":
            for sub in lines[i+1:]:
                if not sub.strip():
                    continue
                if not (sub.startswith("  ") or sub.startswith("\t")):
                    break  # dedent -> end of the crystal block
                if sub.strip().startswith("#"):
                    continue  # a whole-line comment inside the block is not a key
                if ":" in sub:
                    k, _, v = sub.strip().partition(":")
                    binding[k.strip()] = _strip_trailing_comment(v)
            break
    return binding


CHANNELS = ("boot", "inject", "rag", "act", "serve", "bytes")
WHOS = ("all", "frontier", "7b", "resident")


def invalid_bindings(crystals):
    """Crystals whose `deliver:`/`who:` is not a real value — i.e. they reach NO channel/reader.
    Registered-but-unroutable is invisible to every other check; this is the one that names it."""
    bad = []
    for c in crystals:
        why = []
        if c.get("deliver") not in CHANNELS:
            why.append(f"deliver={c.get('deliver')!r} is not a channel")
        if c.get("who", "all") not in WHOS:
            why.append(f"who={c.get('who')!r} is not a reader")
        if c.get("deliver") == "act" and not str(c.get("on") or "").strip():
            why.append("deliver=act with no `on:` — registers cleanly and never fires")
        if why:
            bad.append((c.get("path"), "; ".join(why)))
    return bad

def _essence(text):
    a = text.find(ESSENCE_OPEN)
    if a == -1:
        return ""
    b = text.find(ESSENCE_CLOSE, a)
    return text[a+len(ESSENCE_OPEN):(b if b != -1 else None)].strip("\n")

def _essence_marker_state(text):
    has_open = ESSENCE_OPEN in text
    has_close = ESSENCE_CLOSE in text
    if has_open and has_close and _essence(text).strip():
        return "OK"
    if not has_open and not has_close:
        return "MISSING MARKERS"
    if has_open and not has_close:
        return "MISSING CLOSE MARKER"
    if not has_open and has_close:
        return "MISSING OPEN MARKER"
    return "EMPTY ESSENCE"

_TELL_RE = _re.compile(r"(?:⚠|🔑)\s*\*\*THE TELL[^\n]*")
_STOP_RE = _re.compile(r"⛔+\s*\*\*(.+?)\*\*", _re.S)


def tell(c, limit=150):
    """The cheapest useful payload a crystal carries: its one-line TELL.

    ⭐ CASCADE TIER 0. Measured 2026-08-31: essence median 1496 chars, TELL median
    100 — ~15x cheaper. The whole corpus of essences is 460,968 chars = a 115-act
    floor to be heard once at 4000 chars/act; the same corpus as tells is ~25k = ~7
    acts. So a starved crystal should announce its TELL, never its filename, which
    carries no knowledge at all.

    Falls back: explicit "THE TELL" line -> first bolded ⛔ headline -> the name.
    ⚠ It must NEVER return empty; an empty tier-0 is worse than a filename.
    """
    body = c.get("essence") or ""
    m = _TELL_RE.search(body)
    if m:
        t = m.group(0)
    else:
        m2 = _STOP_RE.search(body)
        t = m2.group(1) if m2 else ""
    t = " ".join(t.split())
    t = t.replace("**", "").replace("⚠ THE TELL:", "").replace("THE TELL:", "").strip(" -—:")
    if not t:
        t = os.path.basename(c.get("path", "") or c.get("name", "") or "crystal")
    if len(t) <= limit:
        return t
    cut = t[:limit]
    sp = cut.rfind(" ")          # break on a word, never mid-token
    return (cut[:sp] if sp > limit * 0.6 else cut).rstrip(" ,;:—-") + "…"


def load_crystals(repo=REPO):
    out = []
    for root in ROOTS:
        base = os.path.join(repo, root)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            # prune heavy/irrelevant + hidden dirs in-place (no crystals bind there) — keeps the walk cheap
            dirnames[:] = sorted(
                d for d in dirnames
                if d not in EXCLUDE_DIRS and not d.startswith(".")
                and os.path.relpath(os.path.join(dirpath, d), repo) not in EXCLUDE_RELPATHS)
            for fn in sorted(filenames):
                if not fn.endswith(".md"):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    with open(path, encoding="utf-8") as f:
                        head = f.read(HEAD_BYTES)  # cheap detection: the crystal: binding is in the frontmatter (top)
                except Exception:
                    continue
                if "crystal:" not in _frontmatter(head):
                    continue
                # confirmed a binding — now pay for the full read (rare) to get the essence
                try:
                    with open(path, encoding="utf-8") as f:
                        text = f.read()
                except Exception:
                    continue
                b = _parse_binding(_frontmatter(text))
                if not b.get("deliver"):
                    continue  # not a real binding
                b["path"] = os.path.relpath(path, repo)
                b["essence"] = _essence(text)
                b["essence_state"] = _essence_marker_state(text)
                out.append(b)
    return out

def for_channel(crystals, channel, who=None):
    res = []
    for c in crystals:
        if c.get("deliver") != channel:
            continue
        cw = c.get("who", "all")
        if who and cw not in (who, "all"):
            continue
        res.append(c)
    return res

# ---- ACT BINDING (2026-07-20) -----------------------------------------------------------------
# THE PROBLEM THIS SOLVES: `deliver: rag` selects by TOKEN OVERLAP between your prompt and the
# crystal's essence. That is PULL-shaped — it can only surface what you were already thinking
# about ([[topic-retrieval-cannot-deliver-the-unthought]]: 13 deliveries to the session that
# already knew, 0 to the session that needed it). And with one slot, 66 crystals competed and 50
# never won.
#
# An ACT-BOUND crystal fires because YOU ARE DOING THE THING, not because your words happened to
# overlap. It never enters the topic ranking, so it cannot be crowded out by a broad-topic winner.
# This generalises what already works: the discriminator gate fires on "about to claim a cause",
# the Librarian on "about to commit" — both hand-wired. This lets a crystal declare the same thing
# in its own frontmatter instead of needing a bespoke hook per knowing.
#
#   crystal:
#     on: bash            # single act
#     on: commit,write    # or several
#
# `_parse_binding` already accepts arbitrary keys, so `on:` needed NO parser change.
# `delegate` added 2026-08-02: PreToolUse on Task/Agent — you are about to BRIEF A SUBAGENT. Tom named
# the gap ("the 165k burn on waiting is a major waste") and the audit confirmed it structurally: NO hook
# in settings.json matched Task or Agent, so the single most expensive decision a session makes — 12 lanes
# at 100k-320k tokens each — was the one act the whole nervous system could not see. subagent-nudge.py says
# WHETHER to delegate; nothing could reach the brief itself, where block-vs-poll is decided.
ACTS = ("bash", "write", "commit", "prompt", "boot", "delegate")


def for_act(crystals, act, who=None):
    """Crystals bound to `act`. Comma lists supported. Unknown acts return nothing rather than
    everything — a typo must go quiet, never spam every act."""
    act = (act or "").strip().lower()
    if not act:
        return []
    res = []
    for c in crystals:
        on = str(c.get("on") or "").strip().lower()
        if not on:
            continue
        if act not in {a.strip() for a in on.split(",") if a.strip()}:
            continue
        cw = c.get("who", "all")
        if who and cw not in (who, "all"):
            continue
        res.append(c)
    return res


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    e = sub.add_parser("emit"); e.add_argument("--channel", required=True); e.add_argument("--who", default=None)
    d = sub.add_parser("doctor")
    d.add_argument("--root", default=REPO)
    d.add_argument("--act", default="bash")
    d.add_argument("--ctx", default="")
    d.add_argument("--target", default="")
    d.add_argument("--who", default=os.environ.get("CRYSTAL_WHO", "frontier"))
    d.add_argument("--session", default=os.environ.get("CLAUDE_SESSION_ID", "doctor"))
    a = ap.parse_args()
    root = getattr(a, "root", REPO)
    crystals = load_crystals(root)
    if a.cmd == "list":
        if not crystals:
            print("(no crystals bound yet)"); return
        for c in crystals:
            print(f"- {c['path']}")
            print(f"    deliver={c.get('deliver')} when={c.get('when','-')} who={c.get('who','all')} mint_from={c.get('mint_from','-')}")
            if c.get("essence"):
                print(f"    essence: {len(c['essence'].splitlines())} line(s)")
    elif a.cmd == "emit":
        for c in for_channel(crystals, a.channel, a.who):
            print(c.get("essence", ""))
    elif a.cmd == "doctor":
        return doctor(root, crystals, a.act, a.ctx, a.target, a.who, a.session)


def _load_ledger(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return {}


def _fmt_wait(seconds):
    if seconds <= 0:
        return "now"
    mins = int((seconds + 59) // 60)
    return f"in {mins} minute(s)"


def doctor(root, crystals, act, ctx, target, who, session):
    """Read-only health report for standalone crystal installs."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import crystal_act

    root = Path(root).resolve()
    ledger_path = root / "scratch" / ".act-ledger.json"
    led = _load_ledger(ledger_path)
    now = time.time()
    act = (act or "").strip().lower()
    who = who or "frontier"
    session = (session or "doctor")[:40]

    print("crystals doctor")
    print(f"root: {root}")
    print(f"memory: {root / 'memory'}")
    print(f"ledger: {ledger_path} ({'present' if ledger_path.exists() else 'absent'})")
    print(f"crystals found: {len(crystals)}")
    print()

    print("per-crystal essence:")
    if not crystals:
        print("  BLOCKED: no crystals found; no delivery can be proven")
    for c in crystals:
        state = c.get("essence_state") or ("OK" if c.get("essence") else "MISSING MARKERS")
        marker = "OK" if state == "OK" else "MISSING MARKERS"
        print(f"  {marker}: {c.get('path')} ({state}; deliver={c.get('deliver')} on={c.get('on', '-')})")
    print()

    print("ledger state:")
    active = []
    for c in crystals:
        base = os.path.basename(c.get("path", ""))
        if not base:
            continue
        seen = int(led.get(f"act-session:{session}:{act}:{base}", 0) or 0)
        last = float(led.get(f"act:{act}:{base}", 0) or 0)
        wait = crystal_act.BASE_MIN * (crystal_act.BACKOFF_BASE ** seen) * 60
        remaining = (last + wait) - now
        if seen >= crystal_act.MAX_PER_SESSION:
            active.append((base, "session cap reached", None))
        elif last and remaining > 0:
            active.append((base, f"active backoff expires {_fmt_wait(remaining)}", last + wait))
    if not led:
        print("  empty ledger; no active backoff recorded")
    elif not active:
        print(f"  {len(led)} ledger key(s); no active backoff for act={act!r} session={session!r}")
    for base, msg, expires in active:
        suffix = f" at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expires))}" if expires else ""
        print(f"  {base}: {msg}{suffix}")
    print("  contract: act backoff timestamps are global per repo; session delivery counts are per CLAUDE_SESSION_ID")
    print()

    print(f"would fire for act={act!r} who={who!r}:")
    cands = crystal_act.candidates(act, ctx=ctx, target=target, who=who, repo=root, crystals=crystals)
    eligible = []
    blocked = []
    for c in cands:
        base = os.path.basename(c.get("path", ""))
        seen = int(led.get(f"act-session:{session}:{act}:{base}", 0) or 0)
        last = float(led.get(f"act:{act}:{base}", 0) or 0)
        wait = crystal_act.BASE_MIN * (crystal_act.BACKOFF_BASE ** seen) * 60
        remaining = (last + wait) - now
        if seen >= crystal_act.MAX_PER_SESSION:
            blocked.append((c, "session cap reached"))
        elif last and remaining > 0:
            blocked.append((c, f"backoff expires {_fmt_wait(remaining)}"))
        else:
            eligible.append(c)
    got, starved = crystal_act.pack(crystal_act.order(eligible, act, session, led=led, now=now))
    if not cands:
        # ⛔ AN EMPTY PROBE IS NOT A BROKEN INSTALL, AND THE OLD WORDING READ LIKE ONE. Found
        # 2026-09-05 by walking the install as an outside tester would: after seeding the starter
        # set, doctor printed "crystals found: 3", every essence OK, exit 0, and then "none",
        # because `--ctx` defaults to empty and act-bound crystals match on CONTEXT. A first-hour
        # tester reads that pair as "installed it and nothing happened", which is precisely the
        # failure the starter set exists to prevent. Say which of the two it is.
        if not (ctx or "").strip():
            print("  no --ctx given, so nothing CAN match: act-bound crystals are selected by the")
            print("  text of the command you are about to run, never by the act alone.")
            print("  Try a real one:")
            print("    python3 scripts/crystal_registry.py doctor --act bash --ctx 'npm run build 2>&1 | tail -20'")
        else:
            print("  none (no essence-bearing crystal matched this act/context)")
    for c, _piece in got:
        print(f"  FIRE: {c.get('path')}")
    for c, why in blocked:
        print(f"  SUPPRESSED: {c.get('path')} ({why})")
    for c, _piece in starved:
        print(f"  DEFERRED: {c.get('path')} (matched but did not fit budget)")
    # ⛔ A BLOCKED VERDICT MUST NOT EXIT 0. Found in QC 2026-08-31: doctor printed
    # "BLOCKED" and returned success, so any caller keying on the exit code read a
    # store with undeliverable crystals as healthy. A status that travels one hop
    # gets louder while the thing it describes goes unchecked.
    undeliverable = any((c.get("essence_state") or "") != "OK" for c in crystals)
    if undeliverable:
        print()
        print("BLOCKED: at least one registered crystal is undeliverable because essence markers are missing or empty")
    if not crystals or undeliverable:
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main() or 0)


# ── DELIVERY TELEMETRY (2026-07-19) ──────────────────────────────────────────────────────────────
# The inject ledger holds LAST-delivery timestamps (for throttling) but no HISTORY, so the questions
# that decide whether the store is alive were unanswerable: which crystals actually fire, which NEVER
# fire (dead weight), which fire constantly (wallpaper risk — the inject-budget failure mode). This
# appends one line per delivery. Hot path: never raises, never blocks a hook.
DELIVERY_LOG = os.path.join(REPO, "memory", "corpus", "crystal-deliveries.jsonl")


def record_delivery(channel, path, score=None, event=None, act=None, session=None):
    try:
        # json is NOT a module-level import here (this file stays dep-thin for soul-boot), so import it
        # locally. First draft assumed it was in scope: NameError -> swallowed by the fail-open -> an
        # EMPTY log file and zero telemetry, silently. Fail-open without a proof is a silent death.
        import json, time
        os.makedirs(os.path.dirname(DELIVERY_LOG), exist_ok=True)
        with open(DELIVERY_LOG, "a") as f:
            f.write(json.dumps({"ts": int(time.time()), "channel": channel,
                                "crystal": os.path.basename(path or "?"),
                                "score": score, "event": event,
                                # Historical missing keys mean unknown, not a joinable session.
                                # ⛔ The PAYLOAD carries the real session_id; CLAUDE_SESSION_ID is
                                # UNSET under the hooks, so env-only made every row "unknown"
                                # and the join key could never populate. Caller passes it.
                                "session": session or os.environ.get("CLAUDE_SESSION_ID") or "unknown",
                                **({"act": act} if act is not None else {})}) + "\n")
    except Exception:
        pass    # telemetry must never cost a delivery
