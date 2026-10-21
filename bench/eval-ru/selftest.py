"""Checks the checkers without a model: reference answers must pass, a few known-bad ones must fail.

    python bench/eval-ru/selftest.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import items_coding  # noqa: E402
import items_russian  # noqa: E402
import items_tools  # noqa: E402
import run_eval  # noqa: E402

REF = {
    "code-roman": """```python
def roman_to_int(s):
    v = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    t = 0
    for i, c in enumerate(s):
        t += -v[c] if i + 1 < len(s) and v[s[i + 1]] > v[c] else v[c]
    return t
```""",
    "code-intervals": """```python
def merge_intervals(iv):
    out = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out
```""",
    "code-lru": """```python
from collections import OrderedDict
class LRUCache:
    def __init__(self, capacity):
        self.c, self.d = capacity, OrderedDict()
    def get(self, k):
        if k not in self.d:
            return -1
        self.d.move_to_end(k)
        return self.d[k]
    def put(self, k, v):
        self.d[k] = v
        self.d.move_to_end(k)
        if len(self.d) > self.c:
            self.d.popitem(last=False)
```""",
    "code-duration": """```python
import re
def parse_duration(s):
    m = re.fullmatch(r"(?:(\\d+)d)?(?:(\\d+)h)?(?:(\\d+)m)?(?:(\\d+)s)?", s)
    if not s or not m:
        raise ValueError(s)
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se
```""",
    "code-topk": """```python
from collections import Counter
def top_k_frequent(words, k):
    c = Counter(words)
    return sorted(c, key=lambda w: (-c[w], w))[:k]
```""",
    "code-brackets": """```python
def is_balanced(s):
    st, pair = [], {")": "(", "]": "[", "}": "{"}
    for ch in s:
        if ch in "([{":
            st.append(ch)
        elif ch in pair:
            if not st or st.pop() != pair[ch]:
                return False
    return not st
```""",
    "code-flatten": """```python
def flatten(d, sep="."):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            for k2, v2 in flatten(v, sep).items():
                out[f"{k}{sep}{k2}"] = v2
        else:
            out[k] = v
    return out
```""",
    "code-pluralize": """```python
def pluralize_ru(n, forms):
    a = abs(n)
    if a % 10 == 1 and a % 100 != 11:
        f = forms[0]
    elif 2 <= a % 10 <= 4 and not 12 <= a % 100 <= 14:
        f = forms[1]
    else:
        f = forms[2]
    return f"{n} {f}"
```""",
    "code-chunk": """```javascript
function chunk(arr, size) {
  if (!Number.isInteger(size) || size <= 0) throw new RangeError("size");
  const out = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}
```""",
    "code-csv": """```javascript
function parseCsvLine(line) {
  const out = []; let cur = ""; let q = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (q) {
      if (c === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (c === '"') q = false;
      else cur += c;
    } else if (c === '"') q = true;
    else if (c === ",") { out.push(cur); cur = ""; }
    else cur += c;
  }
  out.push(cur);
  return out;
}
```""",
    "code-semver": """```javascript
export function compareSemver(a, b) {
  const [ma, pa] = a.split("-"); const [mb, pb] = b.split("-");
  const x = ma.split(".").map(Number), y = mb.split(".").map(Number);
  for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] < y[i] ? -1 : 1;
  if (pa === undefined && pb === undefined) return 0;
  if (pa === undefined) return 1;
  if (pb === undefined) return -1;
  const p = pa.split("."), q = pb.split(".");
  for (let i = 0; i < Math.max(p.length, q.length); i++) {
    if (p[i] === undefined) return -1;
    if (q[i] === undefined) return 1;
    const n = /^\\d+$/.test(p[i]) && /^\\d+$/.test(q[i]);
    const u = n ? Number(p[i]) : p[i], v = n ? Number(q[i]) : q[i];
    if (u !== v) return u < v ? -1 : 1;
  }
  return 0;
}
```""",
    "code-groupby": """Here is the function:

```js
function groupBy(items, keyFn) {
  const m = new Map();
  for (const it of items) { const k = keyFn(it); if (!m.has(k)) m.set(k, []); m.get(k).push(it); }
  return m;
}
module.exports = { groupBy };
```""",
}

TOOLS_OK = {
    "tool-weather-ru": {"tool_calls": [{"name": "get_weather", "args": {"city": "Kazan", "unit": "celsius"}}]},
    "tool-currency": {"tool_calls": [{"name": "convert_currency", "args": {"amount": 250, "from": "EUR", "to": "JPY"}}]},
    "tool-issues-ru": {"tool_calls": [{"name": "search_issues", "args": {"repo": "Asofwar/Strata", "query": "kv cache",
                                                                         "state": "open", "limit": 5}}]},
    "tool-parallel-ru": {"tool_calls": [{"name": "get_weather", "args": {"city": "Moscow", "unit": "celsius"}},
                                        {"name": "get_weather", "args": {"city": "Paris", "unit": "celsius"}}]},
    "tool-write-json-ru": {"tool_calls": [{"name": "write_file", "args": {
        "path": "config/app.json", "content": "{\n  \"debug\": true,\n  \"port\": 8080,\n  \"name\": \"Страта\"\n}"}}]},
    "tool-none-ru": {"content": "56", "tool_calls": []},
    "tool-followup-ru": {"content": "Да, куртка нужна: в Новосибирске -3 °C и идёт снег.", "tool_calls": []},
}

RU_OK = {
    "ru-closure": "Замыкание - это функция, которая помнит переменные из того места, где её создали. Даже когда внешняя "
                  "функция уже закончила работу, внутренняя продолжает видеть её переменные.",
    "ru-3-bullets": "- История всех изменений\n- Удобная совместная работа\n- Ветки для экспериментов",
    "ru-translate-en-ru": "Никогда не открывайте сервер за пределы 127.0.0.1 без ключа API. Установщик создаёт ключ сам, "
                          "если выбрать доступ по локальной сети. Если видеокарте не хватает памяти, сервер переносит "
                          "часть модели в оперативную память, поэтому ответы медленнее, но остаются верными.",
    "ru-translate-ru-en": "The model runs on one graphics card and uses the computer's RAM for the parts that do not fit "
                          "in video memory. The more video memory, the faster the model answers. Before the first start "
                          "the program downloads about twenty gigabytes of files.",
    "ru-summary": "В сентябре поддержка получила 1 240 обращений, на 18% больше из-за ошибки входа в аккаунт в версии 3.2, "
                  "которую исправили в 3.2.1. Время ответа и удовлетворённость ухудшились, в октябре наймут специалиста.",
    "ru-capital": "Канберра",
    "ru-json": "```json\n{\"name\": \"Иван Петров\", \"age\": 34, \"city\": \"Тверь\"}\n```",
    "ru-apples": "После того как Маша съела 2, осталось 15. Треть от 15 - это 5, их она отдала.\n\nОтвет: 10",
    "ru-grammar": "Правильно: «Я кладу книгу на стол и надеваю пальто, потому что на улице холодно». Глагола «ложу» "
                  "в литературном языке нет, а одевают кого-то, надевают что-то.",
    "ru-grandma": "Оперативная память - это как рабочий стол у компьютера. На нём лежат вещи, с которыми он работает "
                  "прямо сейчас. Чем больше стол, тем больше дел можно делать сразу. Когда компьютер выключают, стол "
                  "убирают.",
}

RU_BAD = {
    "ru-capital": "Канберра.",
    "ru-3-bullets": "Вот преимущества:\n- История\n- Ветки\n- Совместная работа",
    "ru-closure": "A closure is a function that remembers its scope.",
    "ru-apples": "Ответ: 11",
    "ru-grandma": "Это RAM, быстрая память. Она хранит данные. Компьютер её использует.",
}


def main():
    bad = 0
    for it in items_coding.ITEMS:
        ok, why = run_eval.score("coding", it, {"content": REF[it["id"]], "tool_calls": [], "bad_args": []})
        if not ok:
            print("reference fails", it["id"], why)
            bad += 1
        ok, _ = run_eval.score("coding", it, {"content": "```python\npass\n```", "tool_calls": [], "bad_args": []})
        if ok:
            print("empty solution passes", it["id"])
            bad += 1
    for it in items_tools.ITEMS:
        m = {"content": "", "bad_args": [], **TOOLS_OK[it["id"]]}
        ok, why = run_eval.score("tools", it, m)
        if not ok:
            print("reference fails", it["id"], why)
            bad += 1
        ok, _ = run_eval.score("tools", it, {"content": "Не знаю.", "tool_calls": [], "bad_args": []})
        if ok:
            print("non-answer passes", it["id"])
            bad += 1
    for it in items_russian.ITEMS:
        ok, why = it["check"](RU_OK[it["id"]])
        if not ok:
            print("reference fails", it["id"], why)
            bad += 1
        if it["id"] in RU_BAD and it["check"](RU_BAD[it["id"]])[0]:
            print("bad answer passes", it["id"])
            bad += 1
        if it["check"]("答案是" + RU_OK[it["id"]])[0]:
            print("CJK answer passes", it["id"])
            bad += 1
    ns = run_eval.needle_items()
    for n in ns:
        assert n["code"] in n["prompt"]
    print(f"needles: {[(n['id'], n['code'], len(n['prompt'])) for n in ns]}")
    print("selftest:", "FAILED" if bad else "ok", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
