import os
from utils.json_util import save_to_json, load_from_json
from utils.web_parser import get_applicants
from models import Direction, Applicant

def merge_records(all_lists: list[list[Applicant]]) -> dict[int, Applicant]:
    """Объединяем записи с разных направлений по коду абитуриента."""
    merged: dict[int, Applicant] = {}

    for lst in all_lists:
        for rec in lst:
            if rec.code not in merged:
                merged[rec.code] = Applicant(code=rec.code, consent=rec.consent, directions={})
            # обновляем согласие, если его ещё не было
            if merged[rec.code].consent in (None, "", "—") and rec.consent:
                merged[rec.code].consent = rec.consent
            # сливаем направления
            for dir_name, info in rec.directions.items():
                merged[rec.code].directions[dir_name] = info

    return merged

def main():
    # my_code = 5063839
    directions = [
        Direction('ИВЧТ', '118', 12),
        Direction('ИФСТ', '156', 29),
        Direction('ПИНФ', '119', 15),
        Direction('ПИНЖ', '120', 15),
    ]

    filename = "applicants.json"
    if os.path.exists(filename):
        print("Загружаем данные из JSON...")
        merged = load_from_json(filename)
    else:
        print("Парсим страницы...")
        per_direction_lists = []
        for direction in directions:
            per_direction_lists.append(get_applicants(direction))

        merged = merge_records(per_direction_lists)
        save_to_json(merged, filename)

    print(f"Уникальных абитуриентов: {len(merged)}")
    # some_code = next(iter(merged))
    # print(merged[some_code])

if __name__ == "__main__":
	main()
