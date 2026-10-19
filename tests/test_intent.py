"""Intent ordering, process-crash recovery and portable journal acceptance."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from crystals.intent import IntentLog
from crystals.platform import subprocess_options


class IntentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="intent café space ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "memory").mkdir()
        self.log = IntentLog(self.root)

    def run_python(self, *args):
        return subprocess.run([sys.executable, *args], capture_output=True,
                              text=True, encoding="utf-8", timeout=20,
                              **subprocess_options())

    def test_order_success_failure_and_append_only(self):
        with self.log.action("write", "café\nline", "session:a") as ident:
            raw = self.log.path.read_bytes()
            self.assertEqual([ident], [r["id"] for r in IntentLog(self.root).recovery["pending"]])
        self.assertTrue(self.log.path.read_bytes().startswith(raw))
        with self.assertRaises(RuntimeError):
            with self.log.action("bash", "failing act", "session:b"):
                raise RuntimeError("act failed")
        rows = [json.loads(l) for l in self.log.path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(["intended", "committed", "intended", "aborted"], [r["status"] for r in rows])
        self.assertNotIn(b"\r", self.log.path.read_bytes())
        self.assertIn("café", self.log.path.read_text(encoding="utf-8"))
        self.assertEqual([], IntentLog(self.root).recovery["pending"])

    def test_real_crash_releases_lock_and_reports_unknown(self):
        child = self.run_python("-c", "from crystals.intent import IntentLog; import os,sys; "
                                "j=IntentLog(sys.argv[1]); j.begin('bash','crashed','old'); os._exit(9)",
                                str(self.root))
        self.assertEqual(9, child.returncode, child.stderr)
        restarted = IntentLog(self.root)
        self.assertEqual("crashed", restarted.recovery["pending"][0]["text"])
        ident = restarted.begin("write", "new act", "new")
        restarted.finish(ident, "committed")
        self.assertEqual(1, len(restarted.pending()["pending"]))

    def test_logging_failure_prevents_act(self):
        reached = []
        with patch("crystals.intent.os.fsync", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                with self.log.action("write", "blocked", "session"):
                    reached.append(True)
        self.assertEqual([], reached)

    def test_terminal_validation_and_idempotent_retry(self):
        ident = self.log.begin("bash", "ls", "session")
        self.log.finish(ident, "committed")
        before = self.log.path.read_bytes()
        self.log.finish(ident, "committed")
        self.assertEqual(before, self.log.path.read_bytes())
        for args in ((ident, "aborted"), ("unknown", "committed"), (ident, "other")):
            with self.assertRaises(ValueError):
                self.log.finish(*args)
        with self.assertRaises(ValueError):
            self.log.begin("bash", "ls", "")

    def test_torn_tail_is_reported_and_blocks_new_acts(self):
        ident = self.log.begin("bash", "before torn write", "session")
        with self.log.path.open("ab") as f:
            f.write(b'{"id":')
        restarted = IntentLog(self.root)
        self.assertEqual([2], restarted.recovery["torn_lines"])
        self.assertEqual(ident, restarted.recovery["pending"][0]["id"])
        before = self.log.path.read_bytes()
        with self.assertRaises(ValueError):
            restarted.begin("bash", "after", "session")
        self.assertEqual(before, self.log.path.read_bytes())
        self.log.path.write_bytes(before + b"\n")
        with self.assertRaises(ValueError):
            IntentLog(self.root)

    def test_concurrent_processes_do_not_lose_or_mix_rows(self):
        code = ("from crystals.intent import IntentLog; import sys; "
                "j=IntentLog(sys.argv[1]); i=j.begin('bash',sys.argv[2],'parallel'); "
                "j.finish(i,'committed')")
        children = [subprocess.Popen([sys.executable, "-c", code, str(self.root), str(i)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, **subprocess_options()) for i in range(8)]
        for child in children:
            _, error = child.communicate(timeout=20)
            self.assertEqual(0, child.returncode, error)
        rows = [json.loads(l) for l in self.log.path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(16, len(rows))
        self.assertEqual(8, len({r["id"] for r in rows}))
        self.assertEqual([], IntentLog(self.root).recovery["pending"])

    def test_cli_lifecycle_and_original_readonly_matching(self):
        plain = self.run_python("-m", "crystals", "--store", str(self.root), "--act", "bash")
        self.assertEqual([], json.loads(plain.stdout))
        self.assertFalse(self.log.path.exists())
        begin = self.run_python("-m", "crystals", "--store", str(self.root), "--act", "bash",
                                "--text", "café", "--intent-log", "--session", "cli")
        self.assertEqual(0, begin.returncode, begin.stderr)
        ident = json.loads(begin.stdout)["intent_id"]
        recover = self.run_python("-m", "crystals.intent", "--store", str(self.root), "recover")
        self.assertEqual(ident, json.loads(recover.stdout)["pending"][0]["id"])
        finish = self.run_python("-m", "crystals.intent", "--store", str(self.root), "aborted", ident)
        self.assertEqual(0, finish.returncode, finish.stderr)
        self.assertEqual([], IntentLog(self.root).recovery["pending"])


if __name__ == "__main__":
    unittest.main()
