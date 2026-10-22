"""The fork's easy Windows installer (packaging/fork): Strata-Turbo-Install.cmd and easy-install.ps1.

The files' form (an ASCII .cmd with CRLF and its PowerShell part, a UTF-8 easy-install.ps1 with a BOM, both parsed by
PowerShell), the checks' plain-language stops with faked hardware (STRATA_TEST_*: nothing on the PC is looked at or
changed), and the uninstall: it removes the install folder and the shortcuts, keeps the model unless told otherwise,
and never deletes a model folder outside the install folder. No GPU, no download."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORK = ROOT / "packaging" / "fork"
CMD = FORK / "Strata-Turbo-Install.cmd"
PS1 = FORK / "easy-install.ps1"
MARKER = "#STRATA-BOOTSTRAP#"
POWERSHELL = shutil.which("powershell") if os.name == "nt" else None


def parse_errors(code_path: Path | None = None, text: str | None = None) -> str:
    if code_path is not None:
        src = "[System.Management.Automation.Language.Parser]::ParseFile('%s',[ref]$t,[ref]$e)" % str(code_path).replace("'", "''")
    else:
        src = "[System.Management.Automation.Language.Parser]::ParseInput([Console]::In.ReadToEnd(),[ref]$t,[ref]$e)"
    cmd = "$e=$null; $t=$null; " + src + " | Out-Null; if ($e.Count) { $e | ForEach-Object { $_.Message }; exit 1 } else { 'ok' }"
    r = subprocess.run([POWERSHELL, "-NoProfile", "-Command", cmd], input=text, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return "" if r.returncode == 0 else (r.stdout + r.stderr)


class Files(unittest.TestCase):
    def test_cmd_is_ascii_crlf_with_its_powershell_part(self):
        raw = CMD.read_bytes()
        raw.decode("ascii")                                       # ASCII only: any code page reads it the same
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), "CRLF line endings only")
        text = raw.decode("ascii")
        self.assertIn("powershell.exe -NoProfile -ExecutionPolicy Bypass", text)
        head, sep, tail = text.partition("\r\n" + MARKER + "\r\n")
        self.assertTrue(sep, "the PowerShell part starts at its marker line")
        self.assertNotIn(MARKER, head, "the command line builds the marker, so LastIndexOf finds only the real one")
        self.assertTrue(head.rstrip().endswith("exit /b %RC%"), "cmd stops before the PowerShell part")
        self.assertIn("easy-install.ps1", tail)
        self.assertIn("releases/latest/download/", tail)
        self.assertIn("STRATA_RELEASE_DIR", tail)

    def test_easy_ps1_is_utf8_with_bom(self):
        raw = PS1.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), "Windows PowerShell 5.1 reads a file without a BOM as ANSI")
        text = raw.decode("utf-8-sig")
        self.assertIn("Проверяю компьютер", text)
        for flag in ("--setup", "--family", "cyber-tiel", "--yes", "--no-start", "--draft-vocab", "cyrillic"):
            self.assertIn("'" + flag + "'", text)

    def test_the_model_pins_match_setup(self):
        """The disk check and the download progress use setup's file name, folder and size for Cyber-Tiel UD-IQ4_XS."""
        sys.path.insert(0, str(ROOT))
        import setup  # noqa: E402
        fam = setup.OWN_PATH_FAMILIES["cyber-tiel"]
        name = fam["file"].format(q="UD-IQ4_XS")
        text = PS1.read_text(encoding="utf-8-sig")
        self.assertIn("$ModelFile = '%s'" % name, text)
        self.assertIn("$ModelTag = '%s'" % (fam["tag"] + "UD-IQ4_XS"), text)
        self.assertIn("$ModelBytes = %d" % fam["sha256"][name][0], text)
        self.assertEqual(setup.own_path_size(fam, 31.8), "UD-IQ4_XS", "a 32 GB PC gets the size the installer plans for")
        self.assertIn("$MinDriver = %d" % setup.MIN_DRIVER, text)

    @unittest.skipUnless(POWERSHELL, "Windows PowerShell")
    def test_both_parse(self):
        self.assertEqual(parse_errors(PS1), "")
        tail = CMD.read_text(encoding="ascii").partition(MARKER)[2]
        self.assertEqual(parse_errors(text=MARKER + tail), "")


@unittest.skipUnless(POWERSHELL, "Windows PowerShell")
class Checks(unittest.TestCase):
    """STRATA_CHECK_ONLY with faked hardware: each failed check stops with its sentence, before any download."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="strata-easy-test-"))
        rel = self.tmp / "release"
        rel.mkdir()
        (rel / "Strata-Turbo-9.9.9-windows-cuda13.zip").write_bytes(b"")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("STRATA_")}
        self.env.update({"STRATA_CHECK_ONLY": "1", "STRATA_NO_PAUSE": "1", "STRATA_RELEASE_DIR": str(rel),
                         "STRATA_HOME": str(self.tmp / "home"), "APPDATA": str(self.tmp / "appdata"),
                         "TEMP": str(self.tmp), "TMP": str(self.tmp),
                         "STRATA_TEST_GPU": "NVIDIA GeForce RTX 4070;8.9;590.10;12282", "STRATA_TEST_RAM_GB": "64",
                         "STRATA_TEST_FREE_GB": "500", "STRATA_TEST_OFFLINE": "1", "STRATA_LANG": "ru"})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_checks(self, **env) -> tuple[int, str]:
        e = dict(self.env, **env)
        r = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PS1)], env=e,
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
        out = r.stdout.decode("utf-8", errors="replace") + r.stderr.decode("utf-8", errors="replace")
        return r.returncode, out

    def test_no_nvidia_card(self):
        rc, out = self.run_checks(STRATA_TEST_GPU="none")
        self.assertEqual(rc, 1, out)
        self.assertIn("не найдена видеокарта NVIDIA", out)

    def test_no_driver(self):
        rc, out = self.run_checks(STRATA_TEST_GPU="nodriver")
        self.assertEqual(rc, 1, out)
        self.assertIn("драйвер не установлен", out)

    def test_an_older_card(self):
        rc, out = self.run_checks(STRATA_TEST_GPU="NVIDIA GeForce GTX 1080;6.1;590.10;8192")
        self.assertEqual(rc, 1, out)
        self.assertIn("слишком старая", out)

    def test_an_old_driver_says_how_to_update(self):
        rc, out = self.run_checks(STRATA_TEST_GPU="NVIDIA GeForce RTX 3060;8.6;566.36;12288")
        self.assertEqual(rc, 1, out)
        self.assertIn("версия 566.36, а нужна 580", out)
        self.assertIn("https://www.nvidia.com/ru-ru/drivers/", out)
        rc, out = self.run_checks(STRATA_TEST_GPU="NVIDIA GeForce RTX 3060;8.6;566.36;12288", STRATA_LANG="en")
        self.assertIn("version 566.36, and 580 or newer is needed", out)
        self.assertIn("https://www.nvidia.com/en-us/drivers/", out)

    def test_little_ram(self):
        rc, out = self.run_checks(STRATA_TEST_RAM_GB="16")
        self.assertEqual(rc, 1, out)
        self.assertIn("Мало оперативной памяти: 16 ГБ", out)
        self.assertIn("не меньше 32 ГБ", out)

    def test_little_disk(self):
        rc, out = self.run_checks(STRATA_TEST_FREE_GB="5")
        self.assertEqual(rc, 1, out)
        self.assertIn("Мало места на диске", out)

    def test_no_internet(self):
        rc, out = self.run_checks()
        self.assertEqual(rc, 1, out)
        self.assertIn("Нет связи с интернетом", out)
        self.assertIn("huggingface.co", out)

    def test_skip_checks_only_warns(self):
        rc, out = self.run_checks(STRATA_TEST_RAM_GB="16", STRATA_SKIP_CHECKS="1")
        self.assertIn("STRATA_SKIP_CHECKS=1", out)
        self.assertIn("Нет связи с интернетом", out, "it goes on to the next check")

    def test_nothing_is_created(self):
        self.run_checks(STRATA_TEST_GPU="none")
        self.run_checks()
        self.assertFalse((self.tmp / "home").exists(), "the checks make no install folder")


@unittest.skipUnless(POWERSHELL, "Windows PowerShell")
class Uninstall(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="strata-easy-test-"))
        self.home = self.tmp / "Strata-Turbo"
        ver = self.home / "9.9.9"
        ver.mkdir(parents=True)
        (ver / "START-HERE.bat").write_text("@echo off\r\n", encoding="ascii")
        (self.home / "install.log").write_text("log", encoding="utf-8")
        shutil.copy(PS1, self.home / "Strata-Turbo.ps1")
        self.model = self.home / "Strata-data" / "models" / "m.gguf"
        self.model.parent.mkdir(parents=True)
        with open(self.model, "wb") as f:                       # 0.1 GiB+ (sparse is fine): a model worth asking about
            f.truncate(120 << 20)
        self.links = self.tmp / "links"
        (self.links / "Desktop").mkdir(parents=True)
        (self.links / "Programs" / "Strata Turbo").mkdir(parents=True)
        (self.links / "Desktop" / "Strata Turbo.lnk").write_bytes(b"x")
        (self.links / "Programs" / "Strata Turbo" / "Strata Turbo.lnk").write_bytes(b"x")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("STRATA_")}
        self.env.update({"STRATA_NO_PAUSE": "1", "STRATA_SHORTCUTS_DIR": str(self.links), "APPDATA": str(self.tmp / "appdata"),
                         "TEMP": str(self.tmp), "TMP": str(self.tmp),
                         "STRATA_LANG": "ru"})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def uninstall(self, answers: str, **env) -> str:
        e = dict(self.env, STRATA_UNINSTALL_ANSWERS=answers, **env)
        r = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.home / "Strata-Turbo.ps1"),
                            "uninstall"], env=e, stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
        out = r.stdout.decode("utf-8", errors="replace") + r.stderr.decode("utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, out)
        return out

    def test_no_keeps_everything(self):
        self.uninstall("н")
        self.assertTrue((self.home / "9.9.9").is_dir())
        self.assertTrue((self.links / "Desktop" / "Strata Turbo.lnk").exists())

    def test_y_on_the_english_layout_is_not_yes_in_russian(self):
        """"y" is н (no) typed with the English layout: in Russian it must not delete anything."""
        self.uninstall("y")
        self.assertTrue((self.home / "9.9.9").is_dir())

    def test_yes_keeps_the_model_by_default(self):
        out = self.uninstall("д,н")
        self.assertFalse((self.home / "9.9.9").exists())
        self.assertFalse((self.home / "Strata-Turbo.ps1").exists())
        self.assertTrue(self.model.exists(), out)
        self.assertFalse((self.links / "Desktop" / "Strata Turbo.lnk").exists())
        self.assertFalse((self.links / "Programs" / "Strata Turbo").exists())
        self.assertIn("Модель осталась", out)

    def test_yes_yes_removes_the_model_too(self):
        self.uninstall("д,д")
        self.assertFalse(self.home.exists())

    def test_files_it_did_not_make_stay(self):
        (self.home / "notes.txt").write_text("mine", encoding="utf-8")
        other = self.home / "Strata"                              # a checkout someone keeps there: not a version folder
        other.mkdir()
        (other / "START-HERE.bat").write_text("@echo off\r\n", encoding="ascii")
        out = self.uninstall("д,д")
        self.assertTrue((self.home / "notes.txt").exists(), out)
        self.assertTrue((other / "START-HERE.bat").exists(), out)
        self.assertFalse((self.home / "9.9.9").exists())

    def test_a_model_folder_outside_the_install_is_never_deleted(self):
        outside = self.tmp / "shared-data"
        (outside / "models").mkdir(parents=True)
        keep = outside / "models" / "shared.gguf"
        keep.write_bytes(b"model")
        out = self.uninstall("д,д", STRATA_DATA_DIR=str(outside))
        self.assertTrue(keep.exists(), out)
        self.assertIn("общие", out)


DUMMY_SERVER = '''import http.server, json, sys
port = int(sys.argv[sys.argv.index("--port") + 1])
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"busy": False, "queued": 0}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a):
        pass
http.server.HTTPServer(("127.0.0.1", port), H).serve_forever()
'''


@unittest.skipUnless(POWERSHELL, "Windows PowerShell")
class StartStop(unittest.TestCase):
    """The desktop icon and Stop, with a stand-in server.py behind a real run-<tag>.bat (no GPU, no model)."""

    def setUp(self):
        import socket
        self.tmp = Path(tempfile.mkdtemp(prefix="strata-easy-test-"))
        self.home = self.tmp / "Strata-Turbo"
        ver = self.home / "9.9.9"
        (ver / "serve").mkdir(parents=True)
        (ver / "START-HERE.bat").write_text("@echo off\r\n", encoding="ascii")
        (ver / "serve" / "server.py").write_text(DUMMY_SERVER, encoding="utf-8")
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        (ver / "run-cybertiel-test.bat").write_text(
            '@echo off\r\n"%s" "%s" --port %d\r\n' % (sys.executable, ver / "serve" / "server.py", self.port), encoding="ascii")
        (ver / "strata-cybertiel-test.json").write_text('{"port": %d}' % self.port, encoding="utf-8")
        shutil.copy(PS1, self.home / "Strata-Turbo.ps1")
        self.opened = self.tmp / "opened.txt"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("STRATA_")}
        self.env.update({"STRATA_NO_PAUSE": "1", "STRATA_LANG": "ru", "STRATA_OPEN_URL_LOG": str(self.opened),
                         "APPDATA": str(self.tmp / "appdata"), "TEMP": str(self.tmp), "TMP": str(self.tmp)})
        self.serving = None

    def tearDown(self):
        if self.serving is not None and self.serving.poll() is None:
            self.launcher("stop")
            self.serving.kill()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def launcher(self, mode: str) -> str:
        r = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.home / "Strata-Turbo.ps1"), mode],
                           env=self.env, stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
        return r.stdout.decode("utf-8", errors="replace") + r.stderr.decode("utf-8", errors="replace")

    def up(self) -> bool:
        import urllib.request
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/status" % self.port, timeout=2) as r:
                return r.status == 200
        except OSError:
            return False

    def test_start_again_opens_the_chat_and_stop_ends_the_window(self):
        import time
        self.serving = subprocess.Popen([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                         str(self.home / "Strata-Turbo.ps1"), "start"], env=self.env,
                                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for _ in range(60):
            if self.up():
                break
            time.sleep(0.5)
        self.assertTrue(self.up(), "the run script's server answers")
        self.assertTrue((self.home / "strata-turbo.pid").exists())
        out = self.launcher("start")
        self.assertIn("уже работает", out)
        self.assertIn("http://127.0.0.1:%d/" % self.port, self.opened.read_text(encoding="utf-8"))
        out = self.launcher("stop")
        self.assertIn("Strata Turbo выключена", out)
        code = self.serving.wait(timeout=30)
        text = self.serving.stdout.read().decode("utf-8", errors="replace")
        self.assertEqual(code, 0, text)
        self.assertIn("Включить снова", text, "the window says it was stopped, not that it failed")
        self.assertFalse(self.up())
        self.assertFalse((self.home / "strata-turbo.pid").exists())
        self.assertIn("сейчас не запущена", self.launcher("stop"))

    def test_a_stale_pid_file_does_not_block_the_start(self):
        """A window closed with its cross leaves the PID file: a process that now has that PID is not Strata."""
        (self.home / "strata-turbo.pid").write_text("%d 1" % os.getpid(), encoding="ascii")
        self.serving = subprocess.Popen([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                         str(self.home / "Strata-Turbo.ps1"), "start"], env=self.env,
                                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        import time
        for _ in range(60):
            if self.up():
                break
            time.sleep(0.5)
        self.assertTrue(self.up())
        self.launcher("stop")
        self.serving.wait(timeout=30)


if __name__ == "__main__":
    unittest.main()
