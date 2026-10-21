"""Tool-use items: 7 OpenAI-format tool-calling prompts. A check gets the reply's message (content, tool_calls with
parsed arguments) and returns (passed, reason). Arguments that are not valid JSON fail the item."""

WEATHER = {"type": "function", "function": {
    "name": "get_weather", "description": "Current weather for a city.",
    "parameters": {"type": "object", "properties": {
        "city": {"type": "string", "description": "City name in English, e.g. \"Kazan\""},
        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}},
        "required": ["city", "unit"]}}}
CURRENCY = {"type": "function", "function": {
    "name": "convert_currency", "description": "Convert an amount between currencies.",
    "parameters": {"type": "object", "properties": {
        "amount": {"type": "number"},
        "from": {"type": "string", "description": "ISO 4217 code, e.g. USD"},
        "to": {"type": "string", "description": "ISO 4217 code, e.g. EUR"}},
        "required": ["amount", "from", "to"]}}}
ISSUES = {"type": "function", "function": {
    "name": "search_issues", "description": "Search the issues of a GitHub repository.",
    "parameters": {"type": "object", "properties": {
        "repo": {"type": "string", "description": "owner/name"},
        "query": {"type": "string"},
        "state": {"type": "string", "enum": ["open", "closed", "all"]},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50}},
        "required": ["repo", "query", "state"]}}}
WRITE = {"type": "function", "function": {
    "name": "write_file", "description": "Create or overwrite a text file in the workspace. Missing parent directories are created automatically.",
    "parameters": {"type": "object", "properties": {
        "path": {"type": "string", "description": "Path relative to the workspace root"},
        "content": {"type": "string"}},
        "required": ["path", "content"]}}}
SHELL = {"type": "function", "function": {
    "name": "run_shell", "description": "Run a shell command in the workspace and return its output.",
    "parameters": {"type": "object", "properties": {
        "command": {"type": "string"}},
        "required": ["command"]}}}

SYSTEM = "You are a helpful assistant. Use the tools when they are needed."


def calls(msg):
    return [(c["name"], c["args"]) for c in msg.get("tool_calls") or []]


def one_call(msg, name):
    cs = calls(msg)
    if len(cs) != 1:
        return None, f"{len(cs)} calls"
    if cs[0][0] != name:
        return None, f"called {cs[0][0]}"
    return cs[0][1], ""


def check_weather_kazan(msg):
    a, why = one_call(msg, "get_weather")
    if a is None:
        return False, why
    ok = str(a.get("city", "")).strip().lower() in ("kazan", "казань") and a.get("unit") == "celsius"
    return ok, "" if ok else f"args {a}"


def check_currency(msg):
    a, why = one_call(msg, "convert_currency")
    if a is None:
        return False, why
    ok = (a.get("amount") in (250, 250.0) and str(a.get("from", "")).upper() == "EUR"
          and str(a.get("to", "")).upper() == "JPY")
    return ok, "" if ok else f"args {a}"


def check_issues(msg):
    a, why = one_call(msg, "search_issues")
    if a is None:
        return False, why
    ok = (a.get("repo") == "Asofwar/Strata" and a.get("state") == "open" and a.get("limit") == 5
          and "kv" in str(a.get("query", "")).lower())
    return ok, "" if ok else f"args {a}"


def check_parallel(msg):
    cs = calls(msg)
    cities = sorted(str(a.get("city", "")).strip().lower() for n, a in cs if n == "get_weather")
    ok = len(cs) == 2 and cities in (["moscow", "paris"], ["москва", "париж"], ["moscow", "париж"], ["москва", "paris"])
    return ok, "" if ok else f"calls {cs}"


def check_write_json(msg):
    a, why = one_call(msg, "write_file")
    if a is None:
        return False, why
    import json
    try:
        body = json.loads(a.get("content", ""))
    except (TypeError, ValueError):
        return False, f"content not JSON: {a.get('content')!r}"
    ok = a.get("path") in ("config/app.json", "./config/app.json") and body == {"debug": True, "port": 8080,
                                                                                 "name": "Страта"}
    return ok, "" if ok else f"args {a}"


def check_no_call(msg):
    if calls(msg):
        return False, f"calls {calls(msg)}"
    text = msg.get("content") or ""
    ok = "56" in text
    return ok, "" if ok else f"content {text[:80]!r}"


def check_followup(msg):
    if calls(msg):
        return False, f"calls {calls(msg)}"
    text = (msg.get("content") or "").lower()
    cyr = sum("а" <= ch <= "я" or ch == "ё" for ch in text)
    ok = cyr > 20 and ("да" in text or "нужн" in text or "стоит" in text) and ("-3" in text or "−3" in text or "снег" in text)
    return ok, "" if ok else f"content {text[:120]!r}"


ITEMS = [
    {"id": "tool-weather-ru", "tools": [WEATHER, CURRENCY], "check": check_weather_kazan,
     "messages": [{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": "Какая сейчас погода в Казани? Температуру дай в градусах Цельсия."}]},
    {"id": "tool-currency", "tools": [WEATHER, CURRENCY], "check": check_currency,
     "messages": [{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": "Convert 250 euros to Japanese yen."}]},
    {"id": "tool-issues-ru", "tools": [ISSUES, SHELL], "check": check_issues,
     "messages": [{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": "Найди открытые issues в репозитории Asofwar/Strata про kv cache, "
                                              "покажи не больше 5."}]},
    {"id": "tool-parallel-ru", "tools": [WEATHER], "check": check_parallel,
     "messages": [{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": "Сравни погоду в Москве и в Париже (в Цельсиях). Запроси оба города сразу."}]},
    {"id": "tool-write-json-ru", "tools": [WRITE, SHELL], "check": check_write_json,
     "messages": [{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": "Создай файл config/app.json с JSON-объектом: debug = true, port = 8080, "
                                              "name = \"Страта\"."}]},
    {"id": "tool-none-ru", "tools": [WEATHER, SHELL], "check": check_no_call,
     "messages": [{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": "Сколько будет 7 умножить на 8? Ответь одним числом."}]},
    {"id": "tool-followup-ru", "tools": [WEATHER], "check": check_followup,
     "messages": [{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": "Нужна ли мне сегодня тёплая куртка в Новосибирске?"},
                  {"role": "assistant", "content": "", "tool_calls": [
                      {"id": "call_1", "type": "function",
                       "function": {"name": "get_weather", "arguments": "{\"city\": \"Novosibirsk\", \"unit\": \"celsius\"}"}}]},
                  {"role": "tool", "tool_call_id": "call_1",
                   "content": "{\"city\": \"Novosibirsk\", \"temp\": -3, \"condition\": \"snow\", \"wind_ms\": 6}"}]},
]
