#!/usr/bin/env python3
"""crystal_midflight.py — what a context compaction loses, saved at the moment it happens.

WHY THIS SHIPS. A long agent session is eventually compacted: the harness replaces the conversation
with a summary and carries on. The summary keeps the WORK and paraphrases the DECISIONS. Three things
do not survive it well, and each costs the human something specific:

    your own recent words   A paraphrase of an instruction is not the instruction. The costliest
                            loss is a correction sent MID-TURN, which a summary often drops.
    what is in flight       A background job started before the compaction is remembered only if
                            the summary happens to mention it. Otherwise it finishes into silence,
                            or the session starts it again.
    open loops              The unchecked items the session was working through, and the commits
                            that exist locally but were never pushed.

So this runs twice:

    PreCompact     --capture  writes memory/mid-flight.md from the hook payload's transcript_path
    SessionStart   --boot     delivers that file to the next context while it is fresh (< 24 h)

⛔ A CAPTURE NOTHING AT BOOT DELIVERS IS NOT A CAPTURE. The version of this hook in the repo it came
from first wrote its notes into the scratchpad and trimmed the pad to fit, so the capture reached boot
only through the file it was cutting. It also drained the hook payload and IGNORED it, which is where
`transcript_path` lives. Both are why this file owns its own boot delivery and reads the payload first.

⚠ IT NEVER SUMMARISES THE SESSION. The harness already does that. This keeps only what a summary
loses, verbatim, and marks the parts it could not read rather than leaving them out.

  python3 scripts/crystal_midflight.py --capture < payload.json   # what the PreCompact hook runs
  python3 scripts/crystal_midflight.py --boot                      # SessionStart hook JSON
  python3 scripts/crystal_midflight.py --show                      # print what boot would deliver
  python3 scripts/crystal_midflight.py --selftest

Optional: name long-running processes worth reporting as in flight (comma-separated pgrep patterns):
  CRYSTAL_INFLIGHT_PATTERNS="pytest,npm run build"
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIDFLIGHT = os.path.join("memory", "mid-flight.md")
MARK = "⚠ COMPACTED MID-FLIGHT"
N_MESSAGES = 12          # of the human's most recent messages, verbatim
MSG_CHARS = 700
JOB_WINDOW_H = 6         # background output touched this recently counts as in flight
MAX_AGE_H = 24           # older than this, boot stays silent: it describes a different session
BOOT_CAP = 3500          # chars delivered at boot
OPEN_BOX = re.compile(r"^\s*[-*]\s+\[ \]\s+\S", re.M)

# Harness-injected user-role text that is not the human speaking.
NOISE = ("Base directory for this skill", "<local-command", "<command-", "Caveat:",
         "<agent-message", "<task-notification", "[SYSTEM NOTIFICATION", "<system-reminder")


def _redacted(text):
    """Credential-shaped strings are stripped before the file is written AND before boot delivers it.

    The human's words are saved verbatim, and people paste keys into chats. Fails OPEN, because a
    redactor that crashes would cost the whole capture.
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import redact
        return redact.redact(text)
    except Exception:
        return text


def _sh(args, repo, timeout=10):
    try:
        return subprocess.run(args, cwd=repo, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except Exception:
        return ""


def human_messages(transcript_path, n=N_MESSAGES):
    """The human's own words, oldest first: normal turns AND mid-turn queued messages.

    A normal turn is a `type: user` row whose content is a STRING (tool results are lists). A message
    typed while the agent was working arrives as `type: attachment` with `attachment.type ==
    queued_command`, and it is exactly the one most likely to be a correction.
    """
    out = []
    try:
        fh = open(transcript_path, encoding="utf-8")
    except (OSError, TypeError):
        return None
    with fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            text = None
            if d.get("type") == "user":
                c = (d.get("message") or {}).get("content")
                if isinstance(c, str):
                    text = c
            elif d.get("type") == "attachment":
                a = d.get("attachment") or {}
                if isinstance(a, dict) and a.get("type") == "queued_command":
                    text = a.get("prompt")
            if not isinstance(text, str) or not text.strip():
                continue
            t = text.strip()
            if t.startswith(NOISE):
                continue
            out.append((str(d.get("timestamp", ""))[:16].replace("T", " "), t))
    return out[-n:]


def in_flight(repo, now=None):
    """Background output touched recently, plus any processes the user asked us to look for."""
    now = now or time.time()
    lines = []
    roots = {tempfile.gettempdir(), "/tmp", "/private/tmp"}
    seen, jobs = set(), []
    for root in roots:
        for f in glob.glob(os.path.join(root, "claude-*", "*", "*", "tasks", "*.output")):
            real = os.path.realpath(f)
            if real in seen:
                continue
            seen.add(real)
            try:
                age = (now - os.path.getmtime(f)) / 3600
            except OSError:
                continue
            if age < JOB_WINDOW_H:
                jobs.append((age, f))
    for age, f in sorted(jobs)[:10]:
        lines.append("  · background output %s (%s B, touched %.0f min ago). Check it before assuming the job "
                     "finished or failed; an agent's output is large, so read its tail, not the whole file."
                     % (f, format(os.path.getsize(f), ","), age * 60))
    for pat in [p.strip() for p in os.environ.get("CRYSTAL_INFLIGHT_PATTERNS", "").split(",") if p.strip()]:
        for pid in [x for x in _sh(["pgrep", "-f", pat], repo).split() if x.isdigit()][:5]:
            lines.append("  · running (pid %s) matching %r" % (pid, pat))
    return lines or ["  · nothing detected running"]


def open_loops(repo, now=None):
    """Unchecked `- [ ]` items in notes touched in the last day, and commits not yet pushed."""
    now = now or time.time()
    rows = []
    mem = os.path.join(repo, "memory")
    for dirpath, _dirs, files in os.walk(mem):
        for f in files:
            if not f.endswith(".md") or f == os.path.basename(MIDFLIGHT):
                continue
            p = os.path.join(dirpath, f)
            try:
                if now - os.path.getmtime(p) > MAX_AGE_H * 3600:
                    continue
                with open(p, encoding="utf-8", errors="replace") as fh:
                    n = len(OPEN_BOX.findall(fh.read()))
            except OSError:
                continue
            if n:
                rows.append("  · %s: %d unchecked item(s)" % (os.path.relpath(p, repo), n))
    ahead = _sh(["git", "rev-list", "--count", "@{upstream}..HEAD"], repo)
    if ahead.isdigit() and int(ahead):
        rows.append("  · %s local commit(s) NOT PUSHED. A local commit is not a delivered one." % ahead)
    return rows or ["  · none found"]


def _safe(fn, *args):
    """One broken collector must never cost the whole file."""
    try:
        return fn(*args)
    except Exception as exc:
        return ["  · ⚠ %s failed: %s" % (fn.__name__, exc)]


def build(payload, repo=None):
    repo = repo or REPO
    stamp = time.strftime("%Y-%m-%d %H:%M")
    msgs = human_messages(payload.get("transcript_path")) if payload.get("transcript_path") else None
    dirty = [l for l in _sh(["git", "status", "--porcelain"], repo).splitlines() if l.strip()]
    L = ["---", "name: mid-flight",
         "description: Written by the PreCompact hook at %s. Your latest words verbatim, what was in flight, "
         "and open loops at the moment of compaction. Overwritten at every compaction." % stamp,
         "---", "",
         "# %s — %s" % (MARK, stamp),
         "The compaction summary carries the work and paraphrases the decisions. This keeps what it loses.",
         "", "## Your most recent messages (verbatim, oldest first; mid-turn ones included)"]
    if msgs is None:
        L.append("- ⚠ the transcript was not readable by the hook (payload had no usable transcript_path)")
    elif not msgs:
        L.append("- (no messages from you in the transcript)")
    else:
        for ts, t in msgs:
            t = t.replace("\n", " ")
            L.append("- [%s] %s%s" % (ts, t[:MSG_CHARS], " …" if len(t) > MSG_CHARS else ""))
    L += ["", "## In flight at compaction (check each before assuming it finished or failed)"]
    L += _safe(in_flight, repo)
    L += ["", "## Open loops"] + _safe(open_loops, repo)
    L += ["", "## Git",
          "  · HEAD: %s" % (_sh(["git", "log", "--oneline", "-1"], repo) or "(no commits)"),
          "  · uncommitted files: %d" % len(dirty), ""]
    return _redacted("\n".join(L))


def capture(payload, repo=None):
    repo = repo or REPO
    p = os.path.join(repo, MIDFLIGHT)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(build(payload, repo))
    return p


def boot_text(repo=None, now=None, max_age_h=MAX_AGE_H):
    """The file's body while it is fresh; silence when absent or stale."""
    repo = repo or REPO
    p = os.path.join(repo, MIDFLIGHT)
    now = now or time.time()
    try:
        age_h = (now - os.path.getmtime(p)) / 3600
        if age_h > max_age_h:
            return ""
        with open(p, encoding="utf-8") as fh:
            body = re.sub(r"\A---\n.*?\n---\n", "", fh.read(), count=1, flags=re.S).strip()
    except OSError:
        return ""
    if not body:
        return ""
    if len(body) > BOOT_CAP:
        body = body[:BOOT_CAP] + "\n… (full: %s)" % MIDFLIGHT
    return "━━ MID-FLIGHT (written by the PreCompact hook %.1f h ago) ━━\n%s" % (age_h, body)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--boot", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.capture:
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            payload = {}
        try:
            p = capture(payload if isinstance(payload, dict) else {})
            print("PreCompact: wrote %s (your latest words, in-flight jobs, open loops); "
                  "delivered at the next SessionStart." % os.path.relpath(p, REPO))
        except Exception as exc:
            print("PreCompact: ⛔ mid-flight capture FAILED (%s). Nothing was saved for after the compaction."
                  % type(exc).__name__)
        return 0                         # a hook must never block the compaction
    text = boot_text()
    if a.show:
        print(text or "(nothing to deliver: no mid-flight file, or it is older than %d h)" % MAX_AGE_H)
        return 0
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                 "additionalContext": _redacted(text)}}))
    return 0


def selftest():
    import shutil
    ok = True

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print("  [%s] %s" % ("ok" if cond else "FAIL", name))

    d = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(d, "memory", "plans"))
        tr = os.path.join(d, "transcript.jsonl")
        rows = [
            {"type": "user", "timestamp": "2026-01-01T09:00:00Z", "message": {"content": "first instruction"}},
            {"type": "user", "timestamp": "2026-01-01T09:01:00Z",
             "message": {"content": [{"type": "tool_result", "content": "tool noise"}]}},
            {"type": "user", "timestamp": "2026-01-01T09:02:00Z",
             "message": {"content": "Base directory for this skill: /x\nskill body"}},
            {"type": "assistant", "timestamp": "2026-01-01T09:03:00Z", "message": {"content": "assistant text"}},
            {"type": "attachment", "timestamp": "2026-01-01T09:04:00Z",
             "attachment": {"type": "queued_command", "prompt": "actually, stop and use the other branch"}},
            {"type": "user", "timestamp": "2026-01-01T09:05:00Z",
             "message": {"content": "my key is sk-ant-abcdefghijklmnopqrstuvwxyz0123 please use it"}},
        ]
        with open(tr, "w") as fh:
            fh.write("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")
        msgs = human_messages(tr)
        texts = [t for _, t in msgs]
        check("the human's normal turns are captured", "first instruction" in texts)
        # MUTATION: drop the attachment branch in human_messages and this row goes red.
        check("a MID-TURN queued message is captured (the one a summary drops)",
              "actually, stop and use the other branch" in texts)
        check("tool results, skill bodies and assistant text are not", not any(
            x in " ".join(texts) for x in ("tool noise", "skill body", "assistant text")))
        q = "actually, stop and use the other branch"
        check("oldest first", q in texts and texts.index("first instruction") < texts.index(q))
        with open(tr, "a") as fh:
            for i in range(30):
                fh.write(json.dumps({"type": "user", "message": {"content": "msg %d" % i}}) + "\n")
        check("only the most recent N are kept", len(human_messages(tr)) == N_MESSAGES
              and human_messages(tr)[-1][1] == "msg 29")

        with open(os.path.join(d, "memory", "plans", "list.md"), "w") as fh:
            fh.write("- [x] done\n- [ ] still open\n- [ ] also open\n")
        p = capture({"transcript_path": tr}, d)
        body = open(p, encoding="utf-8").read()
        check("--capture writes memory/mid-flight.md", os.path.exists(p) and MARK in body)
        check("open checklist items are counted as open loops", "memory/plans/list.md: 2 unchecked" in body)
        check("a pasted key is REDACTED in the saved file", "sk-ant-abcdefghijklmnopqrstuvwxyz0123" not in body)

        t = boot_text(d)
        check("boot DELIVERS a fresh capture", MARK in t and "msg 29" in t)
        old = time.time() - (MAX_AGE_H + 1) * 3600
        os.utime(p, (old, old))
        check("a capture older than the window stays SILENT at boot", boot_text(d) == "")

        p2 = capture({}, d)
        check("no transcript_path is SAID, not silently empty",
              "transcript was not readable" in open(p2, encoding="utf-8").read())
        check("no mid-flight file at all is silence, not a crash", boot_text(tempfile.mkdtemp()) == "")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("SELFTEST PASS" if ok else "SELFTEST FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
