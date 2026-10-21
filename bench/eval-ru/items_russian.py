"""Russian items: 10 prompts scored by simple rubric checks. Every check also fails a reply with CJK characters
(Qwen models sometimes switch to Chinese) or an empty answer. The checks are rough on purpose; the report also
reads a sample by hand."""
import json
import re

CYR = re.compile(r"[А-Яа-яЁё]")
LAT = re.compile(r"[A-Za-z]")
CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯]")
BULLET = re.compile(r"^\s*(?:[-*•–]|\d+[.)])\s+\S", re.M)


def cyr_share(text):
    c, l = len(CYR.findall(text)), len(LAT.findall(text))
    return c / max(1, c + l)


def words(text):
    return re.findall(r"[\wЁё-]+", text)


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if len(words(s)) >= 2]


def base(text, need_ru=True):
    if not text.strip():
        return "empty"
    if CJK.search(text):
        return "CJK characters"
    if need_ru and cyr_share(text) < 0.7:
        return f"cyrillic share {cyr_share(text):.2f}"
    return ""


def checks(text, *rules):
    fails = [why for ok, why in rules if not ok]
    return (not fails), "; ".join(fails)


def c_closure(t):
    b = base(t)
    if b:
        return False, b
    return checks(t, (len(words(t)) <= 120, f"{len(words(t))} words > 120"),
                  (re.search(r"функци", t, re.I) is not None, "no 'функци'"),
                  (re.search(r"переменн|окружени|област", t, re.I) is not None, "no variables/scope"))


def c_three_bullets(t):
    b = base(t)
    if b:
        return False, b
    n = len(BULLET.findall(t))
    lines = [x for x in t.strip().splitlines() if x.strip()]
    return checks(t, (n == 3, f"{n} bullets"), (len(lines) == 3, f"{len(lines)} non-empty lines"))


EN_TEXT = ("Never expose the server beyond 127.0.0.1 without an API key. The installer creates a key for you when you "
           "choose LAN access. If the graphics card runs out of memory, the server moves part of the model to system RAM, "
           "which makes replies slower but keeps them correct.")


def c_en_ru(t):
    b = base(t)
    if b:
        return False, b
    return checks(t, ("127.0.0.1" in t, "lost 127.0.0.1"),
                  (re.search(r"ключ", t, re.I) is not None, "no 'ключ'"),
                  (re.search(r"сервер", t, re.I) is not None, "no 'сервер'"),
                  (re.search(r"видеокарт|графическ", t, re.I) is not None, "no graphics card"),
                  (re.search(r"оперативн|ОЗУ|системн", t, re.I) is not None, "no system RAM"),
                  (len(words(t)) < 110, "too long"))


RU_TEXT = ("Модель запускается на одной видеокарте и использует оперативную память компьютера для тех частей, которые "
           "не помещаются в видеопамять. Чем больше видеопамяти, тем быстрее отвечает модель. Перед первым запуском "
           "программа скачивает около двадцати гигабайт файлов.")


def c_ru_en(t):
    b = base(t, need_ru=False)
    if b:
        return False, b
    tl = t.lower()
    return checks(t, (cyr_share(t) < 0.05, f"cyrillic share {cyr_share(t):.2f}"),
                  ("graphics card" in tl or "gpu" in tl or "video card" in tl, "no graphics card"),
                  ("memory" in tl or "ram" in tl, "no memory"),
                  ("twenty" in tl or "20" in tl, "no 20 GB"))


REPORT = ("Отчёт о работе отдела поддержки за сентябрь. В сентябре отдел получил 1 240 обращений, на 18% больше, чем в "
          "августе. Рост связан с выпуском новой версии мобильного приложения 3.2, после которого многие пользователи "
          "не могли войти в аккаунт из-за ошибки в обновлении токенов. Ошибку исправили 14 сентября в версии 3.2.1, и "
          "уже к концу месяца число обращений вернулось к обычному уровню - около 35 в день. Среднее время первого "
          "ответа выросло с 2 до 5 часов, потому что двое сотрудников были в отпуске. Удовлетворённость клиентов по "
          "опросам снизилась с 92% до 86%. На октябрь отдел планирует нанять ещё одного специалиста, подготовить "
          "статью с ответами на частые вопросы о входе в аккаунт и ввести дежурства по выходным. Руководитель отдела "
          "Анна Сергеевна Миронова отмечает, что без исправления 3.2.1 нагрузка была бы вдвое выше.")


def c_summary(t):
    b = base(t)
    if b:
        return False, b
    n = len(sentences(t))
    return checks(t, (1 <= n <= 2, f"{n} sentences"),
                  (re.search(r"1[\s ]?240|18\s?%|3\.2", t) is not None, "no key number"),
                  (re.search(r"вход|аккаунт|ошибк", t, re.I) is not None, "no cause"))


def c_capital(t):
    s = t.strip()
    return s == "Канберра", f"got {s[:40]!r}"


def c_json(t):
    s = t.strip()
    m = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", s, re.S)
    if m:
        s = m.group(1)
    try:
        o = json.loads(s)
    except ValueError:
        return False, f"not JSON: {t[:60]!r}"
    ok = isinstance(o, dict) and set(o) == {"name", "age", "city"} and o.get("age") == 34 \
        and "Иван" in str(o.get("name")) and "Петров" in str(o.get("name")) and o.get("city") == "Тверь"
    return ok, "" if ok else f"object {o}"


def c_apples(t):
    b = base(t)
    if b:
        return False, b
    last = [x for x in t.strip().splitlines() if x.strip()][-1]
    ok = re.fullmatch(r"\**Ответ:\s*\**\s*10\s*\**\.?", last.strip()) is not None
    return ok, "" if ok else f"last line {last[:60]!r}"


def c_grammar(t):
    b = base(t)
    if b:
        return False, b
    return checks(t, (re.search(r"кладу", t, re.I) is not None, "no 'кладу'"),
                  (re.search(r"надеваю", t, re.I) is not None, "no 'надеваю'"))


def c_grandma(t):
    b = base(t)
    if b:
        return False, b
    n = len(sentences(t))
    lat = re.findall(r"[A-Za-z]{2,}", t)
    # no key-word check: "без терминов" lets a good answer avoid even the word "память"
    return checks(t, (3 <= n <= 5, f"{n} sentences"), (not lat, f"latin words {lat[:5]}"))


ITEMS = [
    {"id": "ru-closure", "check": c_closure,
     "prompt": "Объясни простыми словами, что такое замыкание (closure) в JavaScript. Не больше 120 слов."},
    {"id": "ru-3-bullets", "check": c_three_bullets,
     "prompt": "Назови преимущества Git перед копированием папок с проектом. Ответ - ровно три пункта маркированного "
               "списка на русском языке, без вступления и без заключения."},
    {"id": "ru-translate-en-ru", "check": c_en_ru,
     "prompt": "Переведи на русский язык, ответ - только перевод:\n\n" + EN_TEXT},
    {"id": "ru-translate-ru-en", "check": c_ru_en,
     "prompt": "Translate into English. Reply with the translation only.\n\n" + RU_TEXT},
    {"id": "ru-summary", "check": c_summary,
     "prompt": "Перескажи этот отчёт в одном-двух предложениях:\n\n" + REPORT},
    {"id": "ru-capital", "check": c_capital,
     "prompt": "Напиши столицу Австралии одним словом по-русски, без точки и без пояснений."},
    {"id": "ru-json", "check": c_json,
     "prompt": "Верни JSON-объект с полями name, age и city для человека: Иван Петров, 34 года, живёт в Твери. "
               "Только JSON, без пояснений."},
    {"id": "ru-apples", "check": c_apples,
     "prompt": "У Маши было 17 яблок. Она съела 2, затем отдала брату треть оставшихся. Сколько яблок у неё осталось? "
               "Коротко объясни решение, а последней строкой напиши «Ответ: N»."},
    {"id": "ru-grammar", "check": c_grammar,
     "prompt": "Исправь ошибки в предложении и кратко объясни, что было не так: «Я ложу книгу на стол и одеваю пальто, "
               "потому что на улице холодно.»"},
    {"id": "ru-grandma", "check": c_grandma,
     "prompt": "Объясни бабушке, что такое оперативная память компьютера. 3-5 предложений, без английских слов и "
               "без терминов."},
]
