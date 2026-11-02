"""Author-list checks and the same term the tool sends to PubMed."""

import re

MAX_AUTHORS = 20
MAX_NAME = 80
PMID = re.compile(r"^[1-9][0-9]{0,8}$")
AUTHOR = re.compile(r"^[A-Za-z][A-Za-z .'\-]{0,79}$")


def normalize_author(raw):
    return " ".join(raw.split())


def unique_authors(names):
    chosen = []
    seen = set()
    for raw in names:
        name = normalize_author(raw)
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        chosen.append(name)
    return chosen


def union_term(names):
    clauses = [f'"{name}"[Author]' for name in names]
    if len(clauses) == 1:
        return clauses[0]
    return "(" + " OR ".join(clauses) + ")"


def input_problem(value):
    """A (kind, message) pair, or None when the PMID and author list can be searched."""
    problem = pmid_problem(value.pmid)
    if problem:
        return problem
    if len(value.authors) == 0:
        return ("missing", "authors is empty")
    if len(value.authors) > MAX_AUTHORS:
        return ("malformed", f"authors has more than {MAX_AUTHORS} names")
    for raw in value.authors:
        problem = author_problem(raw)
        if problem:
            return problem
    return None


def output_problem(output):
    """A (kind, message) pair, or None when other_papers can be a count."""
    if type(output.other_papers) is not int or output.other_papers < 0:
        return ("malformed", "other_papers must be zero or greater")
    return None


def pmid_problem(raw):
    if raw.strip() == "":
        return ("missing", "pmid is empty")
    if PMID.fullmatch(raw) is None:
        return ("malformed", "pmid is not a PubMed id")
    return None


def author_problem(raw):
    if raw.strip() == "":
        return ("missing", "author is empty")
    if any(ord(char) < 32 or ord(char) == 127 or ord(char) > 127 for char in raw):
        return ("malformed", "author contains a character an author name cannot contain")
    name = normalize_author(raw)
    if len(name) > MAX_NAME:
        return ("malformed", f"author is longer than {MAX_NAME} characters")
    if AUTHOR.fullmatch(name) is None:
        return ("malformed", "author is not an author name")
    return None
