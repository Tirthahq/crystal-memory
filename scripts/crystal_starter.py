#!/usr/bin/env python3
"""
crystal_starter.py — gate 5 of the crystals standalone package: the STARTER SET.

WHY THIS EXISTS. A new store is empty, delivery is SPEAK-only, and there is no RAG in v1. So a tester's
honest first-hour report is "I installed it and nothing happened" — indistinguishable from a broken
install. A handful of universal crystals in their store on day one makes the loop visible before they
have written anything of their own.

⛔ THIS DOES NOT BREAK THE MINTING RULE. The rule is *never mint from IMPORTED text* — text we did not
observe the outcome of. It is not "ship empty". Every crystal in starter/ was
observed here, on our own work, and rewritten to stand alone: no links into our node store, no internal
node names, no dependency on our repo. They ship as OURS BY OBSERVATION, with provenance in the body.

WHERE THEY LIVE, AND WHY NOT UNDER memory/. The starter files sit in `starter/`,
OUTSIDE `memory/`, so our own registry never loads them. Under memory/ they would register here as
near-duplicates of the live crystals they were derived from — two versions of one knowing to keep in
sync, which is the exact drift the store fights.

USAGE
  python3 scripts/crystal_starter.py list                  # what is in the set
  python3 scripts/crystal_starter.py seed --into <root>    # copy into <root>/memory/crystals/
  python3 scripts/crystal_starter.py selftest              # prove it on a clean foreign repo

SEEDING IS NON-DESTRUCTIVE: an existing file of the same name is never overwritten, so re-seeding a
store someone has edited cannot silently revert their edits. It reports what it skipped.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _find_starter_dir():
    """Locate starter/ in BOTH layouts this package lives in.

    Inside the development repo the package sits at <repo>/crystals-standalone/, so the starter
    set is <repo>/crystals-standalone/starter/ while the scripts are at <repo>/scripts/.
    Once EXTRACTED to its own repo the scripts are <root>/scripts/ and the starter set is
    <root>/starter/.

    MEASURED 2026-09-17: the path was hardcoded to the first layout, so the selftest passed in
    the development repo and failed on the first run after extraction, seeding nothing and
    reporting five failures. The package's own portability test was not portable.
    """
    for cand in (ROOT / "starter", ROOT / "crystals-standalone" / "starter"):
        if cand.is_dir():
            return cand
    return ROOT / "starter"


STARTER_DIR = _find_starter_dir()
CORE_SCRIPTS = ("crystal_registry.py", "crystal_act.py", "crystal_inject.py",
                "crystallize-stop-hook.py", "crystal_starter.py")
# Where a seeded crystal lands in the target store. Any path under memory/ works — the registry walks
# memory/ recursively and binds on the frontmatter block, not on the location.
SEED_SUBDIR = Path("memory") / "crystals"


def starter_files():
    """The set, sorted by name so `list` and `seed` report in a stable order."""
    if not STARTER_DIR.is_dir():
        return []
    return sorted(p for p in STARTER_DIR.glob("crystal-*.md") if p.is_file())


def seed(into, quiet=False):
    """Copy the starter set into <into>/memory/crystals/. Returns (written, skipped) name lists."""
    dest_dir = Path(into) / SEED_SUBDIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    written, skipped = [], []
    for src in starter_files():
        dest = dest_dir / src.name
        if dest.exists():
            skipped.append(src.name)
            continue
        shutil.copy2(src, dest)
        written.append(src.name)
    if not quiet:
        for n in written:
            print(f"  seeded  {SEED_SUBDIR / n}")
        for n in skipped:
            print(f"  kept    {SEED_SUBDIR / n}  (already present — not overwritten)")
        print(f"{len(written)} seeded, {len(skipped)} left alone, into {Path(into) / SEED_SUBDIR}")
    return written, skipped


# ---- selftest ---------------------------------------------------------------------------------
# The gate the task asks for: prove the starter set on a CLEAN FOREIGN REPO, and assert the artifact
# rather than an exit code. A bare exit 0 is not a pass.

def _run(argv, cwd=None, env=None):
    return subprocess.run(argv, cwd=cwd, env=env, text=True, capture_output=True, check=False)


def _foreign_root(tmp):
    """A minimal foreign install: the layout contract and nothing else of ours."""
    foreign = Path(tmp) / "foreign"
    (foreign / "scripts").mkdir(parents=True)
    (foreign / "memory").mkdir()
    (foreign / "scratch").mkdir()
    for name in CORE_SCRIPTS:
        shutil.copy2(ROOT / "scripts" / name, foreign / "scripts" / name)
    return foreign


def _fire(foreign, ctx, dry=False, session="starter-selftest"):
    """Run the real delivery path in the foreign root and return its stdout."""
    env = dict(os.environ)
    env["CLAUDE_SESSION_ID"] = session
    # ⛔ A "CLEAN FOREIGN REPO" THAT INHERITS THE AMBIENT ENVIRONMENT IS NOT CLEAN, AND THE TEST
    # CANNOT SEE THE DIFFERENCE. MEASURED 2026-09-17: this selftest failed on exactly one of its
    # fifteen checks, deterministically, on the machine where the package is developed. The cause
    # was CRYSTAL_HOLDBACK_PCT=10 exported in that shell for a live holdback experiment, copied
    # into the child here, suppressing one delivery by design. The package was fine; the harness
    # was reporting its own environment. Scrub every knob that can change what gets delivered, so
    # a pass means the package works rather than that the developer's shell was quiet today.
    for k in [k for k in env if k.startswith("CRYSTAL_")]:
        if k != "CRYSTAL_ACT":
            del env[k]
    argv = [sys.executable, str(foreign / "scripts" / "crystal_act.py"),
            "--act", "bash", "--ctx", ctx]
    if dry:
        argv.append("--dry")
    return _run(argv, cwd=str(foreign), env=env).stdout


def selftest():
    ok = True

    def check(cond, label):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
        ok = ok and bool(cond)

    tmp = tempfile.mkdtemp(prefix="crystal-starter-")
    try:
        foreign = _foreign_root(tmp)
        doctor = [sys.executable, str(foreign / "scripts" / "crystal_registry.py"), "doctor"]

        # 1. The empty store must be UNHEALTHY. If doctor were green here, every check below would be
        #    passed by a store with nothing in it.
        pre = _run(doctor, cwd=str(foreign))
        check(pre.returncode == 2, "empty foreign store: doctor exits 2 (nothing to deliver)")

        # 2. THE NEGATIVE CONTROL RUNS BEFORE ANY POSITIVE ARM, ON PURPOSE. Run it afterwards and a
        #    silent result could be the act ledger's backoff rather than the match rule, and the
        #    control would prove nothing.
        pre_fire = _fire(foreign, "ls -la /tmp")
        check(pre_fire.strip() == "", "unseeded store is silent for an unrelated command")

        written, skipped = seed(foreign, quiet=True)
        check(len(written) == 3 and not skipped, f"seeded 3 starter crystals (got {len(written)})")

        # 3. Registered AND deliverable. A crystal with a valid binding and no essence markers
        #    registers fine and can never deliver, so registration alone is not the assertion.
        post = _run(doctor, cwd=str(foreign))
        check(post.returncode == 0, "seeded foreign store: doctor exits 0")
        check("MISSING" not in post.stdout, "no seeded crystal is missing its essence markers")
        for name in ("crystal-exit-code-through-a-pipe",
                     "crystal-green-tests-do-not-prove-head-builds",
                     "crystal-a-positive-control-cannot-detect-a-yes-machine"):
            check(name in post.stdout, f"registered: {name}")

        # 4. A NEGATIVE CONTROL AGAIN, now that the store is full: an unrelated command must still
        #    deliver nothing. This is what stops "it fires on everything" reading as success.
        quiet = _fire(foreign, "ls -la /tmp")
        check(quiet.strip() == "", "seeded store stays silent for an unrelated command")

        # 5. EACH ONE ACTUALLY FIRES, on the real delivery path, and the ESSENCE TEXT arrives — not a
        #    name, not an exit code. Distinct commands so each arm exercises one crystal's match list.
        fires = {
            "npm run build 2>&1 | tail -20": "REPORTS TAIL'S EXIT CODE",
            "git commit -m fix": "COMPILES THE WORKING TREE",
            "python3 harness.py --selftest": "CANNOT DETECT A YES-MACHINE",
        }
        for cmd, marker in fires.items():
            out = _fire(foreign, cmd)
            check(marker in out, f"fires on `{cmd}`")

        # 6. RE-SEEDING IS SAFE. The failure this guards is a tester editing a starter crystal and a
        #    later seed silently reverting it, so assert the CONTENT, not the skip count.
        edited = foreign / SEED_SUBDIR / "crystal-exit-code-through-a-pipe.md"
        edited.write_text(edited.read_text(encoding="utf-8") + "\nTESTER EDIT\n", encoding="utf-8")
        w2, s2 = seed(foreign, quiet=True)
        check(not w2 and len(s2) == 3, "re-seed writes nothing when the set is already present")
        check("TESTER EDIT" in edited.read_text(encoding="utf-8"),
              "re-seed does not overwrite a file the tester edited")

        # 7. CAN THIS SELFTEST SAY NO? Sabotage one crystal's essence markers and require the health
        #    check to go red. Without this arm every check above is passed by an instrument that
        #    always agrees.
        sab_tmp = tempfile.mkdtemp(prefix="crystal-starter-sabotage-")
        try:
            sab = _foreign_root(sab_tmp)
            seed(sab, quiet=True)
            victim = sab / SEED_SUBDIR / "crystal-green-tests-do-not-prove-head-builds.md"
            victim.write_text(
                victim.read_text(encoding="utf-8").replace("<!-- crystal:" + "essence -->", "", 1),
                encoding="utf-8")
            sab_doc = _run([sys.executable, str(sab / "scripts" / "crystal_registry.py"), "doctor"],
                           cwd=str(sab))
            check(sab_doc.returncode == 2,
                  "sabotage control: a starter crystal stripped of its essence marker turns doctor red")
        finally:
            shutil.rmtree(sab_tmp, ignore_errors=True)

        print("SELFTEST: starter set on a clean foreign repo " + ("PASS" if ok else "FAIL"))
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    s = sub.add_parser("seed")
    s.add_argument("--into", required=True, help="root of the store to seed (its memory/ is written)")
    sub.add_parser("selftest")
    args = ap.parse_args()

    if args.cmd == "list":
        files = starter_files()
        for p in files:
            print(f"  {p.relative_to(ROOT)}")
        print(f"{len(files)} starter crystal(s) in {STARTER_DIR.relative_to(ROOT)}")
        return 0
    if args.cmd == "seed":
        seed(args.into)
        return 0
    return selftest()


if __name__ == "__main__":
    sys.exit(main())
