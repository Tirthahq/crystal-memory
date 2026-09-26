#!/usr/bin/env python3
"""Published install layout and fail-closed maintenance bindings. No I/O at import.

INSTALL.md owns directory declarations; maintenance filenames below are consumers
of those directories, not additional claims about what v1 installs.

CLAUDE_PROJECT_DIR selects the repository; CRYSTALS_INSTALL_CONTRACT may select
an install page with narrower declared store directories. No directory discovery
can grant mutation authority. Optional MEMORY_INDEX_FILE and MEMORY_BOOT_FILES
(os.pathsep separated) identify the installer's protected entry points.
CORRECTOR_OWN_FILES is an explicit local-author file allowlist for bounded edits;
imported provenance still prevents editing. Gardener uses --transcripts-dir or
TRANSCRIPT_DIR for the user's own usage ledger, otherwise the published scratch/.

"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path


class ContractError(Exception):
    """A maintenance input or dependency cannot be satisfied."""

# ⛔ A RUNTIME LIBRARY MUST NOT IMPORT A CI GATE. This used to dynamically load
# check-portable-store-contract.py to borrow its INSTALL parser, which made a dev tool a shipping
# requirement and hid the dependency from every static check (measured 2026-09-22: four agents dead on
# a clean install, `No such file`). Both now import the one owner.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from install_layout import parse_layout   # noqa: E402


class StoreContract:
    def __init__(self, root=None, layout=None):
        # Registry's script-relative repository convention, with the requested hook override.
        self.root = Path(root or os.environ.get("CLAUDE_PROJECT_DIR")
                         or Path(__file__).resolve().parents[1]).resolve()
        # ⛔ THE AUTHORITY LIVES IN TWO PLACES AND ONLY ONE WAS RESOLVED. Inside this repo the
        # standalone source sits at `crystals-standalone/INSTALL.md`; in the SHIPPED package that same
        # file is the repo root's own `INSTALL.md`. Hardcoding the first meant every agent raised
        # "No such file" the first time they were copied into the package they were made portable FOR —
        # measured 2026-09-22, on the first real port. The portability gate could not see it, because
        # the gate also runs from this repo where the first path exists.
        # 🔑 A path that is correct in the source tree and absent in the destination is exactly the
        # defect "portable" is supposed to mean, and only running it THERE shows it.
        here = Path(__file__).resolve().parents[1]
        self.layout = Path(layout or os.environ.get("CRYSTALS_INSTALL_CONTRACT")
                           or next((p for p in (here / "crystals-standalone/INSTALL.md",
                                                here / "INSTALL.md") if p.exists()),
                                   here / "crystals-standalone/INSTALL.md"))
        try:
            self.directories, self.files = parse_layout(self.layout)
            self.lines = self.layout.read_text(encoding="utf-8").splitlines()
        except (OSError, ValueError) as error:
            raise ContractError(str(error)) from error
        self.memory_dir = self.directory("memory")
        self.scratch_dir = self.directory("scratch")
        self.scripts_dir = self.directory("scripts")
        declared = sorted(d for d in self.directories if d.startswith("memory/"))
        self.store_dirs = tuple(self.root / d for d in declared) or (self.memory_dir,)

    def expected(self, path):
        try:
            rel = Path(path).relative_to(self.root).as_posix()
        except ValueError:
            rel = ""
        parent = max((d for d in self.directories if rel == d or rel.startswith(d + "/")),
                     key=len, default="")
        token = parent.rsplit("/", 1)[-1] + "/"
        line = next((i for i, s in enumerate(self.lines, 1)
                     if s.strip().startswith(token)), 1)
        return f"{self.layout}:{line}: {self.lines[line - 1].strip()}"

    def directory(self, name):
        if name not in self.directories:
            raise ContractError(f"cannot answer: {self.layout} does not declare {name}/")
        return self.root / name

    def require(self, *parts):
        path = self.root.joinpath(*parts)
        if not path.exists():
            raise ContractError(f"cannot answer: missing {path}; expected by {self.expected(path)}")
        return path

    def require_dir(self, path):
        self.require(path)
        if Path(path).resolve() != Path(path).absolute():
            raise ContractError(f"cannot answer: symlink directory is not authorized: {path}")
        if not Path(path).is_dir():
            raise ContractError(f"cannot answer: not a directory: {path}; expected by {self.expected(path)}")
        return Path(path)

    def population(self):
        """Exact declared directories, never a recursive mutator walk."""
        for directory in self.store_dirs:
            self.require_dir(directory)
            if directory.resolve() != directory:
                raise ContractError(f"cannot answer: symlink store is not authorized: {directory}")
        return self.store_dirs

    def node_files(self, recursive=False):
        """Declared-store .md files.

        ⛔ THE DEFAULT IS NON-RECURSIVE ON PURPOSE, AND THE TWO CALLERS ARE NOT THE SAME.
        A MUTATOR (node-cleaner MOVES files into archive/) must act on an exact allowlist, never a
        walk, or a recursive sweep of a stranger's memory/ relocates their starter set.
        A READER (node-health, and the wayfinding commit gate above it) must see the WHOLE tree, or it
        reports on a population nobody chose.

        ⛔ MEASURED 2026-09-18, and it is why this parameter exists: binding node-health to the
        non-recursive population cut its universe from 2,375 nodes to 16, so the commit gate called
        every [[link]] in a new node dangling while standalone node-health resolved all 2,755 names.
        The gate was honest and its population was wrong. That is the SAME defect the FOLDER_CAP story
        was about (node-cleaner's non-recursive os.listdir reporting "all folders within cap" over a
        set that excluded every over-cap folder) reproduced one layer up, inside the module written to
        fix it. The static contract checker cannot see it: `d.glob("*.md")` carries no hardcoded path,
        so it is clean by the rule and wrong by the population.
        ⇒ INSTALL.md declares crystals live under memory/ "at any depth", so recursion is what the
        published contract says a READER should see.
        """
        pattern = "**/*.md" if recursive else "*.md"
        return sorted(p for d in self.population() for p in d.glob(pattern)
                      if p.is_file() and not p.is_symlink())

    def require_nodes(self):
        files = self.node_files()
        if not files:
            raise ContractError(f"cannot answer: no nodes in declared store {self.memory_dir}; "
                                f"{self.layout}: seed the starter set before checking again")
        return files

    def output(self, directory, filename):
        parent = self.require_dir(directory)
        path = parent / filename
        if path.is_symlink():
            raise ContractError(f"cannot answer: output is a symlink: {path}")
        return path

    def script(self, name, command, required=True):
        path = self.scripts_dir / name
        if not path.is_file():
            notice = f"{command}: missing {'REQUIRED' if required else 'OPTIONAL'} script {path}; {self.expected(path)}"
            if required:
                raise ContractError(notice)
            print(f"skip: {notice}", file=sys.stderr)
            return None
        return path

    def load_script(self, name, command):
        path = self.script(name, command)
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except (ImportError, OSError) as error:
            raise ContractError(f"{command}: cannot load {path}: {error}") from error
        return module

    def caps(self, command):
        module = self.load_script("store_caps.py", command)
        # Reuse its thresholds, raises and retention policy; replace only the
        # recursive discovery input, which cannot authorize a mutator.
        module.node_folders = lambda mem=None: [
            (d, d.relative_to(self.root).as_posix(), len(list(d.glob("*.md"))))
            for d in self.population()]
        return module

    def health(self, command):
        module = self.load_script("node-health.py", command)
        module.REPO = str(self.root)
        # Derive from node-health's own relative path, never a second literal — see the note
        # on TOMBSTONE_REL there for what two literals cost (2026-09-25).
        module.TOMBSTONE_FILE = str(self.root / module.TOMBSTONE_REL)
        # Scanning rules stay in node-health; only its input population is bound here.
        # ⚠ ROOT_DOCS are part of the population node-health checks, and the commit gate was blind
        # to all five — including CLAUDE.md, the constitution, where a broken sign costs the most.
        # A store that does not have them simply contributes none (the safe direction for a reporter).
        module.node_files = lambda: [str(p) for p in self.node_files(recursive=True)
                                    if not any(s in str(p.relative_to(self.root)) for s in module.SKIP)
                                    and not p.name.endswith("NODE-INDEX.md")] + [
            str(self.root / f) for f in module.ROOT_DOCS if (self.root / f).exists()]
        # ⛔ ARCHIVED NODES ARE RESOLVABLE LINK TARGETS, AND THIS LAMBDA COULD SEE 3 OF 251.
        # It globbed `<population folder>/{archive,_archive}/*.md` — non-recursive, and only for a
        # folder literally one level under a population folder. So `memory/_archive/reviews/`,
        # `memory/ops/artifacts/_archive/` and six more were invisible, leaving 248 real, existing
        # nodes unresolvable. Everything reading the store through this contract then reported ~55
        # dangling links that all point at files that exist: `librarian status` said 55 where
        # standalone node-health said 0.
        #
        # ⚠ THIS IS THE THIRD TIME THIS EXACT BUG HAS BEEN PAID FOR. node-health's own comment
        # records it from 2026-08-10 ("19 permanently-red dangling links ... the resolver could not
        # see the folder") and its verdict applies here: A PERMANENTLY-RED CHECK IS WORSE THAN NO
        # CHECK, because it trains every session to skim the boot surface.
        # ⇒ Reuse node-health's OWN rule — a recursive walk filtered by its archived_dirs() policy —
        # rather than a second, narrower re-implementation of "what counts as archived".
        module.archived_files = lambda: sorted(
            str(p) for p in self.memory_dir.glob("**/*.md")
            if any(a in p.relative_to(self.root).as_posix() for a in module.archived_dirs()))
        return module

    def run_script(self, name, command, *args, required=True):
        path = self.script(name, command, required)
        if path is None:
            return subprocess.CompletedProcess([], 0, "", "")
        result = subprocess.run([sys.executable, str(path), *args], cwd=self.root,
                                env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.root)},
                                capture_output=True, text=True)
        if result.returncode:
            raise ContractError(f"{command}: {path} failed (exit {result.returncode}): "
                                f"{result.stderr.strip() or result.stdout.strip()}")
        return result


def main():
    try:
        contract = StoreContract()
        for directory in contract.population():
            print(directory)
        return 0
    except ContractError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
