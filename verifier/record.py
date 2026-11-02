"""Read coauthors.json. The other-paper count is checked against this record."""

import json
from pathlib import Path

from .names import union_term, unique_authors

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
    authors = unique_authors(given.authors)
    if data.get("pmid") != given.pmid:
        return ("malformed", "coauthors.json pmid does not match the input")
    if data.get("authors") != authors:
        return ("malformed", "coauthors.json authors do not match the input")
    if data.get("term") != union_term(authors):
        return ("malformed", "coauthors.json term does not match the author list")
    union_count = data.get("union_count")
    source_hits = data.get("source_hits")
    other = data.get("other_papers")
    if type(union_count) is not int or union_count < 1:
        return ("malformed", "coauthors.json union_count must be at least 1")
    if type(source_hits) is not int or source_hits != 1:
        return ("malformed", "coauthors.json source_hits must be 1")
    if type(other) is not int or other < 0:
        return ("malformed", "coauthors.json other_papers must be zero or greater")
    if other != union_count - 1:
        return ("malformed", "coauthors.json other_papers is not union_count minus 1")
    return ("ok", data)
