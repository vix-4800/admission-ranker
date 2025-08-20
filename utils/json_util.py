"""Utilities for JSON serialization of applicant data."""

import json
import os
from dataclasses import asdict

from models import Applicant


def save_to_json(merged: dict[int, Applicant], filename: str = "applicants.json"):
    """Save applicant data to JSON file.

    Args:
        merged: Dictionary of applicants indexed by code
        filename: Output filename (default: applicants.json)
    """
    data = {code: asdict(app) for code, app in merged.items()}
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_from_json(filename: str = "applicants.json") -> dict[int, Applicant]:
    """Load applicant data from JSON file.

    Args:
        filename: Input filename (default: applicants.json)

    Returns:
        Dictionary of applicants indexed by code
    """
    if not os.path.exists(filename):
        return {}

    with open(filename, "r", encoding="utf-8") as f:
        raw = json.load(f)

    merged: dict[int, Applicant] = {}
    for code, rec in raw.items():
        merged[int(code)] = Applicant(
            code=int(code), directions=rec.get("directions", {})
        )
    return merged
