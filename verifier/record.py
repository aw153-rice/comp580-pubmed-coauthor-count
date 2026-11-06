"""Read coauthors.json. The coauthor count is checked against this record."""

import json
from pathlib import Path

from .names import byline_problem, personal_names

FILE_NAME = "coauthors.json"


def load_record(workspace, given):
    """Return ("ok", record), or ("missing"|"malformed", message)."""
    path = Path(workspace) / FILE_NAME
    if not path.is_file():
        return ("missing", "coauthors.json is missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ("malformed", "coauthors.json is not JSON")
    if type(data) is not dict:
        return ("malformed", "coauthors.json is not an object")
    if data.get("pmid") != given.pmid:
        return ("malformed", "coauthors.json pmid does not match the input")
    problem = byline_problem(data.get("byline"))
    if problem:
        return problem
    count = data.get("coauthor_count")
    if type(count) is not int or count < 1:
        return ("malformed", "coauthors.json coauthor_count must be at least 1")
    if count != len(personal_names(data["byline"])):
        return ("malformed", "coauthors.json coauthor_count is not the number of personal authors")
    return ("ok", data)
