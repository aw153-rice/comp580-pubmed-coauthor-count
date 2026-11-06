"""The paper's byline: personal authors from one PubMed summary."""

from __future__ import annotations

import os
import re

from contract import CoauthorCountInput, CoauthorCountOutput
from plugin.client import ESUMMARY_URL, TOOL_NAME

MAX_BYLINE = 10000
MAX_NAME = 200
AUTHOR = "Author"
COLLECTIVE = "CollectiveName"
PMID = re.compile(r"^[1-9][0-9]{0,8}$")


def normalize_author(raw: str) -> str:
    return " ".join(raw.split())


def personal_names(byline: list[dict]) -> list[str]:
    return [row["name"] for row in byline if row["authtype"] == AUTHOR]


def count_coauthors(given: CoauthorCountInput, client) -> tuple[CoauthorCountOutput, dict]:
    problem = pmid_problem(given.pmid)
    if problem:
        raise ValueError(problem)
    byline = load_byline(client, given.pmid)
    names = personal_names(byline)
    if not names:
        raise RuntimeError("paper lists no personal authors")
    record = {"pmid": given.pmid, "byline": byline, "coauthor_count": len(names)}
    return CoauthorCountOutput(coauthor_count=len(names)), record


def pmid_problem(raw: str) -> str | None:
    if raw.strip() == "":
        return "pmid is empty"
    if PMID.fullmatch(raw) is None:
        return "pmid is not a PubMed id"
    return None


def load_byline(client, pmid: str) -> list[dict]:
    body = client.get_json(
        ESUMMARY_URL,
        ncbi_params({"db": "pubmed", "id": pmid, "retmode": "json", "version": "2.0"}),
    )
    if body.get("error"):
        raise RuntimeError(f"ESummary error: {body['error']}")
    result = body.get("result")
    if not isinstance(result, dict):
        raise TypeError("ESummary returned no result")
    uids = result.get("uids")
    if not isinstance(uids, list):
        raise TypeError("ESummary returned no uids")
    parsed = [as_pmid(raw) for raw in uids]
    if parsed != [pmid]:
        raise RuntimeError("ESummary did not return that paper")
    record = result.get(pmid)
    if not isinstance(record, dict):
        raise TypeError("ESummary returned a record that is not an object")
    if record.get("error"):
        raise RuntimeError(f"ESummary error: {record['error']}")
    return checked_byline(record.get("authors"))


def checked_byline(raw) -> list[dict]:
    if not isinstance(raw, list):
        raise TypeError("ESummary returned no author list")
    if len(raw) == 0:
        raise RuntimeError("paper lists no authors")
    if len(raw) > MAX_BYLINE:
        raise RuntimeError(f"paper lists more than {MAX_BYLINE} authors")
    byline = []
    for row in raw:
        if not isinstance(row, dict):
            raise TypeError("ESummary author is not an object")
        name = row.get("name")
        kind = row.get("authtype")
        if not isinstance(name, str) or not isinstance(kind, str):
            raise TypeError("ESummary author has no name and authtype")
        if any(ord(char) < 32 or ord(char) == 127 for char in name):
            raise RuntimeError("ESummary author name contains a control character")
        normalized = normalize_author(name)
        if normalized == "":
            raise RuntimeError("ESummary author name is empty")
        if len(normalized) > MAX_NAME:
            raise RuntimeError(f"ESummary author name is longer than {MAX_NAME} characters")
        if kind not in (AUTHOR, COLLECTIVE):
            raise RuntimeError("ESummary author type is not Author or CollectiveName")
        byline.append({"name": normalized, "authtype": kind})
    return byline


def ncbi_params(extra: dict[str, str]) -> dict[str, str]:
    params = {"tool": TOOL_NAME, **extra}
    email = os.environ.get("NCBI_EMAIL", "").strip()
    api_key = os.environ.get("NCBI_API_KEY", "").strip()
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key
    return params


def as_pmid(raw) -> str:
    if type(raw) is bool or not isinstance(raw, int | str):
        raise TypeError(f"invalid pmid: {raw!r}")
    text = str(raw).strip()
    if PMID.fullmatch(text) is None:
        raise RuntimeError(f"invalid pmid: {raw!r}")
    return text
