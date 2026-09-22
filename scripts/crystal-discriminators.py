#!/usr/bin/env python3
"""crystal-discriminators.py — RUN the checks. The half that observes the world.

A `stale_after:` date only schedules when you stop asserting a claim. It never checks whether the claim
is still TRUE, so a note can be byte-identical, unexpired, and false — which is exactly the case the
mechanism exists for. A date is a prediction of an unscheduled event; anyone who can name the day the
thing gets fixed did not need the note in the first place.

So a note may also carry the one command that settles it:

    crystal:
      stale_after: 2026-12-01
      discriminator: test "$(some command)" != "the answer that would falsify this"

⛔ THE CONTRACT: **exit 0 while the claim HOLDS, non-zero when it is FALSIFIED.**
   This is not automatic. The first discriminator we wrote failed it: a cloud CLI call printed one
   answer while our box was down and a different answer when it came back, and **exited 0 both times**.
   A runner keyed on the exit code would have read "the claim still holds" forever, including on the
   day it stopped being true. Wrap the answer in a `test` so it can actually refuse.

⭐ THE POLICY IS DELIBERATELY ASYMMETRIC — read this before changing it:
  · **FAIL (non-zero) ⇒ the note is EXPIRED IMMEDIATELY, whatever its date says.** The safety
    direction: a claim its own check refuses must stop being asserted at once, not at the end of a
    window somebody guessed.
  · **PASS (exit 0) ⇒ recorded as evidence, and NOTHING is extended.** A passing check does not push
    `stale_after` forward on its own. Auto-extending would let the store re-assert a claim no human
    ever looked at again — which is this whole mechanism's exposure, rebuilt one level up. The report
    NAMES the passing notes so a person can move the date deliberately.
  · **A timeout or a missing binary is INCONCLUSIVE**, never a pass and never a fail, and an
    inconclusive run can never clear an earlier refusal. "I could not check" is not "it is fine again".

⛔ NEVER ON THE DELIVERY PATH. This executes shell recorded in a note's frontmatter. It is offline,
   explicit, timeout-bounded and logged; the hook only ever READS the file this writes. Run it from a
   scheduled job, or by hand, on a cadence that suits how fast your claims rot.

  python3 scripts/crystal-discriminators.py --list       # what would run; executes nothing
  python3 scripts/crystal-discriminators.py --run        # execute them, record verdicts
  python3 scripts/crystal-discriminators.py --oneline    # a status line
  python3 scripts/crystal-discriminators.py --selftest
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIMEOUT_S = 60


def _registry():
    spec = importlib.util.spec_from_file_location(
        "crystal_registry", os.path.join(REPO, "scripts", "crystal_registry.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def results_path():
    return os.path.join(REPO, _registry().DISC_RESULTS)


def with_discriminators(repo=REPO):
    cr = _registry()
    return [c for c in cr.load_crystals(repo) if (c.get("discriminator") or "").strip()]


def run_one(c, timeout=TIMEOUT_S):
    """Execute one discriminator and return the row that will be recorded."""
    cmd = (c.get("discriminator") or "").strip()
    base = os.path.basename(str(c.get("path") or ""))
    started = time.time()
    row = {"ts": datetime.now(timezone.utc).isoformat(), "crystal": base, "cmd": cmd}
    try:
        p = subprocess.run(cmd, shell=True, cwd=REPO, capture_output=True, text=True, timeout=timeout)
        row.update(verdict="pass" if p.returncode == 0 else "fail", exit=p.returncode,
                   ms=int((time.time() - started) * 1000),
                   tail=(p.stdout or p.stderr or "")[-200:].strip())
    except subprocess.TimeoutExpired:
        row.update(verdict="inconclusive", exit=None, ms=int(timeout * 1000),
                   tail=f"timed out after {timeout}s")
    except Exception as e:                                   # noqa: BLE001 — any launch failure
        row.update(verdict="inconclusive", exit=None, ms=int((time.time() - started) * 1000),
                   tail=f"could not run: {e}")
    return row


def record(rows, path=None):
    path = path or results_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, separators=(",", ":")) + "\n")
    except OSError:
        pass
    return len(rows)


def latest(path=None):
    """The most recent verdict per note. INCONCLUSIVE never overwrites a real verdict."""
    path = path or results_path()
    out = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if not isinstance(r, dict) or not r.get("crystal"):
                    continue
                if r.get("verdict") == "inconclusive" and r["crystal"] in out:
                    continue
                out[r["crystal"]] = r
    except OSError:
        pass
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true", help="execute the discriminators and record results")
    ap.add_argument("--list", action="store_true", help="show what WOULD run; execute nothing")
    ap.add_argument("--oneline", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--timeout", type=int, default=TIMEOUT_S)
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    cs = with_discriminators()

    if a.list or not (a.run or a.oneline):
        print(f"{len(cs)} note(s) carry a discriminator:")
        for c in cs:
            print(f"  {os.path.basename(str(c.get('path')))}\n      $ {(c.get('discriminator') or '').strip()}")
        if not cs:
            print("  (none yet — add `discriminator:` to any note that asserts live state)")
        return 0

    if a.oneline:
        seen = latest()
        failed = [k for k, v in seen.items() if v.get("verdict") == "fail"]
        passed = [k for k, v in seen.items() if v.get("verdict") == "pass"]
        unchecked = [os.path.basename(str(c.get("path"))) for c in cs
                     if os.path.basename(str(c.get("path"))) not in seen]
        if failed:
            print(f"<<< crystal-discriminators: {len(failed)} claim(s) REFUSED by their own check "
                  f"(expired now, regardless of date): {', '.join(sorted(failed)[:3])}")
        elif unchecked:
            print(f"crystal-discriminators: {len(cs)} with a check · {len(passed)} passing · "
                  f"{len(unchecked)} NEVER RUN — a check that has never run is not a check")
        else:
            print(f"crystal-discriminators: {len(cs)} with a check · all passing ✓")
        return 0

    rows = [run_one(c, a.timeout) for c in cs]
    record(rows)
    for r in rows:
        mark = {"pass": "✓", "fail": "<<< FAIL", "inconclusive": "? inconclusive"}[r["verdict"]]
        print(f"  {mark} {r['crystal']} (exit={r['exit']}, {r['ms']}ms) {r['tail'][:90]}")
    fails = sum(1 for r in rows if r["verdict"] == "fail")
    print(f"\n{len(rows)} run · {fails} refused by their own check · "
          f"{sum(1 for r in rows if r['verdict'] == 'inconclusive')} inconclusive")
    if fails:
        print("⛔ A refused claim is EXPIRED from now on, whatever its stale_after says. "
              "Rewrite or delete it; nothing is retired automatically.")
    return 0


def selftest():
    import tempfile
    ok = True

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")

    check("a passing command is a pass",
          run_one({"discriminator": "true", "path": "/x/a.md"})["verdict"] == "pass")
    check("a failing command is a fail",
          run_one({"discriminator": "false", "path": "/x/b.md"})["verdict"] == "fail")
    check("a timeout is INCONCLUSIVE, never a pass or a fail",
          run_one({"discriminator": "sleep 5", "path": "/x/c.md"}, timeout=1)["verdict"] == "inconclusive")
    check("a missing binary is never a pass",
          run_one({"discriminator": "this-binary-does-not-exist-zz", "path": "/x/d.md"})["verdict"] != "pass")
    # The contract, in both directions — this is the shape to copy when writing one.
    check("the shipped shape can say YES",
          run_one({"discriminator": 'test "$(echo down)" != up', "path": "/x/e.md"})["verdict"] == "pass")
    check("the shipped shape can say NO",
          run_one({"discriminator": 'test "$(echo up)" != up', "path": "/x/e.md"})["verdict"] == "fail")
    check("a bare read with no comparison can NEVER refuse (the defect to avoid)",
          run_one({"discriminator": "echo up", "path": "/x/f.md"})["verdict"] == "pass")

    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
        p = fh.name
    record([{"ts": "1", "crystal": "x.md", "verdict": "fail", "exit": 1},
            {"ts": "2", "crystal": "x.md", "verdict": "inconclusive", "exit": None}], p)
    check("an inconclusive run does NOT clear an earlier fail", latest(p)["x.md"]["verdict"] == "fail")
    record([{"ts": "3", "crystal": "x.md", "verdict": "pass", "exit": 0}], p)
    check("a later real verdict does replace it", latest(p)["x.md"]["verdict"] == "pass")
    os.unlink(p)

    print("SELFTEST PASS" if ok else "SELFTEST FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
