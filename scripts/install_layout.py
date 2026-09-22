#!/usr/bin/env python3
"""install_layout.py — the published install layout, parsed. ONE owner, no side effects.

⛔ WHY THIS EXISTS. `store_contract.py` — a RUNTIME library the maintenance agents load — used to reach
its layout parser by dynamically importing `check-portable-store-contract.py`, a CI gate:

    checker = Path(__file__).with_name("check-portable-store-contract.py")
    spec = importlib.util.spec_from_file_location(...)

That is backwards. A library must not depend on a checker, and the consequence was concrete: shipping
the agents meant shipping the gate, the gate's own matcher constants ("/Users/", "/home/", "~/") then
tripped its own ABSOLUTE-PATH rule when it appeared in its own closure, and a stranger got a CI tool
they never asked for. The dependency was also INVISIBLE to static analysis — neither an import nor a
declared requirement — so all four agents died on a clean install with `No such file`, and only running
them in a bare tree revealed it.

🔑 Both sides now import THIS. The parser is unchanged, so the gate and the contract cannot drift into
disagreeing about what the install page says — which was the other, quieter risk of having one of them
own it.
"""
import posixpath
import re

def parse_layout(path):
    """Accept one unambiguous, indented directory tree; never infer from repo files."""
    text = path.read_text(encoding="utf-8")
    candidates = []
    for block in re.findall(r"^```[^\n]*\n(.*?)^```\s*$", text, re.M | re.S):
        lines = block.strip("\n").splitlines()
        if not lines or not re.fullmatch(r"[^\s]+/", lines[0]):
            continue
        directories, files = set(), set()
        stack = [(-1, "")]
        valid = True
        for line in lines[1:]:
            if not line.strip():
                continue
            match = re.fullmatch(r"( +)([\w./-]+/)(?:\s+(.*))?", line)
            if not match:
                valid = False
                break
            spaces, name, description = match.groups()
            if name.startswith("/") or ".." in name.split("/"):
                valid = False
                break
            depth = len(spaces)
            while stack[-1][0] >= depth:
                stack.pop()
            directory = posixpath.join(stack[-1][1], name.rstrip("/"))
            directories.add(directory)
            stack.append((depth, directory))
            tokens = (description or "").split()
            # File inventories contain filenames only; prose is not a manifest.
            if tokens and all(re.fullmatch(r"[\w.-]+\.(?:py|sh|mjs)", t) for t in tokens):
                files.update(posixpath.join(directory, t) for t in tokens)
        if valid and directories and files:
            candidates.append((directories, files))
    if len(candidates) != 1:
        raise ValueError(f"cannot parse layout from {path}: expected one directory tree with a script inventory")
    return candidates[0]
