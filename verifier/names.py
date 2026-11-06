"""Byline checks and the same personal-author selection the tool uses."""

import re

MAX_BYLINE = 10000
MAX_NAME = 200
AUTHOR = "Author"
COLLECTIVE = "CollectiveName"
PMID = re.compile(r"^[1-9][0-9]{0,8}$")


def normalize_author(raw):
    return " ".join(raw.split())


def personal_names(byline):
    return [row["name"] for row in byline if row["authtype"] == AUTHOR]


def input_problem(value):
    """A (kind, message) pair, or None when the PMID can be fetched."""
    return pmid_problem(value.pmid)


def output_problem(output):
    """A (kind, message) pair, or None when coauthor_count can be a count."""
    if type(output.coauthor_count) is not int or output.coauthor_count < 1:
        return ("malformed", "coauthor_count must be at least 1")
    return None


def pmid_problem(raw):
    if raw.strip() == "":
        return ("missing", "pmid is empty")
    if PMID.fullmatch(raw) is None:
        return ("malformed", "pmid is not a PubMed id")
    return None


def byline_problem(raw):
    """A (kind, message) pair, or None when the stored byline can be counted."""
    if type(raw) is not list:
        return ("malformed", "coauthors.json byline is not a list")
    if len(raw) == 0:
        return ("malformed", "coauthors.json byline is empty")
    if len(raw) > MAX_BYLINE:
        return ("malformed", f"coauthors.json byline has more than {MAX_BYLINE} authors")
    for row in raw:
        problem = row_problem(row)
        if problem:
            return problem
    if not personal_names(raw):
        return ("malformed", "coauthors.json lists no personal authors")
    return None


def row_problem(row):
    if type(row) is not dict:
        return ("malformed", "coauthors.json author is not an object")
    name = row.get("name")
    kind = row.get("authtype")
    if type(name) is not str or type(kind) is not str:
        return ("malformed", "coauthors.json author has no name and authtype")
    if any(ord(char) < 32 or ord(char) == 127 for char in name):
        return ("malformed", "coauthors.json author name contains a control character")
    if name == "" or name != normalize_author(name):
        return ("malformed", "coauthors.json author name is empty or not normalized")
    if len(name) > MAX_NAME:
        return ("malformed", f"coauthors.json author name is longer than {MAX_NAME} characters")
    if kind not in (AUTHOR, COLLECTIVE):
        return ("malformed", "coauthors.json author type is not Author or CollectiveName")
    return None
