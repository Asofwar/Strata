"""bench/agent-ru/tasks_js.py - the JavaScript and TypeScript tasks of the agentic benchmark (Node 24: node:test,
ES modules, .ts files run by Node's own type stripping, so imports name the .ts file).

Visible tests: `node --test "tests/*.test.mjs"` (TypeScript: `tests/*.test.ts`); hidden tests: the same in _hidden/.
"""
from textwrap import dedent as d

TASKS = []


def task(**kw):
    kw.setdefault("ru", False)
    TASKS.append(kw)


# 13. fix a failing test -----------------------------------------------------------------------------------------
task(
    id="js-fix-deepmerge", lang="js", kind="fix-test",
    prompt="The tests fail. Fix src/merge.mjs so that deepMerge does what its comment says; do not change the tests.",
    files={
        "package.json": '{ "name": "merge", "type": "module", "scripts": { "test": "node --test tests/" } }\n',
        "src/merge.mjs": d('''\
            // deepMerge(target, source): a NEW object with the keys of both; neither argument is modified.
            // Where both values are plain objects they are merged recursively; otherwise the value from
            // `source` (a plain object, array, null, number, string, Date) replaces the one in `target`,
            // copied, never merged with it (arrays are copied too).
            export function deepMerge(target, source) {
              for (const key of Object.keys(source)) {
                const value = source[key];
                if (typeof value === "object") {
                  target[key] = deepMerge(target[key] || {}, value);
                } else {
                  target[key] = value;
                }
              }
              return target;
            }
            '''),
        "tests/merge.test.mjs": d('''\
            import { test } from "node:test";
            import assert from "node:assert/strict";
            import { deepMerge } from "../src/merge.mjs";

            test("nested objects merge", () => {
              assert.deepEqual(deepMerge({ a: { x: 1 } }, { a: { y: 2 } }), { a: { x: 1, y: 2 } });
            });

            test("arrays are replaced", () => {
              assert.deepEqual(deepMerge({ list: [1, 2, 3] }, { list: [9] }), { list: [9] });
            });
            '''),
    },
    hidden={
        "_hidden/merge.test.mjs": d('''\
            import { test } from "node:test";
            import assert from "node:assert/strict";
            import { deepMerge } from "../src/merge.mjs";

            test("no mutation", () => {
              const a = { o: { x: 1 }, k: 1 };
              const b = { o: { y: 2 }, list: [1] };
              const r = deepMerge(a, b);
              assert.deepEqual(r, { o: { x: 1, y: 2 }, k: 1, list: [1] });
              assert.deepEqual(a, { o: { x: 1 }, k: 1 });
              assert.deepEqual(b, { o: { y: 2 }, list: [1] });
              assert.notEqual(r.list, b.list);
              assert.notEqual(r.o, a.o);
            });

            test("null and scalars replace", () => {
              assert.deepEqual(deepMerge({ a: { x: 1 } }, { a: null }), { a: null });
              assert.deepEqual(deepMerge({ a: 1 }, { a: { z: 1 } }), { a: { z: 1 } });
              assert.deepEqual(deepMerge({ a: [1] }, { a: { z: 1 } }), { a: { z: 1 } });
              assert.deepEqual(deepMerge({ a: { z: 1 } }, { a: [2] }), { a: [2] });
              const d = new Date(0);
              const r = deepMerge({ when: { x: 1 } }, { when: d });
              assert.ok(r.when instanceof Date);
            });

            test("deep", () => {
              assert.deepEqual(deepMerge({ a: { b: { c: 1, d: 2 } } }, { a: { b: { d: 3 }, e: 4 } }),
                               { a: { b: { c: 1, d: 3 }, e: 4 } });
              assert.deepEqual(deepMerge({}, {}), {});
            });
            '''),
    },
    solution={
        "src/merge.mjs": d('''\
            const isPlain = (v) => v !== null && typeof v === "object" && Object.getPrototypeOf(v) === Object.prototype;

            function clone(v) {
              if (Array.isArray(v)) return [...v];
              if (isPlain(v)) return deepMerge({}, v);
              return v;
            }

            export function deepMerge(target, source) {
              const out = {};
              for (const key of Object.keys(target)) out[key] = clone(target[key]);
              for (const key of Object.keys(source)) {
                const value = source[key];
                out[key] = isPlain(value) && isPlain(out[key]) ? deepMerge(out[key], value) : clone(value);
              }
              return out;
            }
            '''),
    },
)

# 14. implement to spec ------------------------------------------------------------------------------------------
task(
    id="js-impl-emitter", lang="js", kind="implement",
    prompt="Implement the Emitter class in src/emitter.mjs following the comments, and make the tests pass.",
    files={
        "package.json": '{ "name": "emitter", "type": "module" }\n',
        "src/emitter.mjs": d('''\
            // A small event emitter.
            //   on(event, fn)        add a listener; returns a function that removes exactly this registration
            //   once(event, fn)      like on(), but the listener is removed before its first call
            //   off(event, fn)       remove one registration of fn (the earliest); no error when absent
            //   emit(event, ...args) call the listeners in the order they were added, with args; returns how
            //                        many were called. Listeners added or removed during an emit do not change
            //                        which listeners that emit calls.
            //   listenerCount(event)
            // The same fn may be registered several times; each registration is called.
            export class Emitter {
              on(event, fn) { throw new Error("not implemented"); }
              once(event, fn) { throw new Error("not implemented"); }
              off(event, fn) { throw new Error("not implemented"); }
              emit(event, ...args) { throw new Error("not implemented"); }
              listenerCount(event) { throw new Error("not implemented"); }
            }
            '''),
        "tests/emitter.test.mjs": d('''\
            import { test } from "node:test";
            import assert from "node:assert/strict";
            import { Emitter } from "../src/emitter.mjs";

            test("on/emit", () => {
              const e = new Emitter();
              const got = [];
              e.on("x", (a, b) => got.push(a + b));
              assert.equal(e.emit("x", 1, 2), 1);
              assert.deepEqual(got, [3]);
            });
            '''),
    },
    hidden={
        "_hidden/emitter.test.mjs": d('''\
            import { test } from "node:test";
            import assert from "node:assert/strict";
            import { Emitter } from "../src/emitter.mjs";

            test("order, unsubscribe, count", () => {
              const e = new Emitter();
              const got = [];
              const f = () => got.push("f");
              const un = e.on("x", f);
              e.on("x", () => got.push("g"));
              e.on("x", f);
              assert.equal(e.listenerCount("x"), 3);
              assert.equal(e.emit("x"), 3);
              assert.deepEqual(got, ["f", "g", "f"]);
              un();
              assert.equal(e.listenerCount("x"), 2);
              got.length = 0;
              e.emit("x");
              assert.deepEqual(got, ["g", "f"]);
              assert.equal(e.emit("nothing"), 0);
              assert.equal(e.listenerCount("nothing"), 0);
            });

            test("once", () => {
              const e = new Emitter();
              let n = 0;
              e.once("x", (v) => { n += v; e.emit("x", 100); });
              assert.equal(e.emit("x", 1), 1);
              assert.equal(e.emit("x", 1), 0);
              assert.equal(n, 1);
              const fn = () => n++;
              e.once("y", fn);
              e.off("y", fn);
              assert.equal(e.emit("y"), 0);
            });

            test("changes during emit", () => {
              const e = new Emitter();
              const got = [];
              const b = () => got.push("b");
              e.on("x", () => { got.push("a"); e.off("x", b); e.on("x", () => got.push("c")); });
              e.on("x", b);
              assert.equal(e.emit("x"), 2);
              assert.deepEqual(got, ["a", "b"]);
              got.length = 0;
              e.emit("x");
              assert.deepEqual(got, ["a", "c"]);
            });

            test("off removes earliest only", () => {
              const e = new Emitter();
              const got = [];
              const f = (t) => got.push(t);
              e.on("x", f);
              e.on("x", () => got.push("mid"));
              e.on("x", f);
              e.off("x", f);
              e.off("x", () => {});
              e.emit("x", "f");
              assert.deepEqual(got, ["mid", "f"]);
            });
            '''),
    },
    solution={
        "src/emitter.mjs": d('''\
            export class Emitter {
              #map = new Map();
              #list(event) {
                if (!this.#map.has(event)) this.#map.set(event, []);
                return this.#map.get(event);
              }
              on(event, fn) {
                const reg = { fn, call: fn };
                this.#list(event).push(reg);
                return () => {
                  const l = this.#list(event);
                  const i = l.indexOf(reg);
                  if (i >= 0) l.splice(i, 1);
                };
              }
              once(event, fn) {
                const reg = { fn };
                reg.call = (...args) => {
                  const l = this.#list(event);
                  const i = l.indexOf(reg);
                  if (i >= 0) l.splice(i, 1);
                  return fn(...args);
                };
                this.#list(event).push(reg);
                return () => {
                  const l = this.#list(event);
                  const i = l.indexOf(reg);
                  if (i >= 0) l.splice(i, 1);
                };
              }
              off(event, fn) {
                const l = this.#list(event);
                const i = l.findIndex((r) => r.fn === fn);
                if (i >= 0) l.splice(i, 1);
              }
              emit(event, ...args) {
                const snap = [...this.#list(event)];
                for (const r of snap) r.call(...args);
                return snap.length;
              }
              listenerCount(event) {
                return this.#list(event).length;
              }
            }
            '''),
    },
)

# 15. add CLI flags (Russian) ------------------------------------------------------------------------------------
task(
    id="js-cli-todo", lang="js", kind="cli-flag", ru=True,
    prompt=d('''\
        В todo.mjs есть команда `list <файл.json>`. Добавь к ней:
        1. Фильтры `--done` (только выполненные) и `--pending` (только невыполненные). Оба сразу - ошибка:
           код 2 и сообщение в stderr, stdout пустой.
        2. `--format json`: вывести JSON-массив отфильтрованных задач (объекты как в файле) вместо строк
           "[x] title" / "[ ] title". `--format text` - текущий вывод (по умолчанию); другое значение - ошибка с
           кодом 2.
        Функция main(argv) должна по-прежнему возвращать {code, stdout, stderr}, а запуск
        `node todo.mjs list todos.json --done` - печатать stdout и выходить с этим кодом.'''),
    files={
        "package.json": '{ "name": "todo", "type": "module" }\n',
        "todo.mjs": d('''\
            import { readFileSync } from "node:fs";
            import { fileURLToPath } from "node:url";

            export function main(argv) {
              const [cmd, file] = argv;
              if (cmd !== "list" || !file) {
                return { code: 2, stdout: "", stderr: "usage: todo.mjs list <file.json>\\n" };
              }
              const todos = JSON.parse(readFileSync(file, "utf8"));
              const lines = todos.map((t) => `[${t.done ? "x" : " "}] ${t.title}`);
              return { code: 0, stdout: lines.join("\\n") + (lines.length ? "\\n" : ""), stderr: "" };
            }

            if (process.argv[1] === fileURLToPath(import.meta.url)) {
              const r = main(process.argv.slice(2));
              process.stdout.write(r.stdout);
              process.stderr.write(r.stderr);
              process.exitCode = r.code;
            }
            '''),
        "todos.json": '[{"title": "купить хлеб", "done": true}, {"title": "позвонить", "done": false}]\n',
        "tests/todo.test.mjs": d('''\
            import { test } from "node:test";
            import assert from "node:assert/strict";
            import { main } from "../todo.mjs";

            test("list", () => {
              const r = main(["list", "todos.json"]);
              assert.equal(r.code, 0);
              assert.equal(r.stdout, "[x] купить хлеб\\n[ ] позвонить\\n");
            });
            '''),
    },
    hidden={
        "_hidden/todo.test.mjs": d('''\
            import { test } from "node:test";
            import assert from "node:assert/strict";
            import { spawnSync } from "node:child_process";
            import { writeFileSync, mkdtempSync } from "node:fs";
            import { tmpdir } from "node:os";
            import { join } from "node:path";
            import { main } from "../todo.mjs";

            const dir = mkdtempSync(join(tmpdir(), "todo-"));
            const file = join(dir, "t.json");
            const items = [{ title: "a", done: true }, { title: "b", done: false, tag: "x" }, { title: "c", done: true }];
            writeFileSync(file, JSON.stringify(items));

            test("filters", () => {
              assert.equal(main(["list", file, "--done"]).stdout, "[x] a\\n[x] c\\n");
              assert.equal(main(["list", file, "--pending"]).stdout, "[ ] b\\n");
              assert.equal(main(["list", file]).stdout, "[x] a\\n[ ] b\\n[x] c\\n");
              assert.equal(main(["list", file, "--format", "text", "--pending"]).stdout, "[ ] b\\n");
            });

            test("json", () => {
              const r = main(["list", file, "--format", "json", "--pending"]);
              assert.equal(r.code, 0);
              assert.deepEqual(JSON.parse(r.stdout), [{ title: "b", done: false, tag: "x" }]);
              assert.deepEqual(JSON.parse(main(["list", file, "--format", "json"]).stdout), items);
            });

            test("errors", () => {
              const r = main(["list", file, "--done", "--pending"]);
              assert.equal(r.code, 2);
              assert.equal(r.stdout, "");
              assert.ok(r.stderr.length > 0);
              const r2 = main(["list", file, "--format", "xml"]);
              assert.equal(r2.code, 2);
              assert.equal(r2.stdout, "");
            });

            test("process", () => {
              const p = spawnSync(process.execPath, ["todo.mjs", "list", file, "--done", "--format", "json"],
                                  { encoding: "utf8" });
              assert.equal(p.status, 0);
              assert.deepEqual(JSON.parse(p.stdout), [items[0], items[2]]);
              const q = spawnSync(process.execPath, ["todo.mjs", "list", file, "--done", "--pending"],
                                  { encoding: "utf8" });
              assert.equal(q.status, 2);
            });
            '''),
    },
    solution={
        "todo.mjs": d('''\
            import { readFileSync } from "node:fs";
            import { fileURLToPath } from "node:url";
            import { parseArgs } from "node:util";

            const fail = (msg) => ({ code: 2, stdout: "", stderr: msg + "\\n" });

            export function main(argv) {
              let parsed;
              try {
                parsed = parseArgs({ args: argv, allowPositionals: true, options: {
                  done: { type: "boolean" }, pending: { type: "boolean" }, format: { type: "string", default: "text" } } });
              } catch (e) {
                return fail(e.message);
              }
              const { values, positionals } = parsed;
              const [cmd, file] = positionals;
              if (cmd !== "list" || !file) return fail("usage: todo.mjs list <file.json> [--done|--pending] [--format text|json]");
              if (values.done && values.pending) return fail("--done and --pending exclude each other");
              if (!["text", "json"].includes(values.format)) return fail(`unknown format ${values.format}`);
              let todos = JSON.parse(readFileSync(file, "utf8"));
              if (values.done) todos = todos.filter((t) => t.done);
              if (values.pending) todos = todos.filter((t) => !t.done);
              if (values.format === "json") return { code: 0, stdout: JSON.stringify(todos) + "\\n", stderr: "" };
              const lines = todos.map((t) => `[${t.done ? "x" : " "}] ${t.title}`);
              return { code: 0, stdout: lines.join("\\n") + (lines.length ? "\\n" : ""), stderr: "" };
            }

            if (process.argv[1] === fileURLToPath(import.meta.url)) {
              const r = main(process.argv.slice(2));
              process.stdout.write(r.stdout);
              process.stderr.write(r.stderr);
              process.exitCode = r.code;
            }
            '''),
    },
)

# 16. bug from a stack trace, across modules ---------------------------------------------------------------------
task(
    id="js-trace-report", lang="js", kind="stack-trace",
    prompt=d('''\
        Running `node src/cli.mjs data/empty.csv` crashes:

        file:///work/src/report.mjs:4
          const rows = records.map((r) => `${r.name.padEnd(12)} ${r.qty}`);
                               ^

        TypeError: Cannot read properties of undefined (reading 'map')
            at formatReport (file:///work/src/report.mjs:4:24)
            at main (file:///work/src/cli.mjs:8:15)

        A file with no data rows (empty, blank lines only, or just the header) must print "No records." and
        exit 0. Find the cause and fix it; keep everything else working.'''),
    files={
        "package.json": '{ "name": "report", "type": "module" }\n',
        "src/loader.mjs": d('''\
            // parseRecords(text) -> array of {name, qty} from CSV text with a "name,qty" header line.
            export function parseRecords(text) {
              const lines = text.split(/\\r?\\n/).filter((l) => l.trim() !== "");
              if (lines.length < 2) return;   // nothing but a header
              const header = lines[0].split(",").map((h) => h.trim());
              return lines.slice(1).map((line) => {
                const cells = line.split(",");
                const rec = Object.fromEntries(header.map((h, i) => [h, (cells[i] ?? "").trim()]));
                return { name: rec.name, qty: Number(rec.qty) };
              });
            }
            '''),
        "src/report.mjs": d('''\
            export function formatReport(records) {
              if (records.length === 0) return "No records.";
              const total = records.reduce((s, r) => s + r.qty, 0);
              const rows = records.map((r) => `${r.name.padEnd(12)} ${r.qty}`);
              return [...rows, `${"TOTAL".padEnd(12)} ${total}`].join("\\n");
            }
            '''),
        "src/cli.mjs": d('''\
            import { readFileSync } from "node:fs";
            import { parseRecords } from "./loader.mjs";
            import { formatReport } from "./report.mjs";

            export function main(path) {
              const text = readFileSync(path, "utf8");
              const records = parseRecords(text);
              const out = formatReport(records);
              console.log(out);
              return 0;
            }

            main(process.argv[2]);
            '''),
        "data/sample.csv": "name,qty\napples,3\npears,5\n",
        "data/empty.csv": "",
        "tests/report.test.mjs": d('''\
            import { test } from "node:test";
            import assert from "node:assert/strict";
            import { parseRecords } from "../src/loader.mjs";
            import { formatReport } from "../src/report.mjs";

            test("sample", () => {
              const recs = parseRecords("name,qty\\napples,3\\npears,5\\n");
              assert.deepEqual(recs, [{ name: "apples", qty: 3 }, { name: "pears", qty: 5 }]);
              assert.equal(formatReport(recs), "apples       3\\npears        5\\nTOTAL        8");
            });
            '''),
    },
    hidden={
        "_hidden/report.test.mjs": d('''\
            import { test } from "node:test";
            import assert from "node:assert/strict";
            import { spawnSync } from "node:child_process";
            import { writeFileSync, mkdtempSync } from "node:fs";
            import { tmpdir } from "node:os";
            import { join } from "node:path";
            import { parseRecords } from "../src/loader.mjs";
            import { formatReport } from "../src/report.mjs";

            test("empty inputs", () => {
              for (const t of ["", "\\n\\n  \\n", "name,qty", "name,qty\\r\\n\\r\\n"]) {
                assert.deepEqual(parseRecords(t), [], JSON.stringify(t));
                assert.equal(formatReport(parseRecords(t)), "No records.");
              }
            });

            test("crlf and data", () => {
              assert.deepEqual(parseRecords("name,qty\\r\\nx,1\\r\\n"), [{ name: "x", qty: 1 }]);
            });

            test("cli", () => {
              const dir = mkdtempSync(join(tmpdir(), "rep-"));
              const f = join(dir, "h.csv");
              writeFileSync(f, "name,qty\\n");
              const p = spawnSync(process.execPath, ["src/cli.mjs", f], { encoding: "utf8" });
              assert.equal(p.status, 0, p.stderr);
              assert.equal(p.stdout.trim(), "No records.");
              const q = spawnSync(process.execPath, ["src/cli.mjs", "data/sample.csv"], { encoding: "utf8" });
              assert.equal(q.stdout.trim(), "apples       3\\npears        5\\nTOTAL        8");
            });
            '''),
    },
    solution={
        "src/loader.mjs": d('''\
            export function parseRecords(text) {
              const lines = text.split(/\\r?\\n/).filter((l) => l.trim() !== "");
              if (lines.length < 2) return [];
              const header = lines[0].split(",").map((h) => h.trim());
              return lines.slice(1).map((line) => {
                const cells = line.split(",");
                const rec = Object.fromEntries(header.map((h, i) => [h, (cells[i] ?? "").trim()]));
                return { name: rec.name, qty: Number(rec.qty) };
              });
            }
            '''),
    },
)

# 17. implement to spec (TypeScript) -----------------------------------------------------------------------------
task(
    id="ts-impl-duration", lang="ts", kind="implement",
    prompt="Implement parseDuration and formatDuration in src/duration.ts as documented there. The tests run with "
           "`node --test` (Node runs the .ts files itself).",
    files={
        "package.json": '{ "name": "duration", "type": "module" }\n',
        "src/duration.ts": d('''\
            /**
             * parseDuration("1h30m") -> 5400000 (milliseconds).
             * A duration is one or more parts "<number><unit>", optionally separated by spaces. Units: ms, s, m,
             * h, d. The number may have a fractional part ("1.5h"). Parts may come in any order and are summed.
             * Anything else (empty string, unknown unit, a number without unit, negative numbers, stray
             * characters) throws an Error. The result is rounded to a whole number of milliseconds.
             */
            export function parseDuration(text: string): number {
              throw new Error("not implemented");
            }

            /**
             * formatDuration(5400000) -> "1h 30m". Uses d, h, m, s, ms from largest to smallest, leaves out zero
             * parts and joins with single spaces; 0 -> "0ms". Negative or non-integer input throws a RangeError.
             */
            export function formatDuration(ms: number): string {
              throw new Error("not implemented");
            }
            '''),
        "tests/duration.test.ts": d('''\
            import { test } from "node:test";
            import assert from "node:assert/strict";
            import { parseDuration, formatDuration } from "../src/duration.ts";

            test("parse", () => {
              assert.equal(parseDuration("1h30m"), 5_400_000);
            });

            test("format", () => {
              assert.equal(formatDuration(5_400_000), "1h 30m");
            });
            '''),
    },
    hidden={
        "_hidden/duration.test.ts": d('''\
            import { test } from "node:test";
            import assert from "node:assert/strict";
            import { parseDuration as p, formatDuration as f } from "../src/duration.ts";

            test("parse", () => {
              assert.equal(p("500ms"), 500);
              assert.equal(p("2m"), 120_000);
              assert.equal(p("1m500ms"), 60_500);
              assert.equal(p("1.5h"), 5_400_000);
              assert.equal(p("1d 2h 3m 4s 5ms"), 93_784_005);
              assert.equal(p("30m 1h"), 5_400_000);
              assert.equal(p("0.0015s"), 2);
              for (const bad of ["", "  ", "5", "1x", "h", "-1h", "1h-", "1h30", "1 h", "abc", "1h,2m"]) {
                assert.throws(() => p(bad), Error, JSON.stringify(bad));
              }
            });

            test("format", () => {
              assert.equal(f(0), "0ms");
              assert.equal(f(500), "500ms");
              assert.equal(f(93_784_005), "1d 2h 3m 4s 5ms");
              assert.equal(f(86_400_000), "1d");
              assert.equal(f(60_001), "1m 1ms");
              assert.throws(() => f(-1), RangeError);
              assert.throws(() => f(1.5), RangeError);
              for (const ms of [1, 999, 61_000, 3_600_000, 123_456_789]) assert.equal(p(f(ms)), ms);
            });
            '''),
    },
    solution={
        "src/duration.ts": d('''\
            const UNITS: Record<string, number> = { d: 86_400_000, h: 3_600_000, m: 60_000, s: 1000, ms: 1 };

            export function parseDuration(text: string): number {
              const s = text.trim();
              if (!/^(\\d+(\\.\\d+)?(ms|s|m|h|d)\\s*)+$/.test(s)) throw new Error(`bad duration ${JSON.stringify(text)}`);
              let total = 0;
              for (const m of s.matchAll(/(\\d+(?:\\.\\d+)?)(ms|s|m|h|d)/g)) total += Number(m[1]) * UNITS[m[2]];
              return Math.round(total);
            }

            export function formatDuration(ms: number): string {
              if (!Number.isInteger(ms) || ms < 0) throw new RangeError(`bad ms ${ms}`);
              if (ms === 0) return "0ms";
              const parts: string[] = [];
              for (const [u, size] of Object.entries(UNITS)) {
                const n = Math.floor(ms / size);
                if (n) parts.push(`${n}${u}`);
                ms -= n * size;
              }
              return parts.join(" ");
            }
            '''),
    },
)

# 18. refactor without breaking tests (TypeScript) ---------------------------------------------------------------
task(
    id="ts-refactor-pricing", lang="ts", kind="refactor",
    prompt=d('''\
        src/pricing.ts decides everything with switch statements over the plan code. Refactor it to a single
        exported table `PLANS: Record<PlanCode, Plan>` (with a `Plan` type you define, holding each plan's monthly
        price, seat limit and features) and make monthlyPrice, seatLimit and hasFeature read from it. No `switch`
        may remain in the file. The public behaviour (including the error for an unknown code) must not change.'''),
    files={
        "package.json": '{ "name": "pricing", "type": "module" }\n',
        "src/pricing.ts": d('''\
            export type PlanCode = "free" | "pro" | "team" | "enterprise";

            export function monthlyPrice(code: PlanCode, seats: number): number {
              switch (code) {
                case "free":
                  return 0;
                case "pro":
                  return 12 * seats;
                case "team":
                  return seats <= 10 ? 99 : 99 + (seats - 10) * 8;
                case "enterprise":
                  return 2000;
                default:
                  throw new Error(`unknown plan: ${code}`);
              }
            }

            export function seatLimit(code: PlanCode): number {
              switch (code) {
                case "free":
                  return 1;
                case "pro":
                  return 5;
                case "team":
                  return 50;
                case "enterprise":
                  return Infinity;
                default:
                  throw new Error(`unknown plan: ${code}`);
              }
            }

            export function hasFeature(code: PlanCode, feature: string): boolean {
              switch (code) {
                case "free":
                  return feature === "export";
                case "pro":
                  return ["export", "api"].includes(feature);
                case "team":
                  return ["export", "api", "sso"].includes(feature);
                case "enterprise":
                  return ["export", "api", "sso", "audit"].includes(feature);
                default:
                  throw new Error(`unknown plan: ${code}`);
              }
            }
            '''),
        "tests/pricing.test.ts": d('''\
            import { test } from "node:test";
            import assert from "node:assert/strict";
            import { monthlyPrice, seatLimit, hasFeature } from "../src/pricing.ts";

            test("prices", () => {
              assert.equal(monthlyPrice("free", 1), 0);
              assert.equal(monthlyPrice("pro", 3), 36);
              assert.equal(monthlyPrice("team", 12), 115);
              assert.equal(monthlyPrice("enterprise", 400), 2000);
            });

            test("limits and features", () => {
              assert.equal(seatLimit("team"), 50);
              assert.equal(hasFeature("pro", "sso"), false);
              assert.equal(hasFeature("enterprise", "audit"), true);
            });
            '''),
    },
    hidden={
        "_hidden/pricing.test.ts": d('''\
            import { test } from "node:test";
            import assert from "node:assert/strict";
            import { readFileSync } from "node:fs";
            import * as P from "../src/pricing.ts";

            test("table", () => {
              assert.deepEqual(Object.keys(P.PLANS).sort(), ["enterprise", "free", "pro", "team"]);
              const src = readFileSync(new URL("../src/pricing.ts", import.meta.url), "utf8");
              assert.ok(!/\\bswitch\\s*\\(/.test(src), "switch left in pricing.ts");
            });

            test("behaviour", () => {
              assert.equal(P.monthlyPrice("team", 10), 99);
              assert.equal(P.monthlyPrice("team", 1), 99);
              assert.equal(P.monthlyPrice("pro", 0), 0);
              assert.equal(P.seatLimit("free"), 1);
              assert.equal(P.seatLimit("pro"), 5);
              assert.equal(P.seatLimit("enterprise"), Infinity);
              assert.equal(P.hasFeature("free", "export"), true);
              assert.equal(P.hasFeature("free", "api"), false);
              assert.equal(P.hasFeature("team", "sso"), true);
              assert.equal(P.hasFeature("team", "audit"), false);
              for (const fn of [() => P.monthlyPrice("gold" as any, 1), () => P.seatLimit("gold" as any),
                                () => P.hasFeature("gold" as any, "api")]) {
                assert.throws(fn, { message: "unknown plan: gold" });
              }
              assert.throws(() => P.seatLimit("toString" as any), { message: "unknown plan: toString" });
            });
            '''),
    },
    solution={
        "src/pricing.ts": d('''\
            export type PlanCode = "free" | "pro" | "team" | "enterprise";

            export type Plan = { price: (seats: number) => number; seats: number; features: string[] };

            export const PLANS: Record<PlanCode, Plan> = {
              free: { price: () => 0, seats: 1, features: ["export"] },
              pro: { price: (s) => 12 * s, seats: 5, features: ["export", "api"] },
              team: { price: (s) => (s <= 10 ? 99 : 99 + (s - 10) * 8), seats: 50, features: ["export", "api", "sso"] },
              enterprise: { price: () => 2000, seats: Infinity, features: ["export", "api", "sso", "audit"] },
            };

            function plan(code: PlanCode): Plan {
              if (!Object.hasOwn(PLANS, code)) throw new Error(`unknown plan: ${code}`);
              return PLANS[code];
            }

            export function monthlyPrice(code: PlanCode, seats: number): number {
              return plan(code).price(seats);
            }

            export function seatLimit(code: PlanCode): number {
              return plan(code).seats;
            }

            export function hasFeature(code: PlanCode, feature: string): boolean {
              return plan(code).features.includes(feature);
            }
            '''),
    },
)

# 19. a feature across three files -------------------------------------------------------------------------------
task(
    id="js-multi-paging", lang="js", kind="multi-file",
    prompt=d('''\
        Add pagination to the items API (src/api.mjs -> src/service.mjs -> src/repo.mjs):
        - query parameters `limit` (default 20, 1..100) and `offset` (default 0, >= 0), both whole numbers written
          as decimal digits; anything else gives status 400 with body {error: "<message>"}.
        - the 200 body becomes {items, total, limit, offset}, where total is the number of matching items before
          paging. The existing `q` filter applies before paging.
        - the slicing must happen in the repository: repo.findItems(filter, {limit, offset}) returns
          {items, total}; service.listItems(q, {limit, offset}) passes them through.'''),
    files={
        "package.json": '{ "name": "paging", "type": "module" }\n',
        "src/repo.mjs": d('''\
            const ITEMS = Array.from({ length: 57 }, (_, i) => ({ id: i + 1, name: `item ${i + 1}` }));

            // findItems(filter) -> the items whose name contains filter (all items for an empty filter)
            export function findItems(filter) {
              return ITEMS.filter((it) => !filter || it.name.includes(filter));
            }
            '''),
        "src/service.mjs": d('''\
            import { findItems } from "./repo.mjs";

            export function listItems(q) {
              return findItems(q ? q.trim() : "");
            }
            '''),
        "src/api.mjs": d('''\
            import { listItems } from "./service.mjs";

            // handle(query) -> {status, body}; query is an object of strings (the parsed query string)
            export function handle(query) {
              const items = listItems(query.q);
              return { status: 200, body: { items } };
            }
            '''),
        "tests/api.test.mjs": d('''\
            import { test } from "node:test";
            import assert from "node:assert/strict";
            import { handle } from "../src/api.mjs";

            test("filter", () => {
              const r = handle({ q: "item 5" });
              assert.equal(r.status, 200);
              assert.deepEqual(r.body.items.map((i) => i.id), [5, 50, 51, 52, 53, 54, 55, 56, 57]);
            });
            '''),
    },
    hidden={
        "_hidden/api.test.mjs": d('''\
            import { test } from "node:test";
            import assert from "node:assert/strict";
            import { handle } from "../src/api.mjs";
            import { listItems } from "../src/service.mjs";
            import { findItems } from "../src/repo.mjs";

            test("defaults", () => {
              const r = handle({});
              assert.equal(r.status, 200);
              assert.equal(r.body.total, 57);
              assert.equal(r.body.limit, 20);
              assert.equal(r.body.offset, 0);
              assert.deepEqual(r.body.items.map((i) => i.id), Array.from({ length: 20 }, (_, i) => i + 1));
            });

            test("paging with filter", () => {
              const r = handle({ q: "item 5", limit: "3", offset: "2" });
              assert.deepEqual(r.body, { items: [51, 52, 53].map((id) => ({ id, name: `item ${id}` })), total: 9,
                                         limit: 3, offset: 2 });
              assert.deepEqual(handle({ offset: "56", limit: "100" }).body.items.map((i) => i.id), [57]);
              assert.deepEqual(handle({ offset: "100" }).body.items, []);
            });

            test("validation", () => {
              for (const q of [{ limit: "0" }, { limit: "101" }, { limit: "-1" }, { limit: "abc" }, { limit: "2.5" },
                               { offset: "-1" }, { offset: "1e2" }, { limit: "" }, { offset: " 1" }]) {
                const r = handle(q);
                assert.equal(r.status, 400, JSON.stringify(q));
                assert.equal(typeof r.body.error, "string");
              }
              assert.equal(handle({ limit: "100" }).status, 200);
            });

            test("layers", () => {
              assert.deepEqual(findItems("item 1", { limit: 2, offset: 1 }),
                               { items: [{ id: 10, name: "item 10" }, { id: 11, name: "item 11" }], total: 11 });
              assert.equal(listItems(" item 1 ", { limit: 5, offset: 0 }).total, 11);
            });
            '''),
    },
    solution={
        "src/repo.mjs": d('''\
            const ITEMS = Array.from({ length: 57 }, (_, i) => ({ id: i + 1, name: `item ${i + 1}` }));

            export function findItems(filter, { limit, offset }) {
              const all = ITEMS.filter((it) => !filter || it.name.includes(filter));
              return { items: all.slice(offset, offset + limit), total: all.length };
            }
            '''),
        "src/service.mjs": d('''\
            import { findItems } from "./repo.mjs";

            export function listItems(q, page) {
              return findItems(q ? q.trim() : "", page);
            }
            '''),
        "src/api.mjs": d('''\
            import { listItems } from "./service.mjs";

            function int(v, dflt, min, max, name) {
              if (v === undefined) return dflt;
              if (!/^\\d+$/.test(v)) throw new Error(`${name} must be a whole number`);
              const n = Number(v);
              if (n < min || n > max) throw new Error(`${name} out of range`);
              return n;
            }

            export function handle(query) {
              let limit, offset;
              try {
                limit = int(query.limit, 20, 1, 100, "limit");
                offset = int(query.offset, 0, 0, Infinity, "offset");
              } catch (e) {
                return { status: 400, body: { error: e.message } };
              }
              const { items, total } = listItems(query.q, { limit, offset });
              return { status: 200, body: { items, total, limit, offset } };
            }
            '''),
    },
)

# 20. fix a failing test (TypeScript, Russian) -------------------------------------------------------------------
task(
    id="ts-fix-arrays", lang="ts", kind="fix-test", ru=True,
    prompt="Тесты в tests/ падают. Исправь src/arrays.ts так, чтобы функции работали как написано в комментариях "
           "к ним. Тесты не меняй.",
    files={
        "package.json": '{ "name": "arrays", "type": "module" }\n',
        "src/arrays.ts": d('''\
            // chunk([1,2,3,4,5], 2) -> [[1,2],[3,4],[5]]; size must be a positive integer, else RangeError.
            export function chunk<T>(arr: readonly T[], size: number): T[][] {
              const out: T[][] = [];
              for (let i = 0; i + size < arr.length; i += size) {
                out.push(arr.slice(i, i + size));
              }
              return out;
            }

            // zip([1,2,3], ["a","b"]) -> [[1,"a"],[2,"b"]]: as long as the shorter array.
            export function zip<A, B>(a: readonly A[], b: readonly B[]): [A, B][] {
              return a.map((x, i) => [x, b[i]]);
            }

            // windows([1,2,3,4], 3) -> [[1,2,3],[2,3,4]]: every run of `size` consecutive items; [] when the
            // array is shorter than size; size must be a positive integer, else RangeError.
            export function windows<T>(arr: readonly T[], size: number): T[][] {
              const out: T[][] = [];
              for (let i = 0; i <= arr.length - size; i++) out.push(arr.slice(i, i + size));
              return out;
            }
            '''),
        "tests/arrays.test.ts": d('''\
            import { test } from "node:test";
            import assert from "node:assert/strict";
            import { chunk, zip, windows } from "../src/arrays.ts";

            test("chunk", () => {
              assert.deepEqual(chunk([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]]);
            });

            test("zip", () => {
              assert.deepEqual(zip([1, 2, 3], ["a", "b"]), [[1, "a"], [2, "b"]]);
            });

            test("windows", () => {
              assert.deepEqual(windows([1, 2, 3, 4], 3), [[1, 2, 3], [2, 3, 4]]);
            });
            '''),
    },
    hidden={
        "_hidden/arrays.test.ts": d('''\
            import { test } from "node:test";
            import assert from "node:assert/strict";
            import { chunk, zip, windows } from "../src/arrays.ts";

            test("chunk", () => {
              assert.deepEqual(chunk([1, 2, 3, 4], 2), [[1, 2], [3, 4]]);
              assert.deepEqual(chunk([1, 2, 3], 5), [[1, 2, 3]]);
              assert.deepEqual(chunk([], 3), []);
              assert.deepEqual(chunk([1], 1), [[1]]);
              for (const bad of [0, -1, 1.5, NaN]) assert.throws(() => chunk([1, 2], bad), RangeError);
            });

            test("zip", () => {
              assert.deepEqual(zip([1], ["a", "b", "c"]), [[1, "a"]]);
              assert.deepEqual(zip([], [1]), []);
              assert.deepEqual(zip([1, 2], [undefined, null]), [[1, undefined], [2, null]]);
            });

            test("windows", () => {
              assert.deepEqual(windows([1, 2], 3), []);
              assert.deepEqual(windows([1, 2, 3], 1), [[1], [2], [3]]);
              assert.deepEqual(windows([1, 2, 3], 3), [[1, 2, 3]]);
              for (const bad of [0, -2, 2.5]) assert.throws(() => windows([1, 2, 3], bad), RangeError);
            });
            '''),
    },
    solution={
        "src/arrays.ts": d('''\
            function check(size: number): void {
              if (!Number.isInteger(size) || size < 1) throw new RangeError(`bad size ${size}`);
            }

            export function chunk<T>(arr: readonly T[], size: number): T[][] {
              check(size);
              const out: T[][] = [];
              for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
              return out;
            }

            export function zip<A, B>(a: readonly A[], b: readonly B[]): [A, B][] {
              const n = Math.min(a.length, b.length);
              const out: [A, B][] = [];
              for (let i = 0; i < n; i++) out.push([a[i], b[i]]);
              return out;
            }

            export function windows<T>(arr: readonly T[], size: number): T[][] {
              check(size);
              const out: T[][] = [];
              for (let i = 0; i <= arr.length - size; i++) out.push(arr.slice(i, i + size));
              return out;
            }
            '''),
    },
)
