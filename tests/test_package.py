"""Runtime acceptance, including Windows rules and a real MCP pipe exchange."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from crystals import match
from crystals.platform import reserved_name, subprocess_options
from crystals import act, registry

FIXTURE = '''---
crystal:
  deliver: act
  on: bash,write
  match: | tail, café, guard
  who: all
---
<!-- crystal:essence -->
Check the command's exit code. Café — verify it.
<!-- /crystal:essence -->
'''


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="crystals space ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.memory = self.root / "memory" / "crystals"
        self.memory.mkdir(parents=True)
        (self.memory / "probe.md").write_bytes(FIXTURE.encode())
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("CRYSTAL_", "CLAUDE_"))}
        self.env["PYTHONIOENCODING"] = "utf-8"
        self.env_patch = patch.dict(os.environ, self.env, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def run_python(self, *args, input=None, cwd=None):
        return subprocess.run([sys.executable, *args], input=input, cwd=cwd,
                              capture_output=True, text=True, encoding="utf-8",
                              env=self.env, timeout=20, **subprocess_options())

    def test_crlf_same_match_and_no_bash_or_mutation(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*.md")}
        with patch("subprocess.run", side_effect=AssertionError("no subprocess")), \
             patch("subprocess.Popen", side_effect=AssertionError("no subprocess")):
            lf = match("bash", "go test | tail", store=self.root)
            self.assertEqual(len(lf), 1)
            (self.memory / "probe.md").write_bytes(FIXTURE.replace("\n", "\r\n").encode())
            self.assertEqual(lf, match("bash", "go test | tail", store=self.root))
            self.assertEqual([], match("bash", "unrelated", store=self.root))
            self.assertEqual([], match("bash", "guardrail", store=self.root))
            self.assertEqual(1, len(match("bash", "café", store=self.root)))
        self.assertFalse((self.root / "scratch").exists())
        self.assertEqual(set(before), set(self.root.rglob("*.md")))

    def test_utf8_bom_crystal_is_still_delivered(self):
        # Notepad / PowerShell 5.1 Out-File write a BOM by default; a plain utf-8 read made the crystal vanish (crystals#1, ManSio 2026-10-13).
        plain = match("bash", "go test | tail", store=self.root)
        self.assertEqual(len(plain), 1)
        for body in (FIXTURE, FIXTURE.replace("\n", "\r\n")):
            (self.memory / "probe.md").write_bytes(b"\xef\xbb\xbf" + body.encode())
            self.assertEqual(plain, match("bash", "go test | tail", store=self.root))

    def test_symlink_out_of_store_is_not_delivered(self):
        # A *.md symlink whose target lives outside the store was read as a crystal (crystals#1, ManSio 2026-10-13).
        other = tempfile.TemporaryDirectory(prefix="crystals outside ")
        self.addCleanup(other.cleanup)
        outside = Path(other.name)
        (outside / "planted.md").write_bytes(FIXTURE.replace("tail, café, guard", "planted").encode())
        try:
            os.symlink(outside / "planted.md", self.memory / "innocent.md")
            os.symlink(self.memory / "probe.md", self.memory / "alias.md")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not permitted on this runner")
        self.assertEqual([], match("bash", "go test | planted", store=self.root))
        hits = match("bash", "go test | tail", store=self.root)
        self.assertTrue(hits, "positive control: an in-store crystal still delivers")

    def test_reserved_walk_prunes_before_reading(self):
        for name in ("nul", "NUL.md", "con.txt", "COM1", "lpt9.log", "COM¹"):
            self.assertTrue(reserved_name(name), name)
        self.assertFalse(reserved_name("console.md"))
        directories = ["nul", "CON", "good"]
        def walk(base):
            yield str(self.memory), directories, ["NUL.md", "probe.md"]
            self.assertEqual(["good"], directories)
        import builtins
        original_open = builtins.open
        opened = []
        def checked_open(path, *args, **kwargs):
            opened.append(Path(path).name)
            return original_open(path, *args, **kwargs)
        with patch.object(registry.os, "walk", side_effect=walk), \
             patch("builtins.open", side_effect=checked_open):
            self.assertEqual(1, len(registry.load_crystals(self.root)))
        self.assertTrue(opened)
        self.assertFalse(any(reserved_name(name) for name in opened))

    def test_lf_ledger_and_windows_process_flags(self):
        with patch.object(act, "LEDGER", self.root / "scratch" / "ledger.json"):
            act._save({"message": "first\nsecond"})
            raw = act.LEDGER.read_bytes()
            self.assertNotIn(b"\r", raw)
            self.assertEqual("first\nsecond", json.loads(raw)["message"])
        with patch("crystals.platform.os.name", "nt"), \
             patch("crystals.platform.subprocess.CREATE_NO_WINDOW", 0x08000000, create=True):
            self.assertEqual({"creationflags": 0x08000000}, subprocess_options())

    def test_expired_and_refused_are_withheld(self):
        path = self.memory / "probe.md"
        path.write_text(FIXTURE.replace("  who: all", "  who: all\n  stale_after: 2000-01-01"),
                        encoding="utf-8", newline="\n")
        result = match("bash", "guard", store=self.root)[0]
        self.assertTrue(result["expired"])
        self.assertNotIn("Café", result["essence"])
        path.write_text(FIXTURE, encoding="utf-8", newline="\n")
        verdict = self.root / "memory/research/paper-data/discriminator-runs.jsonl"
        verdict.parent.mkdir(parents=True)
        verdict.write_text(json.dumps({"crystal": "probe.md", "verdict": "fail"}) + "\n",
                           encoding="utf-8", newline="\n")
        self.assertTrue(match("bash", "guard", store=self.root)[0]["expired"])

    def test_cli_and_legacy_hook(self):
        cli = self.run_python("-m", "crystals", "--store", str(self.root),
                              "--act", "bash", "--text", "café")
        self.assertEqual(0, cli.returncode, cli.stderr)
        self.assertEqual(1, len(json.loads(cli.stdout)))
        self.assertNotIn("\r", cli.stdout)
        from scripts import crystal_act
        self.assertIs(crystal_act, act)
        with patch.object(act, "REPO", self.root), \
             patch.object(act, "LEDGER", self.root / "scratch/.act-ledger.json"):
            due = act.due_for("bash", "test", repo=self.root, ctx="go test | tail")
            self.assertEqual(1, len(due))

    def test_mcp_stdio_smoke_and_errors(self):
        def request(i, method, params=None):
            return {"jsonrpc": "2.0", "id": i, "method": method, "params": params or {}}
        messages = [request(1, "initialize", {"protocolVersion": "2025-06-18",
                    "capabilities": {}, "clientInfo": {"name": "smoke", "version": "1"}}),
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    request(2, "tools/list"),
                    request(3, "tools/call", {"name": "match", "arguments": {
                        "act": "bash", "text": "café"}}),
                    request(4, "tools/call", {"name": "match", "arguments": {
                        "act": "bash", "text": 12}}), request(5, "unknown")]
        result = self.run_python("-m", "crystals.mcp", "--store", str(self.root),
                                 input="\n".join(json.dumps(m) for m in messages)+"\n{bad\n")
        self.assertEqual(0, result.returncode, result.stderr)
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([1, 2, 3, 4, 5, None], [r["id"] for r in rows])
        self.assertEqual("2025-06-18", rows[0]["result"]["protocolVersion"])
        self.assertEqual("match", rows[1]["result"]["tools"][0]["name"])
        self.assertEqual(1, len(json.loads(rows[2]["result"]["content"][0]["text"])))
        self.assertEqual([-32602, -32601, -32700], [r["error"]["code"] for r in rows[3:]])
        self.assertFalse((self.root / "scratch").exists())
        print("MCP smoke: initialize + tools/list + match over stdio PASS")

    def test_core_imports_are_stdlib(self):
        root = Path(__file__).resolve().parents[1] / "crystals"
        for path in root.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module] if isinstance(node, ast.ImportFrom) and not node.level else []
                for name in names:
                    self.assertIn(name.split(".")[0], sys.stdlib_module_names, (path, name))

    def test_every_text_read_names_utf8(self):
        # Windows defaults to cp1252: a bare read_text()/open() decodes UTF-8 essences wrongly (QC 2026-10-12).
        root = Path(__file__).resolve().parents[1] / "crystals"
        bad = []
        for path in root.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.Call):
                    continue
                name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
                if name not in ("read_text", "open"):
                    continue
                mode = next((a.value for a in node.args[1:2] if isinstance(a, ast.Constant)), "r")
                if name == "open" and "b" in str(mode):
                    continue
                if not any(k.arg == "encoding" for k in node.keywords):
                    bad.append(f"{path.name}:{node.lineno}")
        self.assertEqual(bad, [], "text reads without encoding=")


if __name__ == "__main__":
    unittest.main()
