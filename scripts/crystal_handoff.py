#!/usr/bin/env python3
"""crystal_handoff.py — the third horizon: what survives a context reset.

WHY THIS SHIPS. The other two pieces cover shorter spans and neither covers this one:

    the ACT      crystal_act.py        a knowing arrives at the moment of the command
    the SESSION  crystal_scratchpad.py working memory survives to the next boot
    the RESET    this file             what the session WAS survives the session ending

A scratchpad holds live working memory: open threads, the hunch not yet proven, the thing
deliberately left undone. A handoff is the other shape — the CLOSED record of a span of work,
written once at the end and read once at the start. Without it the next session rebuilds the
situation from commits and files: it recovers the facts and loses the reasoning, and the cost lands
on the HUMAN as re-explaining their own project to their own agent.

⛔ THE DESIGN RULE THAT MATTERS, AND IT IS THE REASON THIS IS NOT A PROMPT TEMPLATE: **the machine
fills only what it can PROVE, and leaves every judgement to whoever writes it.** The "what shipped"
section is generated from `git log`, so it cannot contain a claim with no commit behind it — which is
the single most common lie in a handoff, and the most expensive, because the next session believes
it. Everything that requires judgement (why it matters, what did not work, what is blocked and on
whom) is written as an explicit prompt and stays visibly unanswered until somebody answers it.

⚠ AND THE BOOT CHANNEL IS SHARED. The scratchpad already speaks at SessionStart. So this delivers the
NARROW thing at boot — the pointer, the next action, and what is blocked — never the whole document.
A second channel that dumps a full document at boot does not add a channel, it starves the first one.

  python3 scripts/crystal_handoff.py --new            # draft today's, prefilled with the provable facts
  python3 scripts/crystal_handoff.py --boot           # SessionStart hook JSON (what the hook runs)
  python3 scripts/crystal_handoff.py --show           # print what boot would deliver
  python3 scripts/crystal_handoff.py --list
  python3 scripts/crystal_handoff.py --selftest
"""
import argparse
import datetime
import glob
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HANDOFF_DIR = os.path.join("memory", "handoffs")
BOOT_LINES = 40            # narrow on purpose: the scratchpad shares this channel

UNANSWERED = "<!-- unanswered -->"

SKELETON = """# Handoff — {stamp}

## Next action
{u} one line. What would you start if you opened this cold in the morning?

## Blocked, and on whom
{u} name the person or the decision. "Nobody" is a valid and useful answer.

## Why / the heart of it
{u} what this span of work was actually about, and what it cost to learn. A handoff of pure
{u} facts hands the next reader a clean room with no reason to care.

## What did NOT work
{u} the dead ends, in one line each. This is the highest-value section and the first one people
{u} skip, because nothing in a commit log records the path you abandoned.

## What shipped — GENERATED, do not hand-edit
{shipped}

## Notes
-
"""


def _redacted(text):
    """Strip credential-shaped strings before this reaches a model's context.

    Same argument as the scratchpad: a handoff is delivered verbatim at boot, so a key pasted into
    one travels on every future session. Fails OPEN, because a redactor that crashes the delivery
    would silence the channel it exists to protect.
    """
    try:
        import redact
        return redact.redact(text)
    except Exception:
        return text


def _git(args, repo=None):
    try:
        r = subprocess.run(["git"] + args, cwd=repo or REPO, capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def directory(repo=None):
    return os.path.join(repo or REPO, HANDOFF_DIR)


NAME_RE = re.compile(r"handoff-(\d{4}-\d{2}-\d{2})(?:-(\d+))?\.md$")


def _order_key(path):
    """(day, sequence) — NOT the raw filename.

    ⛔ MEASURED BY THIS FILE'S OWN SELFTEST, first run: a plain reverse string sort puts
    `handoff-2026-01-01.md` ABOVE `handoff-2026-01-01-2.md`, because `-` (0x2D) sorts below `.`
    (0x2E). So the SECOND handoff of a day — the newer one — was returned as the older, and boot
    delivered the stale document. A same-day suffix is exactly the case a busy day produces, so the
    defect would have waited for the first day anyone needed it.
    🔑 A filename that sorts correctly for the common case can invert for the variant, and nothing
    about the wrong answer looks wrong. Parse the key; do not trust the lexicographic accident.
    """
    m = NAME_RE.search(os.path.basename(path))
    return (m.group(1), int(m.group(2) or 1)) if m else ("", 0)


def handoffs(repo=None):
    """Newest first, by (day, same-day sequence) parsed out of the name."""
    return sorted(glob.glob(os.path.join(directory(repo), "handoff-*.md")),
                  key=_order_key, reverse=True)


def shipped_block(repo=None, since=None):
    """The provable half: real commits, real hashes, straight out of git.

    ⛔ Never a model's summary of what it thinks it did. `git log` is the only witness here that
    cannot be mistaken about whether the work exists.
    """
    since = since or "24 hours ago"
    log = _git(["log", "--since=" + since, "--pretty=format:%h  %s"], repo)
    if not log:
        return ("_No commits in the window. That is a fact, not a failure — say in **Notes** what the\n"
                "time went into, because a handoff with no commits and no explanation reads as a lost day._")
    rows = [l for l in log.splitlines() if l.strip()]
    stat = _git(["diff", "--shortstat", "HEAD~%d" % len(rows), "HEAD"], repo) if rows else ""
    head = _git(["rev-parse", "--short", "HEAD"], repo)
    out = ["| commit | what |", "|---|---|"]
    for row in rows[:40]:
        h, _, subj = row.partition("  ")
        out.append("| `%s` | %s |" % (h, subj.replace("|", "\\|")))
    if len(rows) > 40:
        out.append("| … | %d more |" % (len(rows) - 40))
    tail = ["", "%d commit(s). HEAD `%s`." % (len(rows), head)]
    if stat:
        tail.append(stat.strip())
    tail.append("")
    tail.append("⚠ A local commit is not a delivered one. Confirm it left this machine before you call "
                "any of it done: `git cat-file -t <hash>` on the remote, or `git status -sb` for ahead/behind.")
    return "\n".join(out + tail)


def new(repo=None, since=None, stamp=None):
    """Write today's draft. Never overwrites: a second one today gets a -2, -3 suffix."""
    d = directory(repo)
    os.makedirs(d, exist_ok=True)
    day = stamp or datetime.date.today().isoformat()
    p = os.path.join(d, "handoff-%s.md" % day)
    n = 1
    while os.path.exists(p):
        n += 1
        p = os.path.join(d, "handoff-%s-%d.md" % (day, n))
    body = SKELETON.format(stamp=day if n == 1 else "%s (%d)" % (day, n),
                           u=UNANSWERED, shipped=shipped_block(repo, since))
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(body)
    return p


def _section(text, title):
    m = re.search(r"^##\s+%s\s*$(.*?)(?=^##\s|\Z)" % re.escape(title), text, re.M | re.S)
    return m.group(1).strip() if m else ""


def boot_text(repo=None, limit=BOOT_LINES):
    """The narrow delivery: pointer + next action + blocked. Silence when nothing is answered.

    An unanswered skeleton must stay SILENT. Announcing a document whose every section is still a
    prompt trains the reader to skip the channel, and a skipped channel is not a channel.
    """
    files = handoffs(repo)
    if not files:
        return ""
    newest = files[0]
    try:
        with open(newest, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return ""
    nxt, blocked = _section(text, "Next action"), _section(text, "Blocked, and on whom")
    answered = [s for s in (nxt, blocked) if s and UNANSWERED not in s]
    if not answered:
        return ""
    rel = os.path.relpath(newest, repo or REPO)
    out = ["🔀 HANDOFF — the last session closed with this. Full document: %s" % rel, ""]
    if nxt and UNANSWERED not in nxt:
        out += ["NEXT ACTION:", nxt, ""]
    if blocked and UNANSWERED not in blocked:
        out += ["BLOCKED:", blocked, ""]
    out.append("Everything else (what shipped, what did not work, the why) is in the document. "
               "Open it before you start, not after you are confused.")
    lines = "\n".join(out).splitlines()
    if len(lines) > limit:
        lines = lines[:limit] + ["", "… truncated. Open %s." % rel]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--new", action="store_true")
    ap.add_argument("--since", help="git --since window for the shipped table (default: 24 hours ago)")
    ap.add_argument("--boot", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    if a.new:
        p = new(since=a.since)
        print("wrote %s" % os.path.relpath(p, REPO))
        print("The shipped table is generated. Answer the four prompts; an unanswered handoff stays")
        print("silent at boot on purpose, so a skeleton nobody filled in cannot masquerade as a record.")
        return 0

    if a.list:
        found = handoffs()
        if not found:
            print("no handoffs yet — python3 scripts/crystal_handoff.py --new")
        for f in found:
            print(os.path.relpath(f, REPO))
        return 0

    text = boot_text()
    if a.show:
        print(text or "(nothing to deliver — no handoff, or none with its prompts answered)")
        return 0

    if a.boot or True:
        if text:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                     "additionalContext": _redacted(text)}}))
        return 0


def selftest():
    import tempfile
    ok = True

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print("  [%s] %s" % ("ok" if cond else "FAIL", name))

    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "memory"))

    check("no handoff at all is silence, not a crash", boot_text(d) == "")

    p = new(repo=d, stamp="2026-01-01")
    check("--new writes a file", os.path.exists(p))
    check("a fresh skeleton stays SILENT at boot", boot_text(d) == "")

    p2 = new(repo=d, stamp="2026-01-01")
    check("a second handoff the same day does NOT overwrite the first", p2 != p and os.path.exists(p))

    body = open(p2).read().replace(
        UNANSWERED + " one line. What would you start if you opened this cold in the morning?",
        "finish the arrival layer and re-run the frozen list")
    open(p2, "w").write(body)
    t = boot_text(d)
    check("an ANSWERED next action is delivered", "finish the arrival layer" in t)
    check("an unanswered section is NOT delivered", UNANSWERED not in t)
    check("and it names the document rather than pasting it", "handoff-2026-01-01-2.md" in t)
    check("the SAME-DAY SUFFIX is ordered newest-first (a raw string sort inverts this)",
          os.path.basename(handoffs(d)[0]) == "handoff-2026-01-01-2.md")
    check("the generated shipped table is not dumped into the boot channel",
          "| commit |" not in t)

    # the one that matters: the generated half cannot carry an unverified claim, because it is
    # produced from git and a tree with no commits produces no rows.
    ship = shipped_block(repo=d)
    check("a repo with no commits yields NO shipped rows", "| commit |" not in ship)
    check("and it says so instead of leaving a blank the reader fills in", "No commits in the window" in ship)

    long_body = open(p2).read().replace(
        UNANSWERED + " name the person or the decision. \"Nobody\" is a valid and useful answer.",
        "\n".join("blocker %d" % i for i in range(200)))
    open(p2, "w").write(long_body)
    t = boot_text(d)
    check("a long handoff is truncated, not dumped", len(t.splitlines()) <= BOOT_LINES + 2)

    print("SELFTEST PASS" if ok else "SELFTEST FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
