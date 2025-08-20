"""Web parser utilities for scraping university application data."""

import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from models import Applicant, Direction

TABLE_HEADERS = {
    "code": "физическое лицо",
    "points": "сумма баллов",
    "consent": "согласие на зачисление",
    "priority": "приоритет",
}

BASE_URL = "https://abitur.sstu.ru/vpo/direction/2025/{}/m/o/b"
DIGITS_RE = re.compile(r"\b\d{4,}\b")


def normalize_header(text: str) -> str:
    """Normalize table header text for consistent matching.

    Args:
        text: Raw header text from HTML

    Returns:
        Normalized header text
    """
    t = (text or "").lower()
    t = t.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    t = t.replace("<br>", " ")

    t = re.sub(r"\(.*?\)", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def pick_table(soup: BeautifulSoup):
    """Find the most suitable table containing applicant data.

    Args:
        soup: BeautifulSoup object of the parsed HTML

    Returns:
        Table element or None if no suitable table found
    """
    tables = soup.find_all("table")
    matched = []

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
        if need_hits >= 2:
            matched.append(table)

    if not matched:
        return None
    return matched[-1]


def build_header_index(table) -> dict[str, int]:
    """Build mapping from header types to column indices.

    Args:
        table: HTML table element

    Returns:
        Dictionary mapping header keys to column indices
    """
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
    """Extract applicant code from cell text.

    Args:
        cell_text: Text content of table cell

    Returns:
        Applicant code as integer or None if not found
    """
    match = DIGITS_RE.search(cell_text)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def extract_int(cell_text: str) -> Optional[int]:
    """Extract integer value from cell text.

    Args:
        cell_text: Text content of table cell

    Returns:
        Integer value or None if not found/parseable
    """
    cell_text = (cell_text or "").strip().replace("\xa0", " ")
    cell_text = cell_text.replace(",", ".")
    m = re.search(r"-?\d+", cell_text)
    if m:
        try:
            return int(m.group(0))
        except ValueError:
            return None
    return None


def fetch_html(url: str, *, retries: int = 3, timeout: int = 20) -> str:
    """Fetch HTML content from URL with retry logic.

    Args:
        url: URL to fetch
        retries: Number of retry attempts (default: 3)
        timeout: Request timeout in seconds (default: 20)

    Returns:
        HTML content as string

    Raises:
        Exception: If all retry attempts fail
    """
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
        except (requests.RequestException, requests.Timeout, ValueError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.0 * attempt)
    raise RuntimeError(f"Не удалось загрузить {url}: {last_err}")


def _extract_cell_value(
    tds: list, header_idx: dict[str, int], key: str
) -> Optional[str]:
    """Extract text content from table cell if column exists."""
    if key in header_idx and header_idx[key] < len(tds):
        return tds[header_idx[key]].get_text(" ", strip=True)
    return None


def _process_table_row(
    tds: list, header_idx: dict[str, int], direction: Direction
) -> Optional[Applicant]:
    """Process a single table row to extract applicant data."""
    if not tds or len(tds) <= header_idx["code"]:
        return None

    code_text = _extract_cell_value(tds, header_idx, "code")
    if not code_text:
        return None

    code = extract_code(code_text)
    if code is None:
        return None

    points_text = _extract_cell_value(tds, header_idx, "points")
    points = extract_int(points_text) if points_text else None

    # Check consent - skip if not consented
    consent_text = _extract_cell_value(tds, header_idx, "consent")
    if consent_text:
        consent = (
            True
            if "✓" in consent_text
            else (False if "—" in consent_text or consent_text == "" else None)
        )
        if consent is None or consent is False:
            return None

    priority_text = _extract_cell_value(tds, header_idx, "priority")
    priority = extract_int(priority_text) if priority_text else None

    return Applicant(
        code=code,
        directions={
            direction.name: {
                "points": points,
                "priority": priority,
            }
        },
    )


def get_applicants(direction: Direction) -> list[Applicant]:
    """Extract applicant data for a specific direction from web page.

    Args:
        direction: Direction object containing name and URL code

    Returns:
        List of Applicant objects with extracted data

    Raises:
        RuntimeError: If table not found or required columns missing
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
        applicant = _process_table_row(tds, header_idx, direction)
        if applicant:
            applicants.append(applicant)

    return applicants
