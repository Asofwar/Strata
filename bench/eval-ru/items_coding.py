"""Coding items: 12 self-contained tasks (8 Python, 4 JavaScript). Each has a prompt and a test that is appended to
the model's code and run (python -I / node). Pass = the test process exits 0 within the time limit.

Four prompts are in Russian, the way the owner writes to Codex."""

PY_RULE = "Reply with only the code, in one ```python block. No explanations, no example usage."
JS_RULE = "Reply with only the code, in one ```javascript block, plain Node.js (CommonJS, no exports, no imports)."
PY_RULE_RU = "Ответь только кодом в одном блоке ```python, без пояснений и без примеров использования."
JS_RULE_RU = "Ответь только кодом в одном блоке ```javascript (Node.js, CommonJS, без export и import), без пояснений."

ITEMS = [
    {"id": "code-roman", "lang": "python",
     "prompt": "Write a Python function `roman_to_int(s: str) -> int` that converts a Roman numeral (I..MMMCMXCIX) to an "
               "integer. " + PY_RULE,
     "test": """
assert roman_to_int("III") == 3
assert roman_to_int("LVIII") == 58
assert roman_to_int("MCMXCIV") == 1994
assert roman_to_int("MMMCMXCIX") == 3999
assert roman_to_int("XLIV") == 44
print("ok")
"""},
    {"id": "code-intervals", "lang": "python",
     "prompt": "Write a Python function `merge_intervals(intervals)` that takes a list of [start, end] pairs (unsorted, "
               "closed intervals) and returns the merged list sorted by start, as a list of lists. Touching intervals "
               "such as [1,2] and [2,3] merge. " + PY_RULE,
     "test": """
assert merge_intervals([[1,3],[2,6],[8,10],[15,18]]) == [[1,6],[8,10],[15,18]]
assert merge_intervals([[1,4],[4,5]]) == [[1,5]]
assert merge_intervals([]) == []
assert merge_intervals([[5,7],[1,2],[2,4],[6,6]]) == [[1,4],[5,7]]
print("ok")
"""},
    {"id": "code-lru", "lang": "python",
     "prompt": "Напиши на Python класс `LRUCache` с конструктором `LRUCache(capacity: int)` и методами `get(key) -> int` "
               "(возвращает -1, если ключа нет) и `put(key, value) -> None`. При переполнении удаляется давно не "
               "использованный ключ; `get` и `put` считаются использованием. " + PY_RULE_RU,
     "test": """
c = LRUCache(2)
c.put(1, 1); c.put(2, 2)
assert c.get(1) == 1
c.put(3, 3)
assert c.get(2) == -1
c.put(4, 4)
assert c.get(1) == -1
assert c.get(3) == 3 and c.get(4) == 4
c.put(3, 30)
c.put(5, 5)
assert c.get(4) == -1 and c.get(3) == 30
print("ok")
"""},
    {"id": "code-duration", "lang": "python",
     "prompt": "Write a Python function `parse_duration(s: str) -> int` that turns strings like \"1h30m15s\", \"45m\", "
               "\"2h\", \"90s\", \"1d2h\" into a number of seconds (units d, h, m, s, each at most once, in that order). "
               "Raise ValueError for an empty string or anything that does not match. " + PY_RULE,
     "test": """
assert parse_duration("1h30m15s") == 5415
assert parse_duration("45m") == 2700
assert parse_duration("2h") == 7200
assert parse_duration("90s") == 90
assert parse_duration("1d2h") == 93600
for bad in ["", "abc", "10x", "1m1h", "h"]:
    try:
        parse_duration(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("no ValueError for %r" % bad)
print("ok")
"""},
    {"id": "code-topk", "lang": "python",
     "prompt": "Write a Python function `top_k_frequent(words: list[str], k: int) -> list[str]` returning the k most "
               "frequent words, ordered by frequency (highest first) and, for equal frequency, alphabetically. " + PY_RULE,
     "test": """
assert top_k_frequent(["i","love","leetcode","i","love","coding"], 2) == ["i","love"]
assert top_k_frequent(["the","day","is","sunny","the","the","the","sunny","is","is"], 4) == ["the","is","sunny","day"]
assert top_k_frequent(["b","a","c"], 2) == ["a","b"]
print("ok")
"""},
    {"id": "code-brackets", "lang": "python",
     "prompt": "Напиши функцию на Python `is_balanced(s: str) -> bool`, которая проверяет, что скобки (), [] и {} в строке "
               "сбалансированы и правильно вложены. Другие символы игнорируются. " + PY_RULE_RU,
     "test": """
assert is_balanced("") is True
assert is_balanced("([]{})") is True
assert is_balanced("a(b[c]d)e") is True
assert is_balanced("(]") is False
assert is_balanced("([)]") is False
assert is_balanced("((") is False
assert is_balanced("}") is False
print("ok")
"""},
    {"id": "code-flatten", "lang": "python",
     "prompt": "Write a Python function `flatten(d: dict, sep: str = \".\") -> dict` that flattens nested dicts into "
               "one level with joined keys, e.g. {\"a\": {\"b\": 1}} -> {\"a.b\": 1}. Lists and other values are kept "
               "as they are; an empty nested dict is dropped. " + PY_RULE,
     "test": """
assert flatten({"a": {"b": 1, "c": {"d": 2}}, "e": 3}) == {"a.b": 1, "a.c.d": 2, "e": 3}
assert flatten({"x": [1, {"y": 2}]}) == {"x": [1, {"y": 2}]}
assert flatten({"a": {"b": 1}}, sep="/") == {"a/b": 1}
assert flatten({"a": {}, "b": 1}) == {"b": 1}
print("ok")
"""},
    {"id": "code-pluralize", "lang": "python",
     "prompt": "Напиши функцию на Python `pluralize_ru(n: int, forms: tuple[str, str, str]) -> str`, которая возвращает "
               "строку вида \"<n> <слово>\" с правильной формой русского слова для числа n. forms - формы для 1, 2 и 5, "
               "например (\"яблоко\", \"яблока\", \"яблок\"). Учти 11-14 и отрицательные числа. " + PY_RULE_RU,
     "test": """
f = ("яблоко", "яблока", "яблок")
assert pluralize_ru(1, f) == "1 яблоко"
assert pluralize_ru(2, f) == "2 яблока"
assert pluralize_ru(5, f) == "5 яблок"
assert pluralize_ru(11, f) == "11 яблок"
assert pluralize_ru(12, f) == "12 яблок"
assert pluralize_ru(21, f) == "21 яблоко"
assert pluralize_ru(104, f) == "104 яблока"
assert pluralize_ru(111, f) == "111 яблок"
assert pluralize_ru(0, f) == "0 яблок"
assert pluralize_ru(-3, f) == "-3 яблока"
print("ok")
"""},
    {"id": "code-chunk", "lang": "javascript",
     "prompt": "Write a JavaScript function `chunk(arr, size)` that splits an array into arrays of `size` elements "
               "(the last one may be shorter). Throw a RangeError if size is not a positive integer. " + JS_RULE,
     "test": """
const assert = require("assert");
assert.deepStrictEqual(chunk([1,2,3,4,5], 2), [[1,2],[3,4],[5]]);
assert.deepStrictEqual(chunk([], 3), []);
assert.deepStrictEqual(chunk([1,2,3], 5), [[1,2,3]]);
assert.throws(() => chunk([1], 0), RangeError);
assert.throws(() => chunk([1], 1.5), RangeError);
console.log("ok");
"""},
    {"id": "code-csv", "lang": "javascript",
     "prompt": "Напиши функцию на JavaScript `parseCsvLine(line)`, которая разбирает одну строку CSV в массив строк: "
               "разделитель - запятая, поля могут быть в двойных кавычках, внутри кавычек запятая не разделяет, а \"\" "
               "означает одну кавычку. " + JS_RULE_RU,
     "test": '''
const assert = require("assert");
assert.deepStrictEqual(parseCsvLine('a,b,c'), ['a','b','c']);
assert.deepStrictEqual(parseCsvLine('"a,b",c'), ['a,b','c']);
assert.deepStrictEqual(parseCsvLine('"he said ""hi""",x'), ['he said "hi"','x']);
assert.deepStrictEqual(parseCsvLine('a,,c'), ['a','','c']);
assert.deepStrictEqual(parseCsvLine(''), ['']);
assert.deepStrictEqual(parseCsvLine('x,'), ['x','']);
console.log("ok");
'''},
    {"id": "code-semver", "lang": "javascript",
     "prompt": "Write a JavaScript function `compareSemver(a, b)` that compares two versions like \"1.2.10\" and "
               "\"1.10.0\" (major.minor.patch, optional pre-release after '-', e.g. \"1.0.0-rc.1\") and returns -1, 0 or 1. "
               "A pre-release is lower than the same version without one; pre-release parts compare numerically when "
               "both are numbers, else as strings. " + JS_RULE,
     "test": """
const assert = require("assert");
assert.strictEqual(compareSemver("1.2.10", "1.10.0"), -1);
assert.strictEqual(compareSemver("2.0.0", "1.99.99"), 1);
assert.strictEqual(compareSemver("1.0.0", "1.0.0"), 0);
assert.strictEqual(compareSemver("1.0.0-rc.1", "1.0.0"), -1);
assert.strictEqual(compareSemver("1.0.0-rc.2", "1.0.0-rc.10"), -1);
assert.strictEqual(compareSemver("1.0.0-beta", "1.0.0-alpha"), 1);
console.log("ok");
"""},
    {"id": "code-groupby", "lang": "javascript",
     "prompt": "Write a JavaScript function `groupBy(items, keyFn)` that returns a Map from key to an array of the items "
               "with that key, keeping the input order inside each group and the order in which keys first appear. "
               + JS_RULE,
     "test": """
const assert = require("assert");
const m = groupBy([1,2,3,4,5,6], x => x % 3);
assert.ok(m instanceof Map);
assert.deepStrictEqual([...m.keys()], [1,2,0]);
assert.deepStrictEqual(m.get(0), [3,6]);
assert.deepStrictEqual(m.get(1), [1,4]);
const w = groupBy(["apple","avocado","banana"], s => s[0]);
assert.deepStrictEqual([...w.entries()], [["a",["apple","avocado"]],["b",["banana"]]]);
assert.strictEqual(groupBy([], x => x).size, 0);
console.log("ok");
"""},
]
