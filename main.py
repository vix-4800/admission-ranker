import os
from typing import Optional

from models import Applicant, Direction
from utils.json_util import load_from_json, save_to_json
from utils.web_parser import get_applicants


def merge_records(all_lists: list[list[Applicant]]) -> dict[int, Applicant]:
    merged: dict[int, Applicant] = {}

    for lst in all_lists:
        for rec in lst:
            if rec.code not in merged:
                merged[rec.code] = Applicant(code=rec.code, directions={})

            for dir_name, info in rec.directions.items():
                merged[rec.code].directions[dir_name] = info

    return merged


def get_points(app: Applicant, dir_name: str) -> Optional[int]:
    info = app.directions.get(dir_name)
    return None if not info else info.get("points")


def get_priority(app: Applicant, dir_name: str) -> Optional[int]:
    info = app.directions.get(dir_name)
    return None if not info else info.get("priority")


def build_preferences(merged: dict[int, Applicant]) -> dict[int, list[str]]:
    prefs: dict[int, list[str]] = {}
    for code, app in merged.items():
        pairs = []
        for dname, info in app.directions.items():
            pr = info.get("priority")
            pts = info.get("points")
            if pr is not None and pts is not None:
                pairs.append((pr, dname))
        pairs.sort(key=lambda x: (x[0], x[1]))
        prefs[code] = [d for _, d in pairs]
    return prefs


def build_dir_quota_map(directions: list[Direction]) -> dict[str, int]:
    return {d.name: d.avaliable_budget_places for d in directions}


def simulate_admissions(
    merged: dict[int, Applicant],
    directions: list[Direction],
) -> tuple[dict[int, Optional[str]], dict[str, list[int]]]:
    dir_quota = build_dir_quota_map(directions)
    dir_names = list(dir_quota.keys())
    prefs = build_preferences(merged)

    tentatives: dict[str, list[int]] = {dn: [] for dn in dir_names}
    assigned_dir: dict[int, Optional[str]] = {code: None for code in merged.keys()}
    next_choice_idx: dict[int, int] = {code: 0 for code in merged.keys()}

    def rank_dir_pool(dn: str, pool: list[int]) -> list[int]:
        filtered = [(code, get_points(merged[code], dn)) for code in pool]
        filtered = [(c, pts) for c, pts in filtered if pts is not None]
        filtered.sort(key=lambda x: (-x[1], x[0]))
        return [c for c, _ in filtered]

    changed = True
    while changed:
        changed = False

        proposals: dict[str, list[int]] = {dn: [] for dn in dir_names}
        for code, app in merged.items():
            if assigned_dir[code] is None:
                pref_list = prefs.get(code, [])
                if next_choice_idx[code] < len(pref_list):
                    dn = pref_list[next_choice_idx[code]]
                    proposals[dn].append(code)
                    next_choice_idx[code] += 1

        for dn in dir_names:
            if not proposals[dn] and not tentatives[dn]:
                continue
            pool = list(set(tentatives[dn] + proposals[dn]))
            ranked = rank_dir_pool(dn, pool)
            keep = ranked[: dir_quota.get(dn, 0)]
            if set(keep) != set(tentatives[dn]):
                changed = True
            tentatives[dn] = keep

        new_assigned: dict[int, Optional[str]] = {code: None for code in merged.keys()}
        for dn, lst in tentatives.items():
            for code in lst:
                new_assigned[code] = dn
        if new_assigned != assigned_dir:
            changed = True
            assigned_dir = new_assigned

        if all(len(v) == 0 for v in proposals.values()) and not changed:
            break

    accepted_by_dir = {dn: tentatives[dn] for dn in dir_names}
    return assigned_dir, accepted_by_dir


def effective_list_for_direction(
    dir_name: str,
    merged: dict[int, Applicant],
    assigned_dir: dict[int, Optional[str]],
) -> list[tuple[int, int]]:
    candidates: list[tuple[int, int]] = []

    for code, app in merged.items():
        info = app.directions.get(dir_name)
        if not info:
            continue
        pts = info.get("points")
        p_here = info.get("priority")
        if pts is None or p_here is None:
            continue

        assigned = assigned_dir.get(code)
        if assigned is None:
            candidates.append((code, pts))
            continue

        p_assigned = get_priority(app, assigned)
        if p_assigned is not None and p_assigned < p_here:
            continue

        candidates.append((code, pts))

    candidates.sort(key=lambda x: (-x[1], x[0]))
    return candidates


def my_position(
    my_code: int,
    dir_name: str,
    merged: dict[int, Applicant],
    assigned_dir: dict[int, Optional[str]],
    quota: int,
) -> tuple[Optional[int], Optional[int], bool, Optional[int]]:
    eff = effective_list_for_direction(dir_name, merged, assigned_dir)
    idx = None
    my_app = merged.get(my_code)
    my_points = get_points(my_app, dir_name) if my_app else None
    if my_points is None:
        return None, None, False, None

    for i, (code, _) in enumerate(eff):
        if code == my_code:
            idx = i
            break
    if idx is None:
        return None, None, False, my_points

    above = idx
    in_quota = idx < quota
    return idx, above, in_quota, my_points


def main():
    directions = [
        Direction("ИВЧТ", "118", 12),
        Direction("ИФСТ", "156", 29),
        Direction("ПИНФ", "119", 15),
        Direction("ПИНЖ", "120", 15),
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

    assigned_dir, accepted_by_dir = simulate_admissions(merged, directions)

    my_code = int(input("Введите свой код абитуриента: "))
    dir_quota = build_dir_quota_map(directions)

    print(f"\nКвоты по направлениям:")
    for d in directions:
        print(f"- {d.name}: {dir_quota[d.name]} мест")

    print(f"\nСимуляция зачислений...")
    print(f"Итоговое направление для {my_code}: {assigned_dir.get(my_code)}")
    print(
        "\nПозиции по направлениям (после учета чужих более приоритетных зачислений):"
    )
    for d in directions:
        pos, above, in_quota, my_points = my_position(
            my_code, d.name, merged, assigned_dir, dir_quota[d.name]
        )
        if pos is None:
            print(f"- {d.name}: не подавал/нет баллов")
            continue
        print(
            f"- {d.name}: место #{pos+1}, баллы {my_points}, "
            f"квота {dir_quota[d.name]} → {'проходит' if in_quota else 'пока не проходит'}"
        )


if __name__ == "__main__":
    main()
