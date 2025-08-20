from dataclasses import dataclass
from typing import Optional


@dataclass
class Direction:
    name: str
    url_code: str
    avaliable_budget_places: int


@dataclass
class Applicant:
    code: int
    directions: dict[str, dict[str, Optional[int]]]
