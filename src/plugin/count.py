"""The coauthor union: one PubMed count, excluding the source PMID."""

from __future__ import annotations

import os
import re

from contract import CoauthorCountInput, CoauthorCountOutput
from plugin.client import ESEARCH_URL, TOOL_NAME

MAX_AUTHORS = 20
MAX_NAME = 80
PMID = re.compile(r"^[1-9][0-9]{0,8}$")
AUTHOR = re.compile(r"^[A-Za-z][A-Za-z .'\-]{0,79}$")


def normalize_author(raw: str) -> str:
    return " ".join(raw.split())


def unique_authors(names: list[str]) -> list[str]:
    chosen = []
    seen: set[str] = set()
    for raw in names:
        name = normalize_author(raw)
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        chosen.append(name)
    return chosen


def union_term(names: list[str]) -> str:
    clauses = [f'"{name}"[Author]' for name in names]
    if len(clauses) == 1:
        return clauses[0]
    return "(" + " OR ".join(clauses) + ")"


def membership_term(term: str, pmid: str) -> str:
    return f"{term} AND {pmid}[uid]"


def count_papers(given: CoauthorCountInput, client) -> tuple[CoauthorCountOutput, dict]:
    check_input(given)
    authors = unique_authors(given.authors)
    term = union_term(authors)
    union_count = esearch_count(client, term)
    source_hits = esearch_count(client, membership_term(term, given.pmid))
    if source_hits != 1 or union_count < 1:
        raise RuntimeError("source paper is not one hit of the coauthor search")
    other = union_count - 1
    record = {
        "pmid": given.pmid,
        "authors": authors,
        "term": term,
        "union_count": union_count,
        "source_hits": source_hits,
        "other_papers": other,
    }
    return CoauthorCountOutput(other_papers=other), record


def check_input(given: CoauthorCountInput) -> None:
    problem = pmid_problem(given.pmid)
    if problem:
        raise ValueError(problem)
    if len(given.authors) == 0:
        raise ValueError("authors is empty")
    if len(given.authors) > MAX_AUTHORS:
        raise ValueError(f"authors has more than {MAX_AUTHORS} names")
    for raw in given.authors:
        problem = author_problem(raw)
        if problem:
            raise ValueError(problem)


def pmid_problem(raw: str) -> str | None:
    if raw.strip() == "":
        return "pmid is empty"
    if PMID.fullmatch(raw) is None:
        return "pmid is not a PubMed id"
    return None


def author_problem(raw: str) -> str | None:
    if raw.strip() == "":
        return "author is empty"
    if any(ord(char) < 32 or ord(char) == 127 or ord(char) > 127 for char in raw):
        return "author contains a character an author name cannot contain"
    name = normalize_author(raw)
    if len(name) > MAX_NAME:
        return f"author is longer than {MAX_NAME} characters"
    if AUTHOR.fullmatch(name) is None:
        return "author is not an author name"
    return None


def esearch_count(client, term: str) -> int:
    body = client.get_json(
        ESEARCH_URL,
        ncbi_params(
            {
                "db": "pubmed",
                "term": term,
                "retmode": "json",
                "retmax": "0",
                "retstart": "0",
            }
        ),
    )
    if body.get("error"):
        raise RuntimeError(f"ESearch error: {body['error']}")
    result = body.get("esearchresult")
    if not isinstance(result, dict):
        raise TypeError("ESearch returned no esearchresult")
    if result.get("ERROR") or result.get("errorlist"):
        raise RuntimeError(f"ESearch error: {result.get('ERROR') or result.get('errorlist')}")
    if "count" not in result:
        raise TypeError("ESearch returned no count")
    count = as_count(result.get("count"))
    idlist = result.get("idlist")
    if not isinstance(idlist, list):
        raise TypeError("ESearch returned no id list")
    return count


def ncbi_params(extra: dict[str, str]) -> dict[str, str]:
    params = {"tool": TOOL_NAME, **extra}
    email = os.environ.get("NCBI_EMAIL", "").strip()
    api_key = os.environ.get("NCBI_API_KEY", "").strip()
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key
    return params


def as_count(raw) -> int:
    if type(raw) is bool or not isinstance(raw, int | str):
        raise TypeError("ESearch returned no count")
    try:
        count = int(raw)
    except ValueError as error:
        raise RuntimeError("ESearch returned no count") from error
    if count < 0:
        raise RuntimeError("ESearch returned no count")
    return count
