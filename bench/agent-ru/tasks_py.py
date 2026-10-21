"""bench/agent-ru/tasks_py.py - the Python tasks of the agentic benchmark.

Each task is a small repository (`files`), the prompt the agent gets, the hidden tests that score it (`hidden`, put
into _hidden/ after the agent has finished, next to the original visible tests) and a reference solution (`solution`,
only for selftest.py: the files it replaces).  Visible tests: `python -m unittest discover -s tests -v`; hidden tests:
`python -m unittest discover -s _hidden -v`.
"""
from textwrap import dedent as d

TASKS = []


def task(**kw):
    kw.setdefault("lang", "python")
    kw.setdefault("ru", False)
    TASKS.append(kw)


# 1. fix a failing test -------------------------------------------------------------------------------------------
task(
    id="py-fix-slugify", kind="fix-test",
    prompt="The test suite of this repository fails (run the tests to see it). Fix the code so that the tests pass. "
           "Do not change the tests.",
    files={
        "text_utils.py": d('''\
            import re
            import unicodedata


            def slugify(text, sep="-"):
                """Turn text into a URL slug: lowercase ASCII letters and digits joined by `sep`.

                Accents are dropped (e with an acute accent becomes e), every run of other characters becomes
                one separator, and there is no separator at either end.
                """
                text = unicodedata.normalize("NFKD", text)
                text = text.encode("ascii", "ignore").decode()
                text = text.lower()
                text = re.sub(r"[^a-z0-9]", sep, text)
                return text
            '''),
        "tests/test_text_utils.py": d('''\
            import unittest

            from text_utils import slugify


            class SlugifyTest(unittest.TestCase):
                def test_simple(self):
                    self.assertEqual(slugify("hello"), "hello")

                def test_punctuation(self):
                    self.assertEqual(slugify("Hello, World!"), "hello-world")


            if __name__ == "__main__":
                unittest.main()
            '''),
    },
    hidden={
        "_hidden/test_slugify_hidden.py": d('''\
            import unittest

            from text_utils import slugify


            class Hidden(unittest.TestCase):
                def test_cases(self):
                    self.assertEqual(slugify("Hello, World!"), "hello-world")
                    self.assertEqual(slugify("  Cr\\u00e8me  br\\u00fbl\\u00e9e  "), "creme-brulee")
                    self.assertEqual(slugify("a--b"), "a-b")
                    self.assertEqual(slugify("---"), "")
                    self.assertEqual(slugify("\\u00dcn\\u00efc\\u00f6d\\u00e9 2024"), "unicode-2024")
                    self.assertEqual(slugify("One two  three", sep="_"), "one_two_three")
                    self.assertEqual(slugify("x"), "x")
            '''),
    },
    solution={
        "text_utils.py": d('''\
            import re
            import unicodedata


            def slugify(text, sep="-"):
                text = unicodedata.normalize("NFKD", text)
                text = text.encode("ascii", "ignore").decode()
                text = text.lower()
                text = re.sub(r"[^a-z0-9]+", sep, text)
                return text.strip(sep)
            '''),
    },
)

# 2. implement to spec (Russian) ---------------------------------------------------------------------------------
task(
    id="py-impl-roman", kind="implement", ru=True,
    prompt="В файле roman.py две функции-заглушки. Реализуй их точно по описанию в докстрингах. "
           "Существующие тесты должны проходить.",
    files={
        "roman.py": d('''\
            """Римские числа."""


            def to_roman(n):
                """Целое n от 1 до 3999 -> римская запись заглавными буквами (4 -> "IV", 1994 -> "MCMXCIV").

                n вне диапазона -> ValueError; n не int (в том числе bool) -> TypeError.
                """
                raise NotImplementedError


            def from_roman(s):
                """Римская запись -> int.  Принимается только каноническая запись заглавными буквами, то есть ровно
                та строка, которую вернула бы to_roman: "IIII", "VX", "IC", "MMMM", "iv", "" и любые другие
                неканонические строки -> ValueError.  s не str -> TypeError.
                """
                raise NotImplementedError
            '''),
        "tests/test_roman.py": d('''\
            import unittest

            from roman import from_roman, to_roman


            class RomanTest(unittest.TestCase):
                def test_to(self):
                    self.assertEqual(to_roman(4), "IV")
                    self.assertEqual(to_roman(1994), "MCMXCIV")

                def test_from(self):
                    self.assertEqual(from_roman("XLII"), 42)
            '''),
    },
    hidden={
        "_hidden/test_roman_hidden.py": d('''\
            import unittest

            from roman import from_roman, to_roman


            class Hidden(unittest.TestCase):
                def test_round_trip(self):
                    for n in range(1, 4000):
                        self.assertEqual(from_roman(to_roman(n)), n)
                    self.assertEqual(to_roman(3999), "MMMCMXCIX")
                    self.assertEqual(to_roman(1), "I")

                def test_range(self):
                    for bad in (0, -1, 4000):
                        with self.assertRaises(ValueError):
                            to_roman(bad)
                    for bad in (1.0, "5", True, None):
                        with self.assertRaises(TypeError):
                            to_roman(bad)

                def test_invalid(self):
                    for bad in ("IIII", "VX", "IC", "MMMM", "iv", "", "XM", "VV", "IIV", "ABC", " X"):
                        with self.assertRaises(ValueError, msg=bad):
                            from_roman(bad)
                    with self.assertRaises(TypeError):
                        from_roman(5)
            '''),
    },
    solution={
        "roman.py": d('''\
            VALUES = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
                      (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


            def to_roman(n):
                if not isinstance(n, int) or isinstance(n, bool):
                    raise TypeError("int expected")
                if not 1 <= n <= 3999:
                    raise ValueError("out of range")
                out = []
                for v, s in VALUES:
                    while n >= v:
                        out.append(s)
                        n -= v
                return "".join(out)


            _TABLE = {to_roman(i): i for i in range(1, 4000)}


            def from_roman(s):
                if not isinstance(s, str):
                    raise TypeError("str expected")
                if s not in _TABLE:
                    raise ValueError(s)
                return _TABLE[s]
            '''),
    },
)

# 3. refactor without breaking tests -----------------------------------------------------------------------------
_ORDERS_TESTS = d('''\
    import unittest

    import orders

    ITEMS = [
        {"name": "pen", "price": 1.5, "qty": 4},
        {"name": "novel", "price": 12.0, "qty": 1, "category": "books"},
        {"name": "lamp", "price": 30.0, "qty": 1},
    ]


    class OrdersTest(unittest.TestCase):
        def test_total(self):
            self.assertEqual(orders.invoice_total(ITEMS, {}), 47.4)
            self.assertEqual(orders.invoice_total(ITEMS, {"vip": True}), 42.66)

        def test_preview(self):
            self.assertEqual(orders.cart_preview(ITEMS, {}), ["pen: 6.00", "novel: 11.40", "lamp: 30.00"])

        def test_most_expensive(self):
            self.assertEqual(orders.most_expensive_line(ITEMS, {"vip": True}), ("lamp", 27.0))
            self.assertIsNone(orders.most_expensive_line([], {}))
    ''')
task(
    id="py-refactor-orders", kind="refactor",
    prompt="orders.py repeats the same per-line price calculation in three functions. Refactor it: add a public "
           "function `line_total(item, customer)` that returns the rounded (2 decimals) price of one line, and make "
           "invoice_total, cart_preview and most_expensive_line use it, so the discount rules are written only once. "
           "The behaviour must not change and the tests must keep passing.",
    files={
        "orders.py": d('''\
            """Order totals.  VIP customers get 10% off every line, books get 5% off (both can apply)."""


            def invoice_total(items, customer):
                total = 0
                for it in items:
                    price = it["price"] * it["qty"]
                    if customer.get("vip"):
                        price = price * 0.9
                    if it.get("category") == "books":
                        price = price * 0.95
                    total += round(price, 2)
                return round(total, 2)


            def cart_preview(items, customer):
                lines = []
                for it in items:
                    price = it["price"] * it["qty"]
                    if customer.get("vip"):
                        price = price * 0.9
                    if it.get("category") == "books":
                        price = price * 0.95
                    lines.append(f'{it["name"]}: {round(price, 2):.2f}')
                return lines


            def most_expensive_line(items, customer):
                best = None
                for it in items:
                    price = it["price"] * it["qty"]
                    if customer.get("vip"):
                        price = price * 0.9
                    if it.get("category") == "books":
                        price = price * 0.95
                    if best is None or round(price, 2) > best[1]:
                        best = (it["name"], round(price, 2))
                return best
            '''),
        "tests/test_orders.py": _ORDERS_TESTS,
    },
    hidden={
        "_hidden/test_orders_hidden.py": d('''\
            import inspect
            import unittest
            from pathlib import Path

            import orders


            class Hidden(unittest.TestCase):
                def test_line_total(self):
                    self.assertEqual(orders.line_total({"name": "a", "price": 10.0, "qty": 3}, {}), 30.0)
                    self.assertEqual(orders.line_total({"name": "b", "price": 9.99, "qty": 1, "category": "books"},
                                                       {"vip": True}), 8.54)
                    self.assertEqual(list(inspect.signature(orders.line_total).parameters), ["item", "customer"])

                def test_written_once(self):
                    src = Path(orders.__file__).read_text(encoding="utf-8")
                    self.assertEqual(src.count("0.9"), 2, "the VIP and book factors (0.9, 0.95) must appear once")
                    self.assertEqual(src.count("0.95"), 1)
                    for fn in (orders.invoice_total, orders.cart_preview, orders.most_expensive_line):
                        self.assertIn("line_total", inspect.getsource(fn))

                def test_behaviour(self):
                    items = [{"name": "x", "price": 0.1, "qty": 3, "category": "books"},
                             {"name": "y", "price": 0.1, "qty": 3}]
                    self.assertEqual(orders.invoice_total(items, {"vip": True}), 0.53)
                    self.assertEqual(orders.cart_preview(items, {"vip": True}), ["x: 0.26", "y: 0.27"])
                    self.assertEqual(orders.most_expensive_line(items, {}), ("y", 0.3))
            '''),
    },
    solution={
        "orders.py": d('''\
            def line_total(item, customer):
                price = item["price"] * item["qty"]
                if customer.get("vip"):
                    price = price * 0.9
                if item.get("category") == "books":
                    price = price * 0.95
                return round(price, 2)


            def invoice_total(items, customer):
                return round(sum(line_total(it, customer) for it in items), 2)


            def cart_preview(items, customer):
                return [f'{it["name"]}: {line_total(it, customer):.2f}' for it in items]


            def most_expensive_line(items, customer):
                best = None
                for it in items:
                    p = line_total(it, customer)
                    if best is None or p > best[1]:
                        best = (it["name"], p)
                return best
            '''),
    },
)

# 4. bug from a stack trace, across modules ----------------------------------------------------------------------
task(
    id="py-trace-report", kind="stack-trace",
    prompt=d('''\
        Users get this crash when they build the daily sales report:

        Traceback (most recent call last):
          File "make_report.py", line 8, in <module>
            for row in build_report(load_rows("sales.csv")):
          File "sales/report.py", line 9, in build_report
            "avg": mean(values),
          File "sales/stats.py", line 3, in mean
            return sum(xs) / len(xs)
        ZeroDivisionError: division by zero

        It happens when a day has only refunds (negative amounts). Refunds are not sales: a day without sales must
        not appear in the report at all. Find the real cause and fix it.'''),
    files={
        "make_report.py": d('''\
            import sys

            from sales.io import load_rows
            from sales.report import build_report

            if __name__ == "__main__":
                path = sys.argv[1] if len(sys.argv) > 1 else "sales.csv"
                for row in build_report(load_rows("sales.csv")):
                    print(row)
            '''),
        "sales/__init__.py": "",
        "sales/io.py": d('''\
            import csv


            def load_rows(path):
                with open(path, newline="", encoding="utf-8") as f:
                    return [{"day": r["day"], "amount": float(r["amount"])} for r in csv.DictReader(f)]
            '''),
        "sales/stats.py": d('''\
            def mean(xs):
                """Arithmetic mean of a non-empty sequence."""
                return sum(xs) / len(xs)
            '''),
        "sales/grouping.py": d('''\
            def sales_by_day(rows):
                """{day: [amounts of the sales of that day]}; refunds (amount < 0) are not sales."""
                out = {}
                for r in rows:
                    day = out.setdefault(r["day"], [])
                    if r["amount"] > 0:
                        day.append(r["amount"])
                return out
            '''),
        "sales/report.py": d('''\
            from sales.grouping import sales_by_day
            from sales.stats import mean


            def build_report(rows):
                out = []
                for day, values in sorted(sales_by_day(rows).items()):
                    out.append({"day": day, "count": len(values), "total": round(sum(values), 2),
                                "avg": mean(values),
                                })
                return out
            '''),
        "sales.csv": "day,amount\n2024-05-01,10.0\n2024-05-01,30.0\n2024-05-02,-5.0\n2024-05-03,7.5\n",
        "tests/test_report.py": d('''\
            import unittest

            from sales.report import build_report


            class ReportTest(unittest.TestCase):
                def test_basic(self):
                    rows = [{"day": "d1", "amount": 10.0}, {"day": "d1", "amount": 20.0}]
                    self.assertEqual(build_report(rows), [{"day": "d1", "count": 2, "total": 30.0, "avg": 15.0}])
            '''),
    },
    hidden={
        "_hidden/test_report_hidden.py": d('''\
            import unittest

            from sales.grouping import sales_by_day
            from sales.report import build_report


            class Hidden(unittest.TestCase):
                def test_refund_only_day(self):
                    rows = [{"day": "d1", "amount": 10.0}, {"day": "d2", "amount": -5.0},
                            {"day": "d3", "amount": 4.0}, {"day": "d3", "amount": -4.0}, {"day": "d3", "amount": 2.0}]
                    self.assertEqual(build_report(rows), [
                        {"day": "d1", "count": 1, "total": 10.0, "avg": 10.0},
                        {"day": "d3", "count": 2, "total": 6.0, "avg": 3.0}])

                def test_grouping(self):
                    self.assertEqual(sales_by_day([{"day": "a", "amount": -1.0}]), {})
                    self.assertEqual(build_report([]), [])
            '''),
    },
    solution={
        "sales/grouping.py": d('''\
            def sales_by_day(rows):
                out = {}
                for r in rows:
                    if r["amount"] > 0:
                        out.setdefault(r["day"], []).append(r["amount"])
                return out
            '''),
    },
)

# 5. add a CLI flag (Russian) ------------------------------------------------------------------------------------
task(
    id="py-cli-wordcount", kind="cli-flag", ru=True,
    prompt=d('''\
        Доработай CLI wordcount.py (выводит самые частые слова файла):
        1. Флаг `--min-length N`: не учитывать слова короче N символов (по умолчанию 1). Отрицательное N - ошибка
           разбора аргументов (как у argparse: код выхода 2).
        2. Флаг `--json`: вместо строк "слово<TAB>число" вывести одной строкой JSON-список объектов
           {"word": ..., "count": ...} в том же порядке; кириллицу не экранировать (ensure_ascii=False).
        Флаги работают вместе и с `--top`. Старое поведение без флагов не менять.'''),
    files={
        "wordcount.py": d('''\
            import argparse
            import collections
            import re
            import sys


            def count_words(text):
                return collections.Counter(re.findall(r"\\w+", text.lower()))


            def main(argv=None):
                p = argparse.ArgumentParser(description="Top words of a text file")
                p.add_argument("path")
                p.add_argument("--top", type=int, default=10)
                a = p.parse_args(argv)
                with open(a.path, encoding="utf-8") as f:
                    counts = count_words(f.read())
                for word, n in counts.most_common(a.top):
                    print(f"{word}\\t{n}")
                return 0


            if __name__ == "__main__":
                sys.exit(main())
            '''),
        "tests/test_wordcount.py": d('''\
            import contextlib
            import io
            import tempfile
            import unittest
            from pathlib import Path

            import wordcount


            class WordcountTest(unittest.TestCase):
                def test_top(self):
                    with tempfile.TemporaryDirectory() as d:
                        p = Path(d) / "t.txt"
                        p.write_text("b a b c b a", encoding="utf-8")
                        out = io.StringIO()
                        with contextlib.redirect_stdout(out):
                            wordcount.main([str(p), "--top", "2"])
                        self.assertEqual(out.getvalue(), "b\\t3\\na\\t2\\n")
            '''),
    },
    hidden={
        "_hidden/test_wordcount_hidden.py": d('''\
            import contextlib
            import io
            import json
            import subprocess
            import sys
            import tempfile
            import unittest
            from pathlib import Path

            import wordcount

            TEXT = "кот кот кот дом дом я я я я и окно окно"


            def run(*args):
                with tempfile.TemporaryDirectory() as d:
                    p = Path(d) / "t.txt"
                    p.write_text(TEXT, encoding="utf-8")
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        wordcount.main([str(p), *args])
                    return out.getvalue()


            class Hidden(unittest.TestCase):
                def test_plain(self):
                    self.assertEqual(run("--top", "2"), "я\\t4\\nкот\\t3\\n")

                def test_min_length(self):
                    self.assertEqual(run("--min-length", "3"), "кот\\t3\\nдом\\t2\\nокно\\t2\\n")

                def test_json(self):
                    out = run("--json", "--min-length", "4")
                    self.assertEqual(out.strip().count("\\n"), 0)
                    self.assertEqual(json.loads(out), [{"word": "окно", "count": 2}])
                    self.assertIn("окно", out)

                def test_json_top(self):
                    self.assertEqual(json.loads(run("--json", "--top", "1")), [{"word": "я", "count": 4}])

                def test_negative(self):
                    with tempfile.TemporaryDirectory() as d:
                        p = Path(d) / "t.txt"
                        p.write_text(TEXT, encoding="utf-8")
                        r = subprocess.run([sys.executable, "wordcount.py", str(p), "--min-length", "-1"],
                                           capture_output=True, text=True)
                        self.assertEqual(r.returncode, 2)
                        r = subprocess.run([sys.executable, "wordcount.py", str(p), "--json"],
                                           capture_output=True, encoding="utf-8")
                        self.assertEqual(r.returncode, 0)
                        self.assertEqual(json.loads(r.stdout)[0], {"word": "я", "count": 4})
            '''),
    },
    solution={
        "wordcount.py": d('''\
            import argparse
            import collections
            import json
            import re
            import sys


            def count_words(text, min_length=1):
                return collections.Counter(w for w in re.findall(r"\\w+", text.lower()) if len(w) >= min_length)


            def non_negative(s):
                n = int(s)
                if n < 0:
                    raise argparse.ArgumentTypeError("must be >= 0")
                return n


            def main(argv=None):
                p = argparse.ArgumentParser(description="Top words of a text file")
                p.add_argument("path")
                p.add_argument("--top", type=int, default=10)
                p.add_argument("--min-length", type=non_negative, default=1)
                p.add_argument("--json", action="store_true")
                a = p.parse_args(argv)
                with open(a.path, encoding="utf-8") as f:
                    counts = count_words(f.read(), a.min_length)
                top = counts.most_common(a.top)
                if a.json:
                    print(json.dumps([{"word": w, "count": n} for w, n in top], ensure_ascii=False))
                else:
                    for word, n in top:
                        print(f"{word}\\t{n}")
                return 0


            if __name__ == "__main__":
                if hasattr(sys.stdout, "reconfigure"):
                    sys.stdout.reconfigure(encoding="utf-8")
                sys.exit(main())
            '''),
    },
)

# 6. a feature across three files --------------------------------------------------------------------------------
task(
    id="py-multi-email", kind="multi-file",
    prompt=d('''\
        Add an `email` field to users, across models.py, storage.py and api.py:
        - `User` gets `email` (a str, or None for users saved before this change).
        - `api.create_user(name, age, email)` requires it and raises ValueError unless it has exactly one "@",
          a non-empty part before it, and a domain after it that contains a dot not at its start or end.
          Store it lowercased and stripped of surrounding spaces.
        - storage saves and loads the email; files written before this change (without "email") still load,
          with email None.
        Keep the existing behaviour and tests.'''),
    files={
        "models.py": d('''\
            from dataclasses import dataclass


            @dataclass
            class User:
                name: str
                age: int
            '''),
        "storage.py": d('''\
            import json

            from models import User


            def save(path, users):
                data = [{"name": u.name, "age": u.age} for u in users]
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)


            def load(path):
                with open(path, encoding="utf-8") as f:
                    return [User(name=r["name"], age=r["age"]) for r in json.load(f)]
            '''),
        "api.py": d('''\
            from models import User


            def create_user(name, age):
                name = name.strip()
                if not name:
                    raise ValueError("name is required")
                if not isinstance(age, int) or age < 0:
                    raise ValueError("age must be a non-negative int")
                return User(name=name, age=age)
            '''),
        "tests/test_users.py": d('''\
            import tempfile
            import unittest
            from pathlib import Path

            import storage
            from models import User


            class UsersTest(unittest.TestCase):
                def test_round_trip(self):
                    with tempfile.TemporaryDirectory() as d:
                        p = Path(d) / "u.json"
                        storage.save(p, [User("Ann", 30)] if "email" not in User.__dataclass_fields__
                                     else [User("Ann", 30, None)])
                        self.assertEqual(storage.load(p)[0].name, "Ann")
            '''),
    },
    hidden={
        "_hidden/test_users_hidden.py": d('''\
            import json
            import tempfile
            import unittest
            from pathlib import Path

            import api
            import storage
            from models import User


            class Hidden(unittest.TestCase):
                def test_create(self):
                    u = api.create_user(" Ann ", 30, "  Ann.Lee@Example.COM ")
                    self.assertEqual((u.name, u.age, u.email), ("Ann", 30, "ann.lee@example.com"))

                def test_invalid(self):
                    for bad in ("", "ann", "@x.com", "ann@", "ann@com", "ann@.com", "ann@x.", "a@b@c.com"):
                        with self.assertRaises(ValueError, msg=bad):
                            api.create_user("Ann", 1, bad)
                    with self.assertRaises(ValueError):
                        api.create_user("", 1, "a@b.co")
                    with self.assertRaises(TypeError):
                        api.create_user("Ann", 1)

                def test_storage(self):
                    with tempfile.TemporaryDirectory() as d:
                        p = Path(d) / "u.json"
                        storage.save(p, [api.create_user("Ann", 3, "a@b.co")])
                        self.assertEqual(json.loads(p.read_text(encoding="utf-8"))[0]["email"], "a@b.co")
                        self.assertEqual(storage.load(p)[0].email, "a@b.co")
                        p.write_text(json.dumps([{"name": "Old", "age": 9}]), encoding="utf-8")
                        old = storage.load(p)[0]
                        self.assertEqual((old.name, old.age, old.email), ("Old", 9, None))
                        self.assertEqual(User("X", 1, None).email, None)
            '''),
    },
    solution={
        "models.py": d('''\
            from dataclasses import dataclass


            @dataclass
            class User:
                name: str
                age: int
                email: str | None = None
            '''),
        "storage.py": d('''\
            import json

            from models import User


            def save(path, users):
                data = [{"name": u.name, "age": u.age, "email": u.email} for u in users]
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)


            def load(path):
                with open(path, encoding="utf-8") as f:
                    return [User(name=r["name"], age=r["age"], email=r.get("email")) for r in json.load(f)]
            '''),
        "api.py": d('''\
            from models import User


            def _valid_email(e):
                if e.count("@") != 1:
                    return False
                local, domain = e.split("@")
                return bool(local) and "." in domain and not domain.startswith(".") and not domain.endswith(".")


            def create_user(name, age, email):
                name = name.strip()
                if not name:
                    raise ValueError("name is required")
                if not isinstance(age, int) or age < 0:
                    raise ValueError("age must be a non-negative int")
                email = email.strip().lower()
                if not _valid_email(email):
                    raise ValueError("invalid email")
                return User(name=name, age=age, email=email)
            '''),
    },
)

# 7. fix a failing test ------------------------------------------------------------------------------------------
task(
    id="py-fix-lru", kind="fix-test",
    prompt="tests/test_lru.py fails. Fix lru.py so that the cache behaves as its docstring says. "
           "Do not edit the tests.",
    files={
        "lru.py": d('''\
            class LRUCache:
                """A least-recently-used cache of at most `capacity` entries.

                get() of a present key and put() (new or existing key) make that key the most recently used one.
                When a put() goes over capacity, the least recently used key is evicted.  `key in cache` and
                len(cache) do not change the order.
                """

                def __init__(self, capacity):
                    if capacity <= 0:
                        raise ValueError("capacity must be positive")
                    self.capacity = capacity
                    self._data = {}

                def get(self, key, default=None):
                    if key not in self._data:
                        return default
                    return self._data[key]

                def put(self, key, value):
                    self._data[key] = value
                    if len(self._data) > self.capacity:
                        oldest = next(iter(self._data))
                        del self._data[oldest]

                def __len__(self):
                    return len(self._data)

                def __contains__(self, key):
                    return key in self._data
            '''),
        "tests/test_lru.py": d('''\
            import unittest

            from lru import LRUCache


            class LRUTest(unittest.TestCase):
                def test_evicts_oldest(self):
                    c = LRUCache(2)
                    c.put("a", 1)
                    c.put("b", 2)
                    c.put("c", 3)
                    self.assertNotIn("a", c)

                def test_get_refreshes(self):
                    c = LRUCache(2)
                    c.put("a", 1)
                    c.put("b", 2)
                    self.assertEqual(c.get("a"), 1)
                    c.put("c", 3)
                    self.assertIn("a", c)
                    self.assertNotIn("b", c)
            '''),
    },
    hidden={
        "_hidden/test_lru_hidden.py": d('''\
            import unittest

            from lru import LRUCache


            class Hidden(unittest.TestCase):
                def test_put_existing_refreshes(self):
                    c = LRUCache(2)
                    c.put("a", 1)
                    c.put("b", 2)
                    c.put("a", 10)
                    c.put("c", 3)
                    self.assertEqual(c.get("a"), 10)
                    self.assertNotIn("b", c)
                    self.assertEqual(len(c), 2)

                def test_contains_does_not_refresh(self):
                    c = LRUCache(2)
                    c.put("a", 1)
                    c.put("b", 2)
                    self.assertIn("a", c)
                    c.put("c", 3)
                    self.assertNotIn("a", c)

                def test_missing_get(self):
                    c = LRUCache(1)
                    c.put("a", 1)
                    self.assertIsNone(c.get("zz"))
                    self.assertEqual(c.get("zz", 5), 5)
                    c.put("b", 2)
                    self.assertNotIn("a", c)
                    with self.assertRaises(ValueError):
                        LRUCache(0)

                def test_none_value(self):
                    c = LRUCache(2)
                    c.put("a", None)
                    c.put("b", 1)
                    self.assertIsNone(c.get("a", "d"))
                    c.put("c", 2)
                    self.assertIn("a", c)
            '''),
    },
    solution={
        "lru.py": d('''\
            class LRUCache:
                def __init__(self, capacity):
                    if capacity <= 0:
                        raise ValueError("capacity must be positive")
                    self.capacity = capacity
                    self._data = {}

                def get(self, key, default=None):
                    if key not in self._data:
                        return default
                    v = self._data.pop(key)
                    self._data[key] = v
                    return v

                def put(self, key, value):
                    self._data.pop(key, None)
                    self._data[key] = value
                    if len(self._data) > self.capacity:
                        del self._data[next(iter(self._data))]

                def __len__(self):
                    return len(self._data)

                def __contains__(self, key):
                    return key in self._data
            '''),
    },
)

# 8. implement to spec -------------------------------------------------------------------------------------------
task(
    id="py-impl-intervals", kind="implement",
    prompt="Implement the two functions in intervals.py exactly as their docstrings say. Add tests if you like.",
    files={
        "intervals.py": d('''\
            def merge_intervals(intervals):
                """Merge closed intervals given as (start, end) pairs.

                Returns a new list of (start, end) tuples sorted by start, with overlapping or touching intervals
                ((1, 2) and (2, 3)) merged.  The input is not modified and may be in any order.  An interval with
                start > end raises ValueError.  An empty input gives [].
                """
                raise NotImplementedError


            def insert_interval(intervals, new):
                """Insert `new` into a sorted list of non-overlapping intervals and merge as needed.

                Returns a new list in the same form as merge_intervals; the input is not modified.
                """
                raise NotImplementedError
            '''),
        "tests/test_intervals.py": d('''\
            import unittest

            from intervals import merge_intervals


            class IntervalsTest(unittest.TestCase):
                def test_merge(self):
                    self.assertEqual(merge_intervals([(1, 3), (2, 6), (8, 10)]), [(1, 6), (8, 10)])
            '''),
    },
    hidden={
        "_hidden/test_intervals_hidden.py": d('''\
            import unittest

            from intervals import insert_interval, merge_intervals


            class Hidden(unittest.TestCase):
                def test_merge(self):
                    self.assertEqual(merge_intervals([]), [])
                    self.assertEqual(merge_intervals([(5, 7), (1, 2), (2, 3)]), [(1, 3), (5, 7)])
                    self.assertEqual(merge_intervals([(1, 10), (2, 3), (4, 5)]), [(1, 10)])
                    self.assertEqual(merge_intervals([[3, 3]]), [(3, 3)])
                    self.assertEqual(merge_intervals([(-5, -1), (-2, 0)]), [(-5, 0)])
                    src = [(4, 5), (1, 2)]
                    merge_intervals(src)
                    self.assertEqual(src, [(4, 5), (1, 2)])
                    with self.assertRaises(ValueError):
                        merge_intervals([(1, 2), (5, 4)])

                def test_insert(self):
                    self.assertEqual(insert_interval([(1, 3), (6, 9)], (2, 5)), [(1, 5), (6, 9)])
                    self.assertEqual(insert_interval([(1, 2), (3, 5), (6, 7), (8, 10), (12, 16)], (4, 8)),
                                     [(1, 2), (3, 10), (12, 16)])
                    self.assertEqual(insert_interval([], (1, 1)), [(1, 1)])
                    self.assertEqual(insert_interval([(1, 2)], (3, 4)), [(1, 2), (3, 4)])
                    self.assertEqual(insert_interval([(3, 4)], (0, 1)), [(0, 1), (3, 4)])
                    src = [(1, 2)]
                    insert_interval(src, (2, 3))
                    self.assertEqual(src, [(1, 2)])
                    with self.assertRaises(ValueError):
                        insert_interval([(1, 2)], (3, 2))
            '''),
    },
    solution={
        "intervals.py": d('''\
            def merge_intervals(intervals):
                items = []
                for s, e in intervals:
                    if s > e:
                        raise ValueError((s, e))
                    items.append((s, e))
                items.sort()
                out = []
                for s, e in items:
                    if out and s <= out[-1][1]:
                        out[-1] = (out[-1][0], max(out[-1][1], e))
                    else:
                        out.append((s, e))
                return out


            def insert_interval(intervals, new):
                return merge_intervals(list(intervals) + [tuple(new)])
            '''),
    },
)

# 9. bug from a stack trace --------------------------------------------------------------------------------------
task(
    id="py-trace-billing", kind="stack-trace",
    prompt=d('''\
        The nightly job crashed with:

        Traceback (most recent call last):
          File "jobs/nightly.py", line 14, in run
            due = next_billing_date(sub.start, today)
          File "billing.py", line 18, in next_billing_date
            d = add_months(start, k)
          File "billing.py", line 6, in add_months
            return d.replace(year=d.year + y, month=m + 1)
        ValueError: day is out of range for month

        for a subscription that started on 2024-01-31 (today was 2024-02-10). Fix billing.py so that it follows
        its docstring.'''),
    files={
        "billing.py": d('''\
            from datetime import date


            def add_months(d, n):
                y, m = divmod(d.month - 1 + n, 12)
                return d.replace(year=d.year + y, month=m + 1)


            def next_billing_date(start, today):
                """The first billing date strictly after `today`.

                The billing dates of a subscription are start + 1 month, start + 2 months, and so on, each on the
                start's day of month; in a month that has no such day, billing happens on that month's last day
                (and the next month goes back to the start's day).
                """
                k = 1
                while True:
                    d = add_months(start, k)
                    if d > today:
                        return d
                    k += 1
            '''),
        "tests/test_billing.py": d('''\
            import unittest
            from datetime import date

            from billing import next_billing_date


            class BillingTest(unittest.TestCase):
                def test_mid_month(self):
                    self.assertEqual(next_billing_date(date(2024, 1, 15), date(2024, 3, 1)), date(2024, 3, 15))
            '''),
    },
    hidden={
        "_hidden/test_billing_hidden.py": d('''\
            import unittest
            from datetime import date

            from billing import add_months, next_billing_date


            class Hidden(unittest.TestCase):
                def test_month_end(self):
                    s = date(2024, 1, 31)
                    self.assertEqual(next_billing_date(s, date(2024, 2, 10)), date(2024, 2, 29))
                    self.assertEqual(next_billing_date(s, date(2024, 2, 29)), date(2024, 3, 31))
                    self.assertEqual(next_billing_date(s, date(2024, 4, 1)), date(2024, 4, 30))
                    self.assertEqual(next_billing_date(date(2023, 1, 31), date(2023, 2, 1)), date(2023, 2, 28))
                    self.assertEqual(next_billing_date(date(2023, 11, 30), date(2024, 1, 31)), date(2024, 2, 29))

                def test_year(self):
                    self.assertEqual(next_billing_date(date(2024, 12, 31), date(2024, 12, 31)), date(2025, 1, 31))
                    self.assertEqual(next_billing_date(date(2024, 3, 10), date(2024, 1, 1)), date(2024, 4, 10))
                    self.assertEqual(add_months(date(2024, 1, 31), 1), date(2024, 2, 29))
                    self.assertEqual(add_months(date(2024, 1, 31), 13), date(2025, 2, 28))
            '''),
    },
    solution={
        "billing.py": d('''\
            import calendar
            from datetime import date


            def add_months(d, n):
                y, m = divmod(d.month - 1 + n, 12)
                year, month = d.year + y, m + 1
                return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


            def next_billing_date(start, today):
                k = 1
                while True:
                    d = add_months(start, k)
                    if d > today:
                        return d
                    k += 1
            '''),
    },
)

# 10. implement to spec (Russian) --------------------------------------------------------------------------------
task(
    id="py-impl-csvline", kind="implement", ru=True,
    prompt="Реализуй parse_csv_line в csvline.py по докстрингу. Модуль csv стандартной библиотеки не использовать "
           "(разбор нужно написать самому).",
    files={
        "csvline.py": d('''\
            def parse_csv_line(line, delimiter=","):
                """Разобрать одну строку CSV (RFC 4180) в список строк.

                - Поля разделены `delimiter` (один символ). Пустые поля допустимы: "a,,b" -> ["a", "", "b"],
                  "a," -> ["a", ""], "" -> [""].
                - Поле в двойных кавычках может содержать разделитель; две кавычки подряд внутри него - одна
                  кавычка: '"a,""b"""' -> ['a,"b"'].
                - Пробелы не обрезаются: ' a , b' -> [' a ', ' b'].
                - Незакрытая кавычка или символ сразу после закрывающей кавычки (кроме разделителя) -> ValueError.
                - Кавычка в середине поля без кавычек ('a"b') - обычный символ.
                """
                raise NotImplementedError
            '''),
        "tests/test_csvline.py": d('''\
            import unittest

            from csvline import parse_csv_line


            class CsvTest(unittest.TestCase):
                def test_simple(self):
                    self.assertEqual(parse_csv_line("a,b,c"), ["a", "b", "c"])
            '''),
    },
    hidden={
        "_hidden/test_csvline_hidden.py": d('''\
            import unittest
            from pathlib import Path

            import csvline
            from csvline import parse_csv_line as p


            class Hidden(unittest.TestCase):
                def test_cases(self):
                    self.assertEqual(p("a,,b"), ["a", "", "b"])
                    self.assertEqual(p("a,"), ["a", ""])
                    self.assertEqual(p(""), [""])
                    self.assertEqual(p('"a,""b"""'), ['a,"b"'])
                    self.assertEqual(p(' a , b'), [' a ', ' b'])
                    self.assertEqual(p('a"b,c'), ['a"b', 'c'])
                    self.assertEqual(p('"",x'), ['', 'x'])
                    self.assertEqual(p('"x";"y;z"', delimiter=";"), ['x', 'y;z'])
                    self.assertEqual(p('"привет, мир",ок'), ['привет, мир', 'ок'])
                    self.assertEqual(p(',,'), ['', '', ''])

                def test_errors(self):
                    for bad in ('"abc', '"a"b,c', 'x,"y', '"a""'):
                        with self.assertRaises(ValueError, msg=bad):
                            p(bad)

                def test_no_csv_module(self):
                    src = Path(csvline.__file__).read_text(encoding="utf-8")
                    self.assertNotIn("import csv", src)
            '''),
    },
    solution={
        "csvline.py": d('''\
            def parse_csv_line(line, delimiter=","):
                out, i, n = [], 0, len(line)
                while True:
                    if i < n and line[i] == '"':
                        i += 1
                        buf = []
                        while True:
                            if i >= n:
                                raise ValueError("unclosed quote")
                            c = line[i]
                            if c == '"':
                                if i + 1 < n and line[i + 1] == '"':
                                    buf.append('"')
                                    i += 2
                                    continue
                                i += 1
                                break
                            buf.append(c)
                            i += 1
                        out.append("".join(buf))
                        if i < n and line[i] != delimiter:
                            raise ValueError("text after closing quote")
                    else:
                        j = line.find(delimiter, i)
                        j = n if j < 0 else j
                        out.append(line[i:j])
                        i = j
                    if i >= n:
                        return out
                    i += 1
            '''),
    },
)

# 11. refactor without breaking tests ----------------------------------------------------------------------------
task(
    id="py-refactor-registry", kind="refactor",
    prompt=d('''\
        plugins.py keeps its state in a module-level dict. Refactor it into a class `Registry` with the methods
        register(name, factory, *, replace=False), create(name, *args, **kwargs), names(), clear() and support for
        `name in registry`. Add a module-level `default_registry = Registry()` and keep the module-level functions
        register/create/names/clear working as thin wrappers over it, so existing callers do not break. Separate
        Registry instances must not share state, and the module-level `_registry` dict must go away. Same errors
        and messages as now.'''),
    files={
        "plugins.py": d('''\
            _registry = {}


            def register(name, factory, *, replace=False):
                if name in _registry and not replace:
                    raise KeyError(f"plugin {name!r} already registered")
                _registry[name] = factory


            def create(name, *args, **kwargs):
                try:
                    factory = _registry[name]
                except KeyError:
                    raise KeyError(f"unknown plugin {name!r}") from None
                return factory(*args, **kwargs)


            def names():
                return sorted(_registry)


            def clear():
                _registry.clear()
            '''),
        "tests/test_plugins.py": d('''\
            import unittest

            import plugins


            class PluginsTest(unittest.TestCase):
                def setUp(self):
                    plugins.clear()

                def test_register_create(self):
                    plugins.register("upper", lambda s: s.upper())
                    self.assertEqual(plugins.create("upper", "ab"), "AB")
                    self.assertEqual(plugins.names(), ["upper"])

                def test_duplicate(self):
                    plugins.register("x", dict)
                    with self.assertRaises(KeyError):
                        plugins.register("x", list)
                    plugins.register("x", list, replace=True)
                    self.assertEqual(plugins.create("x"), [])
            '''),
    },
    hidden={
        "_hidden/test_plugins_hidden.py": d('''\
            import unittest

            import plugins


            class Hidden(unittest.TestCase):
                def setUp(self):
                    plugins.clear()

                def test_class(self):
                    a, b = plugins.Registry(), plugins.Registry()
                    a.register("one", lambda: 1)
                    self.assertIn("one", a)
                    self.assertNotIn("one", b)
                    self.assertEqual(a.create("one"), 1)
                    self.assertEqual(b.names(), [])
                    with self.assertRaises(KeyError) as cm:
                        b.create("one")
                    self.assertIn("unknown plugin 'one'", str(cm.exception))
                    with self.assertRaises(KeyError) as cm:
                        a.register("one", int)
                    self.assertIn("already registered", str(cm.exception))
                    a.clear()
                    self.assertEqual(a.names(), [])

                def test_default(self):
                    self.assertFalse(hasattr(plugins, "_registry"))
                    self.assertIsInstance(plugins.default_registry, plugins.Registry)
                    plugins.register("b", lambda x=0: x + 1)
                    plugins.register("a", str)
                    self.assertIn("b", plugins.default_registry)
                    self.assertEqual(plugins.names(), ["a", "b"])
                    self.assertEqual(plugins.create("b", x=4), 5)
                    self.assertEqual(plugins.default_registry.names(), ["a", "b"])
                    other = plugins.Registry()
                    self.assertEqual(other.names(), [])
            '''),
    },
    solution={
        "plugins.py": d('''\
            class Registry:
                def __init__(self):
                    self._items = {}

                def register(self, name, factory, *, replace=False):
                    if name in self._items and not replace:
                        raise KeyError(f"plugin {name!r} already registered")
                    self._items[name] = factory

                def create(self, name, *args, **kwargs):
                    try:
                        factory = self._items[name]
                    except KeyError:
                        raise KeyError(f"unknown plugin {name!r}") from None
                    return factory(*args, **kwargs)

                def names(self):
                    return sorted(self._items)

                def clear(self):
                    self._items.clear()

                def __contains__(self, name):
                    return name in self._items


            default_registry = Registry()


            def register(name, factory, *, replace=False):
                default_registry.register(name, factory, replace=replace)


            def create(name, *args, **kwargs):
                return default_registry.create(name, *args, **kwargs)


            def names():
                return default_registry.names()


            def clear():
                default_registry.clear()
            '''),
    },
)

# 12. implement to spec ------------------------------------------------------------------------------------------
task(
    id="py-impl-retry", kind="implement",
    prompt="Implement the `retry` decorator in retry.py as its docstring describes, and add a test file "
           "tests/test_retry.py that covers it. The suite runs with the standard library's unittest "
           "(python -m unittest discover -s tests), so write unittest.TestCase tests.",
    files={
        "retry.py": d('''\
            import time


            def retry(times=3, exceptions=(Exception,), delay=0.1, backoff=2.0, sleep=time.sleep):
                """Decorator: call the function up to `times` times while it raises one of `exceptions`.

                Between attempts it calls sleep(delay), then sleep(delay * backoff), sleep(delay * backoff ** 2)...
                (no sleep after the last attempt).  When every attempt fails, the last exception is re-raised.
                An exception that is not one of `exceptions` propagates at once, without a retry.  The wrapper keeps
                the function's __name__ and __doc__ (functools.wraps) and returns its result.  times < 1 raises
                ValueError when the decorator is created (not when the function is called).
                """
                raise NotImplementedError
            '''),
        "tests/.keep": "",
    },
    hidden={
        "_hidden/test_retry_hidden.py": d('''\
            import unittest

            from retry import retry


            class Hidden(unittest.TestCase):
                def test_succeeds_after_failures(self):
                    slept, calls = [], []

                    @retry(times=4, exceptions=(KeyError,), delay=0.5, backoff=3.0, sleep=slept.append)
                    def f(x):
                        """doc"""
                        calls.append(x)
                        if len(calls) < 3:
                            raise KeyError("k")
                        return x * 2

                    self.assertEqual(f(21), 42)
                    self.assertEqual(calls, [21, 21, 21])
                    self.assertEqual(slept, [0.5, 1.5])
                    self.assertEqual(f.__name__, "f")
                    self.assertEqual(f.__doc__, "doc")

                def test_all_fail(self):
                    slept = []
                    n = [0]

                    @retry(times=3, delay=1, backoff=2, sleep=slept.append)
                    def g():
                        n[0] += 1
                        raise ValueError(f"try {n[0]}")

                    with self.assertRaises(ValueError) as cm:
                        g()
                    self.assertEqual(str(cm.exception), "try 3")
                    self.assertEqual(slept, [1, 2])

                def test_other_exception(self):
                    slept = []
                    n = [0]

                    @retry(times=5, exceptions=(KeyError,), sleep=slept.append)
                    def h():
                        n[0] += 1
                        raise TypeError("no")

                    with self.assertRaises(TypeError):
                        h()
                    self.assertEqual((n[0], slept), (1, []))

                def test_once_and_bad(self):
                    slept = []

                    @retry(times=1, sleep=slept.append)
                    def k():
                        raise OSError("x")

                    with self.assertRaises(OSError):
                        k()
                    self.assertEqual(slept, [])
                    with self.assertRaises(ValueError):
                        retry(times=0)
                    self.assertEqual(retry(sleep=slept.append)(lambda a, b=1: a + b)(1, b=5), 6)
            '''),
    },
    solution={
        "retry.py": d('''\
            import functools
            import time


            def retry(times=3, exceptions=(Exception,), delay=0.1, backoff=2.0, sleep=time.sleep):
                if times < 1:
                    raise ValueError("times must be >= 1")

                def deco(fn):
                    @functools.wraps(fn)
                    def wrapper(*args, **kwargs):
                        wait = delay
                        for attempt in range(times):
                            try:
                                return fn(*args, **kwargs)
                            except exceptions:
                                if attempt == times - 1:
                                    raise
                                sleep(wait)
                                wait *= backoff
                    return wrapper
                return deco
            '''),
        "tests/test_retry.py": d('''\
            import unittest

            from retry import retry


            class RetryTest(unittest.TestCase):
                def test_ok(self):
                    self.assertEqual(retry(sleep=lambda s: None)(lambda: 1)(), 1)
            '''),
    },
)
