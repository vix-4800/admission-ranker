import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from models import Direction, Applicant

TABLE_HEADERS = {
    "code": "физическое лицо",
    "points": "сумма баллов",
    "consent": "согласие на зачисление",
    "priority": "приоритет",
}

BASE_URL = "https://abitur.sstu.ru/vpo/direction/2025/{}/m/o/b"
DIGITS_RE = re.compile(r"\b\d{4,}\b")

def normalize_header(text: str) -> str:
    """Приводим заголовки к нижнему регистру, убираем переносы/скобки и двойные пробелы."""
    t = (text or "").lower()
    t = t.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    t = t.replace("<br>", " ")

    # уберём всё в скобках, чтобы "Физическое лицо (уникальный код)" матчился на "физическое лицо"
    t = re.sub(r"\(.*?\)", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def pick_table(soup: BeautifulSoup):
    """Находим таблицу с нужными заголовками."""
    tables = soup.find_all("table")
    for table in tables:
        thead = table.find("thead")
        if not thead:
            continue
        ths = thead.find_all("th")
        normalized = [normalize_header(th.get_text(" ", strip=True)) for th in ths]
        need_hits = 0
        for key in TABLE_HEADERS.values():
            if any(key in h for h in normalized):
                need_hits += 1
        # достаточно, чтобы хотя бы код и баллы были найдены
        if need_hits >= 2:
            return table
    return None

def build_header_index(table) -> dict[str, int]:
    """Строим индекс колонок по ключам TABLE_HEADERS."""
    thead = table.find("thead")
    ths = thead.find_all("th")
    normalized = [normalize_header(th.get_text(" ", strip=True)) for th in ths]

    idx = {}
    for key, needle in TABLE_HEADERS.items():
        for i, h in enumerate(normalized):
            if needle in h:
                idx[key] = i
                break
    return idx

def extract_code(cell_text: str) -> Optional[int]:
    """Достаём числовой код абитуриента из ячейки с лишним текстом."""
    # берём только первую строку до <div>, но на всякий случай — через regex
    match = DIGITS_RE.search(cell_text)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None

def extract_int(cell_text: str) -> Optional[int]:
    cell_text = (cell_text or "").strip().replace("\xa0", " ")
    # заменим запятую на точку, если вдруг
    cell_text = cell_text.replace(",", ".")
    # вытащим целое число в начале
    m = re.search(r"-?\d+", cell_text)
    if m:
        try:
            return int(m.group(0))
        except ValueError:
            return None
    return None

def fetch_html(url: str, *, retries: int = 3, timeout: int = 20) -> str:
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/127.0 Safari/537.36"
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.0 * attempt)
    raise RuntimeError(f"Не удалось загрузить {url}: {last_err}")

def get_applicants(direction: Direction) -> list[Applicant]:
    """
    Парсим страницу направления и возвращаем список Applicants,
    где directions = { <direction.name>: {"points": int|None, "priority": int|None} }
    consent: True/False/None
    """
    url = BASE_URL.format(direction.url_code)
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    table = pick_table(soup)
    if table is None:
        raise RuntimeError(f"Не нашёл таблицу на {url}")

    header_idx = build_header_index(table)
    missing = [k for k in ("code", "points") if k not in header_idx]
    if missing:
        raise RuntimeError(f"На {url} не нашёл обязательные колонки: {missing}")

    tbody = table.find("tbody")
    if not tbody:
        return []

    applicants: list[Applicant] = []

    for tr in tbody.find_all("tr"):
        tds = tr.find_all(["td", "th"])
        if not tds or len(tds) <= header_idx["code"]:
            continue

        # Код
        code_text = tds[header_idx["code"]].get_text(" ", strip=True)
        code = extract_code(code_text)
        if code is None:
            continue

        # Баллы
        points = None
        if "points" in header_idx and header_idx["points"] < len(tds):
            points_text = tds[header_idx["points"]].get_text(" ", strip=True)
            points = extract_int(points_text)

        # Согласие
        consent = None
        if "consent" in header_idx and header_idx["consent"] < len(tds):
            consent_text = tds[header_idx["consent"]].get_text("", strip=True)
            consent = True if "✓" in consent_text else (False if "—" in consent_text or consent_text == "" else None)

        # Приоритет
        priority = None
        if "priority" in header_idx and header_idx["priority"] < len(tds):
            priority_text = tds[header_idx["priority"]].get_text(" ", strip=True)
            priority = extract_int(priority_text)

        applicants.append(
            Applicant(
                code=code,
                consent=consent,
                directions={
                    direction.name: {
                        "points": points,
                        "priority": priority,
                    }
                },
            )
        )

    return applicants
