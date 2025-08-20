"""Data models for university application analysis."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Direction:
    """Represents a university direction/program.

    Attributes:
        name: Name of the direction
        url_code: URL code used for web scraping
        avaliable_budget_places: Number of available budget places
    """

    name: str
    url_code: str
    avaliable_budget_places: int


@dataclass
class Applicant:
    """Represents an applicant with their application data.

    Attributes:
        code: Unique applicant code
        directions: Dictionary mapping direction names to application info
    """

    code: int
    directions: dict[str, dict[str, Optional[int]]]
