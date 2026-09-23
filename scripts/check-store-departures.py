#!/usr/bin/env python3
"""
check-store-departures.py — WHAT LEFT THE STORE, WHEN, AND WHY.

⛔ WHY THIS EXISTS (Tom, 2026-09-22, after we lost a box to an unbounded cache):
*"been thinking about the eviction policy because that is the key to staying present"* — and then
*"make it observable then, what left and why."*

A store that forgets is not a broken store; forgetting well is a CAPABILITY we have measured
(LongMemEval: compressed memory matched full-history accuracy at 8.0x fewer tokens). But an eviction
policy is a CLAIM ABOUT WHAT MATTERS, so it can be wrong in the dangerous direction: silently dropping
the thing you needed, while looking exactly like a healthy store. That failure has the same signature
as the one we found this morning — a frozen channel and a healthy one are indistinguishable from
outside — so it needs the same treatment: a number, at boot, that cannot be confused with silence.

📏 THE STATE THAT PROMPTED IT, measured 2026-09-22:
    248 archived .md files across 5 `_archive` trees  ·  0 rows of recorded reason
`crystal-retire.py` was BUILT with an append-only tombstone ledger and its file has never existed.
`node-cleaner.py` moves nodes to `_archive/` and writes no ledger at all. So the store's entire
history of departures is: they are gone, and nobody wrote down why.

🔑 THE ASYMMETRY THIS CORRECTS. We treat "what is worth KEEPING" as a decision only a human may make
(a crystal is minted by a person, never by a pipeline). We have been treating "what is worth
FORGETTING" as a chore — a flag nobody set. It is the same decision wearing the other face.

⛔ NOT A GATE AND NOT A QUOTA. It never blocks a commit and never stops a cleaner. Exit 2 is a
FINDING — departures with no recorded reason — not a refusal. Nothing may branch on it.

  python3 scripts/check-store-departures.py            # the report; exit 2 if any departure is silent
  python3 scripts/check-store-departures.py --boot     # one line
  python3 scripts/check-store-departures.py --record --path <p> --why "<reason>" --by <tool>
  python3 scripts/check-store-departures.py --selftest

# INVOKED-BY: state-snapshot
# NEGATIVE-CONTROL: mkdir -p "$NC/memory/x/_archive" && touch "$NC/memory/x/_archive/gone.md" && python3 "$REPO/scripts/check-store-departures.py" --root "$NC"
#  (expect: an archived node with no ledger row prints SILENT and exits 2)
"""
import argparse, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LEDGER_REL = Path("memory") / "claude" / "store-departures.jsonl"


def ledger_path(root):
    return Path(root) / LEDGER_REL


def departed(root):
    """Ground truth: every .md sitting in an _archive tree. These are OUT of the live store."""
    out = []
    mem = Path(root) / "memory"
    if not mem.is_dir():
        return out
    for p in mem.rglob("*.md"):
        # ⚠ TWO DIFFERENT RULES, and they are not the same shape (Codex, 2026-09-22): anything with an
        # `_archive` ANCESTOR, plus files whose IMMEDIATE parent is literally `archive`. On this repo
        # that is 248 + 127. Quoting the total as one population hides that.
        if "_archive" in p.parts or "archive" == p.parent.name:
            out.append(p.relative_to(root).as_posix())
    return sorted(out)


def recorded(root):
    """Reasons we actually wrote down. Append-only; a later row never edits an earlier one."""
    lp = ledger_path(root)
    rows = {}
    if not lp.exists():
        return rows
    for line in lp.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue          # a malformed row is not a reason; it must not silently count as one
        # ⛔ THE READER MUST REFUSE WHAT THE WRITER REFUSES. Found 2026-09-22 by Codex, re-derived
        # here: a row carrying only {"path": ...} was counted as a recorded reason and the report
        # printed "Every departure is accounted for", exit 0. The writer rejects a blank `why`; the
        # reader never looked. A control that tests only the producer proves nothing about the pipe.
        if not isinstance(r, dict):
            continue          # valid JSON that is not an object is not a row
        if r.get("path") and str(r.get("why") or "").strip():
            rows[r["path"]] = r
    return rows


def last_departure_date(root, paths):
    """When the most recent departure happened, from git. Absent git, fall back to mtime.
    ⚠ This dates the FILE's arrival in _archive, which is the move — not the node's own age."""
    if not paths:
        return None
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%ad", "--date=short", "--"] + paths[:400],
                             cwd=root, capture_output=True, text=True, timeout=30).stdout.strip()
        if out:
            return out
    except Exception:
        pass
    try:
        newest = max((Path(root) / p).stat().st_mtime for p in paths)
        return datetime.fromtimestamp(newest, timezone.utc).date().isoformat()
    except Exception:
        return None


def survey(root=None):
    root = root or REPO
    gone = departed(root)
    known = recorded(root)
    silent = [p for p in gone if p not in known]
    return {"root": str(root), "departed": gone, "recorded": known,
            "silent": silent, "last": last_departure_date(root, gone)}


def report(root=None, oneline=False):
    s = survey(root)
    n, k, q = len(s["departed"]), len(s["recorded"]), len(s["silent"])
    when = f", most recent {s['last']}" if s["last"] else ""
    # ⛔ THIS IS AN ARCHIVE-REASON INVENTORY, NOT A DEPARTURE CENSUS. It measures a STOCK of surviving
    # archive files, never a FLOW of departure events, so a direct `rm`/`git rm` is invisible to it.
    # ⛔⛔ AND THE DEGENERATE CASE IS THE DANGEROUS ONE (Codex, 2026-09-22): erase every archived file
    # and the old wording improved to "nothing has left the store", exit 0 — the procedure certified
    # increasing destruction as increasing health. Zero scanned now reports UNKNOWN COVERAGE, not OK.
    if n == 0:
        return ("✦ ARCHIVE REASONS — 0 archive files scanned. ⚠ THIS IS NOT A CLEAN BILL: it means"
                " the scan found nothing, which an empty store and a fully-erased one produce"
                " identically.\n   Direct deletions are invisible to this check ⇒ coverage UNKNOWN."), 0
    head = (f"✦ ARCHIVE REASONS — {n} archive file(s) scanned{when}; {n-q} carry a recorded reason.\n"
            "   (a STOCK of surviving archive files, not a census of departures — direct deletions\n"
            "    are invisible here; for those see `git log --diff-filter=D`.)")
    if q == 0:
        return head + "\n   ✅ Every SCANNED archive file has a reason. Coverage beyond the archive is unmeasured.", 0
    if oneline:
        return head + f" ⚠ {q} SCANNED ARCHIVE FILE(S) HAVE NO RECORDED REASON.", 2
    sample = "\n".join(f"     · {p}" for p in s["silent"][:5])
    more = f"\n     … and {q-5} more" if q > 5 else ""
    return (head + f"\n   ⚠ {q} SCANNED ARCHIVE FILE(S) HAVE NO RECORDED REASON — the store set them\n"
            "   aside and did not say why. A retention decision is a claim about what matters; an\n"
            "   unrecorded one is a claim nobody can check, and it fails in the direction that looks healthy.\n"
            f"{sample}{more}\n"
            "   ⇒ record one: check-store-departures.py --record --path <p> --why \"...\" --by <tool>"), 2


def record(root, path, why, by):
    if not why or not why.strip():
        print("refusing: a departure with an empty reason is the thing this exists to prevent", file=sys.stderr)
        return 1
    lp = ledger_path(root)
    lp.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "path": path, "why": why.strip(), "by": by or "unknown"}
    before = lp.read_text(encoding="utf-8") if lp.exists() else ""
    with lp.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    after = lp.read_text(encoding="utf-8")
    # assert the CONTENT landed, never the act -- an append that wrote nothing still exits 0
    if json.dumps(row, ensure_ascii=False) not in after or len(after) <= len(before):
        print("ledger append did not land", file=sys.stderr)
        return 1
    print(f"recorded: {path}")
    return 0


def selftest():
    import shutil, tempfile
    ok = True

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")

    tmp = Path(tempfile.mkdtemp(prefix="departures-"))
    try:
        arch = tmp / "memory" / "wiki" / "_archive"
        arch.mkdir(parents=True)
        (arch / "gone.md").write_text("# gone\n", encoding="utf-8")
        # CONTROL 1 — a departure with no reason must be found and must EXIT 2.
        txt, code = report(tmp)
        check("an unrecorded departure is found", "1 archive file(s) scanned" in txt)
        check("and it exits 2 (the finding)", code == 2)
        check("it says the reason is missing", "NO RECORDED REASON" in txt)
        # CONTROL 2 — recording the reason must clear it, and must exit 0.
        record(tmp, "memory/wiki/_archive/gone.md", "superseded by the merged node", "selftest")
        txt2, code2 = report(tmp)
        check("recording a reason clears the finding", code2 == 0)
        check("and it says so (SCOPED, never universal)",
              "Every SCANNED archive file has a reason" in txt2 and "unmeasured" in txt2)
        # CONTROL 3 — an EMPTY reason must be refused, or the ledger becomes decoration.
        rc = record(tmp, "memory/wiki/_archive/gone.md", "   ", "selftest")
        check("an empty reason is refused", rc == 1)
        # CONTROL 3b — THE READER MUST REFUSE WHAT THE WRITER REFUSES (Codex, 2026-09-22).
        # The original suite tested the WRITER only and called the pipeline proven; a hand-written
        # {"path": ...} row with no `why` was counted as a reason and printed "accounted for", exit 0.
        import json as _j
        for bad in ({"path": "memory/wiki/_archive/gone.md"},
                    {"path": "memory/wiki/_archive/gone.md", "why": "   "},
                    "a bare json string"):
            (tmp / LEDGER_REL).write_text(_j.dumps(bad) + "\n", encoding="utf-8")
            _, c = report(tmp)
            check(f"reader refuses {str(bad)[:34]!s:36s}", c == 2)
        # CONTROL 3c — THE DEGENERATE CASE: an erased store must NOT read as healthy.
        import tempfile as _tf, shutil as _sh
        gone = Path(_tf.mkdtemp(prefix="departures-erased-"))
        (gone / "memory").mkdir()
        gt, gc = report(gone)
        check("an erased/empty store says NOT A CLEAN BILL", "NOT A CLEAN BILL" in gt)
        check("...and never claims nothing departed", "nothing has left" not in gt)
        _sh.rmtree(gone, ignore_errors=True)
        # restore a good row for the controls below
        record(tmp, "memory/wiki/_archive/gone.md", "superseded by the merged node", "selftest")

        # CONTROL 4 — a malformed row must not count as a reason.
        (tmp / LEDGER_REL).write_text("{not json}\n", encoding="utf-8")
        _, code4 = report(tmp)
        check("a malformed ledger row does not pass as a reason", code4 == 2)
        # CONTROL 5 — an empty store must not report a phantom departure.
        empty = Path(tempfile.mkdtemp(prefix="departures-empty-"))
        (empty / "memory").mkdir()
        t5, c5 = report(empty)
        # ⛔ THIS CONTROL USED TO ASSERT THE DANGEROUS BEHAVIOUR: it required the words "nothing has
        # left the store" on an empty scan, i.e. it enforced the very certification Codex flagged --
        # erase everything and the report improves. Inverted 2026-09-22: emptiness must read UNKNOWN.
        check("an empty store does NOT certify health", c5 == 0 and "NOT A CLEAN BILL" in t5)
        check("...and never says nothing departed", "nothing has left" not in t5)
        shutil.rmtree(empty, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("SELFTEST PASS" if ok else "SELFTEST FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--boot", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--path"); ap.add_argument("--why"); ap.add_argument("--by")
    ap.add_argument("--root", default=None)
    a = ap.parse_args()
    root = Path(a.root) if a.root else REPO
    if a.selftest:
        return selftest()
    if a.record:
        return record(root, a.path, a.why, a.by)
    txt, code = report(root, oneline=a.boot)
    print(txt)
    return code


if __name__ == "__main__":
    sys.exit(main())
