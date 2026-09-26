#!/usr/bin/env python3
"""crystal_uncommitted.py — at boot, say which uncommitted files look like LOST WORK.

WHY THIS SHIPS. An agent that works for hours leaves files it wrote and never committed. Some of that
is deliberate (a draft held on purpose, named in the handoff), some is generated (logs, a regenerated
index), and some is work that simply fell out of the session: written, never committed, never
mentioned again. From `git status` the three look identical.

⛔ THE FRAMING THIS REPLACES. The repo this came from printed its uncommitted files at boot under the
line "a decision, not drift: check the handoff for the why". That was meant to stop a session from
reconciling state it did not understand, and it did. It also let hundreds of files sit uncommitted for
up to fifty days, including evidence a published paper depended on, because every one of them was
presumed to be a decision. **A file is a decision only where something NAMES it.** Unnamed, old and
hand-written, it is at risk, and the boot line should say so.

The first run on the real tree found 2 of 89 uncommitted files in that state. Both were real: a
16-line record of a sent email, uncommitted for three days, and a regenerated page.

THE FOUR BUCKETS, in the order they are decided:
    generated  logs, jsonl, anything under scratch/, or a tracked .md whose ONLY change is the
               Librarian's generated "Referenced by" block. Regenerable, so never at risk.
    held       named (by path or file name) in the newest handoff or in the scratchpad.
               Somebody said why; that is what makes it a decision.
    recent     modified within the last LOST_AGE_H hours. Probably still in progress.
    lost       everything else: hand-written, older than LOST_AGE_H, named nowhere.

⚠ IT NEVER COMMITS, STASHES OR DELETES ANYTHING. It reports. What to do with a file is a judgement,
and the fix is either a commit or a line in the handoff saying why the file waits.

  python3 scripts/crystal_uncommitted.py --boot       # SessionStart hook JSON (silent when nothing is at risk)
  python3 scripts/crystal_uncommitted.py --show       # print all four buckets
  python3 scripts/crystal_uncommitted.py --selftest

Extra generated locations (comma-separated path prefixes) can be declared without editing this file:
  CRYSTAL_GENERATED_PREFIXES="build/,site/" python3 scripts/crystal_uncommitted.py --show
"""
import argparse
import json
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOST_AGE_H = 12
LIST_LIMIT = 12
GENERATED_PREFIXES = ("scratch/",)
GENERATED_SUFFIXES = (".jsonl", ".log", ".out", ".pyc")
SIGN_MARKERS = ("LIBRARIAN:signs", "Referenced by")


def _git(args, repo, strict=False):
    """stdout, or "" on failure. strict=True returns None on failure instead, so a caller that must
    not read "could not look" as "nothing there" can tell the two apart."""
    try:
        r = subprocess.run(["git"] + args, cwd=repo, capture_output=True, text=True)
        ok, out = r.returncode == 0, r.stdout
    except Exception:
        ok, out = False, ""
    if ok:
        return out
    return None if strict else ""


def uncommitted(repo=None):
    """Every modified, added or untracked FILE (not directory), from `git status -z -uall`.

    -z so a path with spaces or unicode arrives unquoted; -uall so an untracked directory is listed as
    its files, because the file is the unit that gets lost.
    """
    repo = repo or REPO
    raw = _git(["status", "--porcelain", "-z", "-uall"], repo, strict=True)
    if raw is None:
        return None                     # could not look: NOT the same as a clean tree
    out, parts, i = [], raw.split("\0"), 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        xy, path = entry[:2], entry[3:]
        if "R" in xy or "C" in xy:
            i += 1                      # a rename carries its OLD path as the next field
        if "D" in xy:
            continue                    # a deletion has no file left to lose
        if "__pycache__/" in path:
            continue
        out.append(path)
    return out


def _signs_only(path, repo):
    """A tracked .md whose only change is the Librarian's generated backlinks block is regenerable.

    Untracked or non-.md files are never signs-only: with no diff there is nothing to prove it.
    """
    if not path.endswith(".md"):
        return False
    d = _git(["diff", "-U0", "--", path], repo)
    if not d.strip():
        return False
    real = [x for x in d.splitlines()
            if x[:1] in "+-" and not x.startswith(("+++", "---")) and x[1:].strip()
            and not any(m in x for m in SIGN_MARKERS)]
    return not real


def _naming_text(repo):
    """What counts as NAMING a file: the newest handoff plus the scratchpad. Missing either is fine."""
    text = ""
    sys.path.insert(0, os.path.join(repo, "scripts"))
    try:
        import crystal_handoff
        files = crystal_handoff.handoffs(repo)
        if files:
            with open(files[0], encoding="utf-8") as fh:
                text += fh.read()
    except Exception:
        pass
    try:
        with open(os.path.join(repo, "memory", "scratchpad.md"), encoding="utf-8") as fh:
            text += fh.read()
    except OSError:
        pass
    return text


def classify(files, repo=None, now=None, age_h=LOST_AGE_H):
    """Split paths into (lost, held, generated, recent). `lost` is a list of (path, age_hours), oldest first."""
    repo = repo or REPO
    now = now or time.time()
    extra = tuple(p.strip() for p in os.environ.get("CRYSTAL_GENERATED_PREFIXES", "").split(",") if p.strip())
    prefixes = GENERATED_PREFIXES + extra
    named = _naming_text(repo)
    lost, held, gen, recent = [], [], [], []
    for f in files:
        if f.startswith(prefixes) or f.endswith(GENERATED_SUFFIXES) or _signs_only(f, repo):
            gen.append(f)
            continue
        if f in named or os.path.basename(f) in named:
            held.append(f)
            continue
        try:
            age = (now - os.path.getmtime(os.path.join(repo, f))) / 3600
        except OSError:
            age = 0.0
        if age > age_h:
            lost.append((f, age))
        else:
            recent.append(f)
    lost.sort(key=lambda x: -x[1])
    return lost, held, gen, recent


def report(repo=None, full=False):
    repo = repo or REPO
    if _git(["rev-parse", "--is-inside-work-tree"], repo).strip() != "true":
        return ""                       # not a git repo: there is nothing this can say
    files = uncommitted(repo)
    if files is None:
        # ⛔ Inside a repo, a failed `git status` must not read as "nothing at risk".
        return "📌 UNCOMMITTED: ⚠ `git status` failed, so lost work could not be checked. Run it by hand."
    if not files:
        return ""
    lost, held, gen, recent = classify(files, repo)
    if not lost and not full:
        return ""                       # nothing at risk: a boot line that always speaks gets skipped
    out = ["📌 UNCOMMITTED (%d files): a decision only where the handoff or scratchpad NAMES it." % len(files)]
    if lost:
        out.append("  ⚠ POSSIBLY LOST WORK: %d hand-written file(s) older than %dh, named nowhere. "
                   "Commit each, or name it in the handoff with the reason it waits:" % (len(lost), LOST_AGE_H))
        for f, age in lost[:LIST_LIMIT]:
            out.append("     · %s  (%.0fh)" % (f, age))
        if len(lost) > LIST_LIMIT:
            out.append("     … and %d more" % (len(lost) - LIST_LIMIT))
    out.append("  held (named): %d · generated: %d · recent (<%dh, in progress): %d   full list: git status"
               % (len(held), len(gen), LOST_AGE_H, len(recent)))
    if full:
        for name, bucket in (("held", held), ("generated", gen), ("recent", recent)):
            for f in bucket:
                out.append("     %-9s %s" % (name, f))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--boot", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.show:
        print(report(full=True) or "(no uncommitted files)")
        return 0
    try:
        text = report()
    except Exception:
        text = ""                       # a boot hook must never fail the session start
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))
    return 0


def selftest():
    import shutil
    import tempfile
    ok = True

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print("  [%s] %s" % ("ok" if cond else "FAIL", name))

    d = tempfile.mkdtemp()
    try:
        def w(rel, body, age_h=None):
            p = os.path.join(d, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
            if age_h is not None:
                t = time.time() - age_h * 3600
                os.utime(p, (t, t))

        def g(*args):
            subprocess.run(["git"] + list(args), cwd=d, capture_output=True, check=True)

        g("init", "-q")
        g("config", "user.email", "t@example.invalid")
        g("config", "user.name", "t")
        w("memory/notes/node.md", "# node\n\nbody\n")
        w("memory/notes/edited.md", "# edited\n\nbody\n")
        g("add", "-A")
        g("commit", "-qm", "base")

        check("a clean tree is silent at boot", report(d) == "")

        w("docs/forgotten draft.md", "an old paragraph nobody committed\n", age_h=72)
        w("docs/held.md", "waiting on a reply\n", age_h=72)
        w("docs/in-progress.md", "being written now\n", age_h=1)
        w("run.log", "noise\n", age_h=72)
        w("scratch/ledger.json", "{}\n", age_h=72)
        w("memory/notes/node.md", "# node\n\nbody\n\n<!-- LIBRARIAN:signs (generated) -->\n"
          "↩ **Referenced by** (1): [[x]]\n<!-- /LIBRARIAN:signs -->\n", age_h=72)
        w("memory/notes/edited.md", "# edited\n\nbody, and a real sentence added by hand\n", age_h=72)
        w("memory/handoffs/handoff-2026-01-01.md", "## Next action\n- docs/held.md waits on a reply\n", age_h=1)

        files = uncommitted(d)
        check("a path with a space arrives whole (the -z parse)", "docs/forgotten draft.md" in files)
        lost, held, gen, recent = classify(files, d)
        lost_paths = [f for f, _ in lost]
        check("an old, unnamed, hand-written file is LOST", "docs/forgotten draft.md" in lost_paths)
        check("a hand edit to a tracked note is LOST when old and unnamed", "memory/notes/edited.md" in lost_paths)
        check("a file named in the handoff is HELD, not lost", "docs/held.md" in held and "docs/held.md" not in lost_paths)
        check("a recent file is in progress, not lost", "docs/in-progress.md" in recent)
        check("a .log and scratch/ are generated", "run.log" in gen and "scratch/ledger.json" in gen)
        # MUTATION: make _signs_only return False and this row goes red (the note lands in `lost`).
        check("a signs-only Librarian diff is generated, not lost", "memory/notes/node.md" in gen)
        t = report(d)
        check("boot SPEAKS when something is at risk, and names the file", "POSSIBLY LOST WORK" in t
              and "docs/forgotten draft.md" in t)
        check("and does not list held or generated files as lost", "run.log" not in t.split("held (named)")[0])

        os.environ["CRYSTAL_GENERATED_PREFIXES"] = "docs/"
        try:
            lost2, _, gen2, _ = classify(uncommitted(d), d)
        finally:
            del os.environ["CRYSTAL_GENERATED_PREFIXES"]
        check("a declared generated prefix moves files out of lost",
              "docs/forgotten draft.md" in gen2 and "docs/forgotten draft.md" not in [f for f, _ in lost2])

        nogit = tempfile.mkdtemp()
        check("outside a git repo it is silent, not a crash", report(nogit) == "")
        real_git = _git
        globals()["_git"] = lambda args, repo, strict=False: (
            (None if strict else "") if args[0] == "status" else real_git(args, repo, strict))
        try:
            check("inside a repo, a FAILED git status is said, never read as clean",
                  "could not be checked" in report(d))
        finally:
            globals()["_git"] = real_git
        shutil.rmtree(nogit, ignore_errors=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("SELFTEST PASS" if ok else "SELFTEST FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
