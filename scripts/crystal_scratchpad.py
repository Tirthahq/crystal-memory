#!/usr/bin/env python3
"""crystal_scratchpad.py — the working memory a crystal is distilled FROM.

WHY THIS SHIPS WITH CRYSTALS. A crystal is a finished knowing: one thing, compressed, bound to an
action. But you do not arrive at a finished knowing directly. You notice something half-formed at
14:40 — a smell, a hunch, a thing that went wrong and you routed around — and by the next session it
is gone. **Crystals are the output of a pipeline whose input had nowhere to live.** This is the input.

It is deliberately NOT governed truth. Carry hypotheses to re-check here, not conclusions to trust.
The rule we use: *a line here is working memory; the moment it becomes a settled knowing, it graduates
into a crystal and comes out of here.*

⛔ AND THE PART THAT MAKES IT WORK AT ALL: **a scratchpad nobody reads at boot is a dead letter.**
Writing to a file a reader polls once, at start-up, is the whole failure. So this ships with a
`SessionStart` hook — the note arrives at the top of the next session without anyone opening a file.
If you only copy the markdown and not the hook, you have built a diary, not a memory.

⚠ BOUNDED ON PURPOSE. A boot channel has a budget, and an append-only file grows forever. Ours once
ran 503 lines against a 500-line read budget — and because the convention was to append at the BOTTOM,
everything carefully preserved landed in the one region a truncated reader never reaches. So: the
newest content goes at the TOP, only the first N lines are delivered, and the tool SAYS when it is
over budget instead of silently truncating.

  python3 scripts/crystal_scratchpad.py --seed        # create it, with the discipline written in
  python3 scripts/crystal_scratchpad.py --boot        # SessionStart hook JSON (what the hook runs)
  python3 scripts/crystal_scratchpad.py --show        # print what boot would deliver
  python3 scripts/crystal_scratchpad.py --selftest
"""
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCHPAD = os.path.join("memory", "scratchpad.md")
BOOT_LINES = 120          # what a session actually receives
WARN_LINES = 400          # past this, it wants a fold

TEMPLATE = """# Scratchpad — working memory, not governed truth

> **NEWEST AT THE TOP.** Only the first ~120 lines reach the next session, so anything appended at the
> bottom of a long file is written where no reader arrives.
>
> **What goes here:** a hunch to re-check · a thing that went wrong and you routed around · what you
> were mid-thought on · what you would start next. Cheap, one line, written at the moment.
>
> **What does NOT go here:** anything you would be upset to see wrong. This is not the truth layer.
> When a line here becomes a settled knowing, write it as a crystal and delete it from here.
>
> **Fold it when it gets long.** An append-only file with no prune step is a store that rots quietly.

## <today's date> — <what this session was>

-
"""



def _redacted(text):
    """Strip credential-shaped strings before the pad reaches a model's context.

    ⛔ The pad is delivered VERBATIM at every boot, so a secret pasted into it once travels on every
    future session until somebody notices. A commit gate cannot help: the pad is read from disk as it
    is now, committed or not. Fails OPEN on any error, because a redactor that crashes the delivery
    would silence the channel it exists to protect.
    """
    try:
        import redact
        return redact.redact(text)
    except Exception:
        return text

def path(repo=None):
    return os.path.join(repo or REPO, SCRATCHPAD)


def read(repo=None):
    try:
        with open(path(repo), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def boot_text(repo=None, limit=BOOT_LINES):
    """What the session receives. Returns '' when there is nothing worth saying.

    Empty or template-only ⇒ SILENCE. A boot channel that speaks when it has nothing teaches the
    reader to skip it, and then it is not a channel any more.
    """
    body = read(repo)
    if not body.strip():
        return ""
    lines = body.splitlines()
    # Drop the instructional header so the channel carries content, not its own manual.
    content = [l for l in lines if not l.startswith(">")]
    if not [l for l in content if l.strip() and not l.startswith("#") and l.strip() != "-"]:
        return ""                      # seeded but never written in
    shown, rest = content[:limit], max(0, len(content) - limit)
    out = ["📝 SCRATCHPAD — your own working memory from last time (not governed truth; re-check it):",
           ""] + shown
    if rest:
        out += ["", f"… {rest} more line(s) not shown. The newest is at the top; if something old still "
                    f"matters, move it up or make it a crystal."]
    if len(content) > WARN_LINES:
        out += ["", f"⚠ This scratchpad is {len(content)} lines. Fold it: promote what became true into "
                    f"crystals, archive the rest. An append-only store with no prune step rots quietly."]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--boot", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    if a.seed:
        p = path()
        if os.path.exists(p):
            print(f"already there: {SCRATCHPAD} (left alone)")
            return 0
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(TEMPLATE)
        print(f"seeded {SCRATCHPAD}")
        print("Now wire the SessionStart hook (see INSTALL.md) or it will never be read.")
        return 0

    text = boot_text()
    if a.show:
        print(text or "(nothing to deliver — empty or never written in)")
        return 0

    # --boot, or no flag: the hook contract. Silence is a valid answer and must exit 0.
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
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")

    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "memory"))
    p = os.path.join(d, SCRATCHPAD)

    check("a missing scratchpad is silence, not a crash", boot_text(d) == "")
    with open(p, "w") as fh:
        fh.write(TEMPLATE)
    check("a seeded-but-unwritten scratchpad stays silent", boot_text(d) == "")
    with open(p, "w") as fh:
        fh.write("# Scratchpad\n\n> instructions line\n\n## today\n\n- the hook fired twice and I ignored it\n")
    t = boot_text(d)
    check("a real note is delivered", "the hook fired twice" in t)
    check("the instructional header is NOT delivered", "instructions line" not in t)
    with open(p, "w") as fh:
        fh.write("# S\n\n" + "\n".join(f"- line {i}" for i in range(600)))
    t = boot_text(d)
    check("a long scratchpad is truncated, not dumped", t.count("- line ") <= BOOT_LINES)
    check("and it SAYS how much it withheld", "more line(s) not shown" in t)
    check("and it warns that the file wants a fold", "rots quietly" in t)
    check("the newest content survives truncation", "- line 0" in t and "- line 599" not in t)

    print("SELFTEST PASS" if ok else "SELFTEST FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
