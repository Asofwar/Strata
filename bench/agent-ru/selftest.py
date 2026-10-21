"""bench/agent-ru/selftest.py - checks the tasks and the tools without a server.

For every task: the untouched repository fails the hidden tests, the reference solution passes the visible and
hidden ones, and a run that only rewrites the visible tests still fails (score_run restores them).  Then the
sandbox tools are exercised once (path escapes, edit_file uniqueness, the run_command allow-list, malformed calls).

    python bench/agent-ru/selftest.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_agent as R  # noqa: E402


def main():
    bad = 0
    ids = [t["id"] for t in R.TASKS]
    assert len(ids) == len(set(ids)), "duplicate task ids"
    with tempfile.TemporaryDirectory() as d:
        for t in R.TASKS:
            root = Path(d) / t["id"]
            R.write_tree(root / "orig", t["files"])
            ok0, v0, h0, _ = R.score_run(root / "orig", t)
            R.write_tree(root / "sol", t["files"])
            R.write_tree(root / "sol", t["solution"])
            ok1, v1, h1, why1 = R.score_run(root / "sol", t)
            R.write_tree(root / "cheat", t["files"])
            for rel in t["files"]:
                if rel.startswith("tests/"):
                    R.write_tree(root / "cheat", {rel: ""})
            ok2, *_ = R.score_run(root / "cheat", t)
            visible_fails = R.run_proc(R.test_cmd(t["lang"], "tests"), root / "orig", 120)[0] != 0
            good = (not ok0) and ok1 and not ok2
            bad += not good
            print(f"{t['id']:22} {t['lang']:6} {t['kind']:11} ru={int(t['ru'])} original hidden exit {h0} "
                  f"(visible {'fails' if visible_fails else 'passes'}), solution {'PASS' if ok1 else 'FAIL ' + why1}"
                  f"{'' if good else '  <-- BAD'}", flush=True)
        sb = R.Sandbox(Path(d) / "tools", "python")
        sb.root.mkdir()
        sb.write_file("a/b.py", "x = 1\nx = 1\n")
        checks = [
            ("escape", lambda: sb.read_file("../x"), ValueError),
            ("abs escape", lambda: sb.write_file("C:/Windows/x.txt", "y"), ValueError),
            ("edit twice", lambda: sb.edit_file("a/b.py", "x = 1", "x = 2"), ValueError),
            ("not allowed", lambda: sb.run_command("cmd /c dir"), ValueError),
        ]
        for name, fn, exc in checks:
            try:
                fn()
                print(f"tool check {name}: no error  <-- BAD")
                bad += 1
            except exc:
                pass
        assert "1| x = 1" in sb.read_file("a/b.py")
        assert "exit code 0" in sb.run_command('python -c "print(1)"')
        assert R.call_tool(sb, "nope", {})[1] == "unknown tool"
        assert R.call_tool(sb, "read_file", {})[1] == "missing argument"
        assert R.call_tool(sb, "read_file", {"path": "a/b.py", "lines": 3})[1] == "bad argument"
        assert R.call_tool(sb, "finish", {"summary": "x"})[2] is True
        assert R.TEXT_CALL.search('<tool_call>{"name": "read_file"}')
        print("tool checks done")
    print(f"{len(R.TASKS)} tasks, {bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
