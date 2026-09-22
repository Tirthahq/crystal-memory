#!/usr/bin/env python3
"""crystal-discriminators.py — RUN the discriminators. The half that observes the world.

⛔ WHY THIS EXISTS. `stale_after` schedules when we stop asserting a claim; it never checks whether the
claim is still true. Grok put it exactly right in the 2026-09-22 review, and it was re-derived rather
than taken on trust:

    "Enforcement is `today > stale_after`. A crystal can be byte-identical, unexpired, and false at
     dawn after the fix. That is exactly the case SELF-staleness cannot see and exactly the case this
     design still cannot see. You substituted a weaker non-semantic oracle (a human guess) while
     leaving the stronger non-semantic oracle (the shell command) as text in a stub."

A date is a PREDICTION of an unscheduled event. Anyone who can name the day the box gets fixed did not
need the crystal. This runner turns the recorded command into the oracle it always was.

⭐ THE POLICY, AND IT IS DELIBERATELY ASYMMETRIC — read this before changing it:
  · **FAIL (non-zero exit) ⇒ the crystal is EXPIRED IMMEDIATELY, whatever its date says.** This is the
    safety direction: a claim whose own discriminator refuses it must stop being asserted at once, not
    at the end of a calendar window somebody guessed.
  · **PASS (exit 0) ⇒ recorded as evidence, and NOTHING is extended.** A passing check does NOT push
    `stale_after` forward on its own. Auto-extending would let the store re-assert a claim no human
    ever looked at again — which is the entire exposure this mechanism exists to close, re-created one
    level up. The report NAMES the crystals whose discriminator passes so a session can bump the date
    deliberately. ⚠ Grok argued for auto-bump-on-success; that half is NOT adopted and the reason is
    here rather than in a commit message nobody re-reads. It is a real policy call and it is the maintainer's.

⛔ NEVER ON THE HOT PATH. This executes shell recorded in a node's frontmatter. It is offline, explicit,
timeout-bounded, and no hook invokes it. `is_expired` only ever READS the result file this writes.

  python3 scripts/crystal-discriminators.py --list       # what would run, and nothing else
  python3 scripts/crystal-discriminators.py --run        # execute them, record results
  python3 scripts/crystal-discriminators.py --oneline    # the boot/status line
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
# Same durable, gitignored, NON-rotating home as gate-events.jsonl. Deliberately not `scratch/`:
# scratch wipes at 14 days and the whole value of this file is that it is older than that.
RESULTS = os.path.join(REPO, "memory", "research", "paper-data", "discriminator-runs.jsonl")
TIMEOUT_S = 60


def _registry():
    spec = importlib.util.spec_from_file_location(
        "crystal_registry", os.path.join(REPO, "scripts", "crystal_registry.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def with_discriminators(repo=REPO):
    cr = _registry()
    return [c for c in cr.load_crystals(repo) if (c.get("discriminator") or "").strip()]


def run_one(c, timeout=TIMEOUT_S):
    """Execute one discriminator. Returns the row that will be recorded.

    A crash, a timeout or a missing binary is NOT 'the claim still holds' — it is INCONCLUSIVE, and it
    is recorded as such. Folding it into either PASS or FAIL would be the classic transport-error-as-
    verdict mistake: a 429 is not 'the model cannot do parallel calls'.
    """
    cmd = (c.get("discriminator") or "").strip()
    base = os.path.basename(str(c.get("path") or ""))
    started = time.time()
    row = {"ts": datetime.now(timezone.utc).isoformat(), "crystal": base, "cmd": cmd}
    try:
        p = subprocess.run(cmd, shell=True, cwd=REPO, capture_output=True, text=True, timeout=timeout)
        # ⛔⛔ THREE STATES, NOT TWO. Until 2026-09-22 this read `pass if 0 else fail`, so a probe that
        # RAN and could not SEE was recorded as FALSIFIED: a DNS blip, an expired credential or a box
        # being down withheld the crystal as though the world had disproven it. `inconclusive` existed
        # but only covered a timeout or a missing binary — failures to LAUNCH, not failures to OBSERVE.
        # Found by an adversarial review and confirmed by running it. All three live discriminators had
        # the defect, and the worst one INVERTED: `test "$(aws ...)" != Online` exits 0 when the CLI
        # prints nothing, so a broken CLI certified "the box does not come up" while seeing nothing at
        # all — the cloud-CLI case this repo keeps as a negative control, live in our own store.
        # 🔑 THE CONTRACT A DISCRIMINATOR MUST NOW SATISFY:
        #     exit 0   the claim HOLDS
        #     exit 1   the claim is FALSIFIED  (the world answered, and the answer is no)
        #     exit 2+  CANNOT SEE              (no answer, empty answer, tool failure) -> inconclusive
        # An inconclusive run neither clears nor creates a refusal; `latest()` already refuses to let
        # it overwrite a fail. Withholding on "cannot see" would teach people to delete discriminators.
        verdict = "pass" if p.returncode == 0 else ("fail" if p.returncode == 1 else "inconclusive")
        row.update(verdict=verdict, exit=p.returncode,
                   ms=int((time.time() - started) * 1000),
                   tail=(p.stdout or p.stderr or "")[-200:].strip())
    except subprocess.TimeoutExpired:
        row.update(verdict="inconclusive", exit=None, ms=int(timeout * 1000),
                   tail=f"timed out after {timeout}s")
    except Exception as e:                                   # noqa: BLE001 - any launch failure
        row.update(verdict="inconclusive", exit=None, ms=int((time.time() - started) * 1000),
                   tail=f"could not run: {e}")
    return row


def record(rows, path=RESULTS):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, separators=(",", ":")) + "\n")
    except OSError:
        pass
    return len(rows)


def latest(path=RESULTS):
    """The most recent verdict per crystal. INCONCLUSIVE never overwrites a real verdict.

    ⚠ An inconclusive run must not clear a FAIL — 'I could not check' is not 'it is fine again', and
    treating it as such would make a broken checker look like a healed claim.
    """
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
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
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
        print(f"{len(cs)} crystal(s) carry a discriminator:")
        for c in cs:
            print(f"  {os.path.basename(str(c.get('path')))}\n      $ {(c.get('discriminator') or '').strip()}")
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
              "Re-mint or retire it; nothing is auto-retired.")
    return 0


def selftest():
    import tempfile
    ok = True

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")

    check("a passing command is a pass", run_one({"discriminator": "true", "path": "/x/a.md"})["verdict"] == "pass")
    check("a failing command is a fail", run_one({"discriminator": "false", "path": "/x/b.md"})["verdict"] == "fail")
    r = run_one({"discriminator": "sleep 5", "path": "/x/c.md"}, timeout=1)
    check("a timeout is INCONCLUSIVE, never a pass or a fail", r["verdict"] == "inconclusive")
    r = run_one({"discriminator": "this-binary-does-not-exist-zz", "path": "/x/d.md"})
    check("a missing binary is a fail or inconclusive, never a pass", r["verdict"] != "pass")
    # the three-state contract, each arm watched
    check("exit 2 is CANNOT SEE, never falsified",
          run_one({"discriminator": "exit 2", "path": "/x/c.md"})["verdict"] == "inconclusive")
    check("exit 3 is also CANNOT SEE", 
          run_one({"discriminator": "exit 3", "path": "/x/d.md"})["verdict"] == "inconclusive")
    check("only exit 1 falsifies",
          run_one({"discriminator": "exit 1", "path": "/x/e.md"})["verdict"] == "fail")
    # ⭐ THE SHAPE EVERY DISCRIMINATOR MUST NOW HAVE, asserted as a control rather than described:
    # capture, refuse an empty answer, THEN compare. The old shape compared first, so an empty answer
    # was indistinguishable from a wrong one - and for a `!=` test it read as the claim HOLDING.
    good = 'out=$(printf ""); [ -n "$out" ] || exit 2; test "$out" != Online'
    check("the guarded shape reports CANNOT SEE on an empty answer",
          run_one({"discriminator": good, "path": "/x/f.md"})["verdict"] == "inconclusive")
    bad = 'test "$(printf "")" != Online'
    check("and the UNGUARDED shape would have called that a PASS (the defect, kept visible)",
          run_one({"discriminator": bad, "path": "/x/g.md"})["verdict"] == "pass")

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
