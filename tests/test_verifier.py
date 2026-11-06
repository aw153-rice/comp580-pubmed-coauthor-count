"""Verifier cases: correct, wrong, missing, malformed, and boundary."""

import json
from pathlib import Path

from slimconfig import build_output

import verifier
from contract import CoauthorCountInput, CoauthorCountOutput
from verifier.names import union_term, unique_authors

PMID = "100"
AUTHORS = ["Smith JA", "Doe JB"]
TERM = '("Smith JA"[Author] OR "Doe JB"[Author])'


def given(pmid=PMID, authors=None):
    return build_output({"pmid": pmid, "authors": AUTHORS if authors is None else authors}, CoauthorCountInput)


def made(other_papers):
    return build_output({"other_papers": other_papers}, CoauthorCountOutput)


def record(pmid=PMID, authors=None, union_count=5, source_hits=1, other_papers=None, term=None):
    names = unique_authors(AUTHORS if authors is None else authors)
    payload = {
        "pmid": pmid,
        "authors": names,
        "term": TERM if term is None else term,
        "union_count": union_count,
        "source_hits": source_hits,
        "other_papers": union_count - 1 if other_papers is None else other_papers,
    }
    if term is None:
        payload["term"] = union_term(names)
    return payload


def write_record(workspace: Path, payload) -> None:
    (workspace / "coauthors.json").write_text(json.dumps(payload), encoding="utf-8")


def test_verify_input_accepts_the_sample():
    assert verifier.verify_input("count_coauthor_papers", given())["valid"] is True
    assert verifier.verify_input("pin_coauthor_count", given())["valid"] is True


def test_verify_input_rejects_blank_pmid_and_authors():
    blank_pmid = verifier.verify_input("count_coauthor_papers", given(pmid="   "))
    assert blank_pmid["valid"] is False
    assert "empty" in blank_pmid["message"]
    empty_authors = verifier.verify_input("pin_coauthor_count", given(authors=[]))
    assert empty_authors["valid"] is False
    assert "authors is empty" in empty_authors["message"]
    blank_name = verifier.verify_input("count_coauthor_papers", given(authors=["Smith JA", " "]))
    assert blank_name["valid"] is False
    assert "author is empty" in blank_name["message"]


def test_verify_input_rejects_malformed_pmid_and_names():
    leading = verifier.verify_input("count_coauthor_papers", given(pmid="0100"))
    assert leading["valid"] is False
    assert "PubMed id" in leading["message"]
    too_long = verifier.verify_input("pin_coauthor_count", given(pmid="1234567890"))
    assert too_long["valid"] is False
    assert "PubMed id" in too_long["message"]
    digit = verifier.verify_input("count_coauthor_papers", given(authors=["Smith 3"]))
    assert digit["valid"] is False
    assert "author name" in digit["message"]
    bracket = verifier.verify_input("pin_coauthor_count", given(authors=["Smith[Author]"]))
    assert bracket["valid"] is False
    assert "author name" in bracket["message"]
    accent = verifier.verify_input("count_coauthor_papers", given(authors=["José M"]))
    assert accent["valid"] is False
    assert "cannot contain" in accent["message"]
    oversized = verifier.verify_input("count_coauthor_papers", given(authors=["A"] * 21))
    assert oversized["valid"] is False
    assert "more than 20" in oversized["message"]
    longer = verifier.verify_input("pin_coauthor_count", given(authors=["A" * 81]))
    assert longer["valid"] is False
    assert "80" in longer["message"]


def test_verify_input_accepts_boundary_names_and_pmids():
    assert verifier.verify_input("count_coauthor_papers", given(pmid="1", authors=["A"]))["valid"] is True
    assert verifier.verify_input("pin_coauthor_count", given(pmid="123456789", authors=["A" + ("b" * 79)]))["valid"] is True
    twenty = [f"Author {chr(65 + index)}" for index in range(20)]
    assert verifier.verify_input("count_coauthor_papers", given(authors=twenty))["valid"] is True
    assert verifier.verify_input("pin_coauthor_count", given(authors=["O'Brien K", "Garcia-Lopez M"]))["valid"] is True


def test_verify_output_accepts_the_count(tmp_path: Path):
    write_record(tmp_path, record())
    verdict = verifier.verify_output("count_coauthor_papers", given(), made(4), str(tmp_path))
    assert verdict["valid"] is True
    assert verdict["score"] == 1.0


def test_verify_output_rejects_a_count_that_keeps_or_drops_a_paper(tmp_path: Path):
    write_record(tmp_path, record())
    kept = verifier.verify_output("count_coauthor_papers", given(), made(5), str(tmp_path))
    assert kept["valid"] is False
    assert kept["score"] == 0.0
    assert "coauthors.json" in kept["message"]
    dropped = verifier.verify_output("count_coauthor_papers", given(), made(3), str(tmp_path))
    assert dropped["valid"] is False
    assert "coauthors.json" in dropped["message"]


def test_verify_output_rejects_a_missing_file(tmp_path: Path):
    verdict = verifier.verify_output("count_coauthor_papers", given(), made(4), str(tmp_path))
    assert verdict["valid"] is False
    assert "missing" in verdict["message"]


def test_verify_output_rejects_malformed_json(tmp_path: Path):
    (tmp_path / "coauthors.json").write_text("{", encoding="utf-8")
    verdict = verifier.verify_output("count_coauthor_papers", given(), made(4), str(tmp_path))
    assert verdict["valid"] is False
    assert "JSON" in verdict["message"]
    (tmp_path / "coauthors.json").write_text("[]", encoding="utf-8")
    verdict = verifier.verify_output("count_coauthor_papers", given(), made(4), str(tmp_path))
    assert verdict["valid"] is False
    assert "not an object" in verdict["message"]


def test_verify_output_rejects_a_record_that_does_not_add_up(tmp_path: Path):
    payload = record(other_papers=4, union_count=10)
    write_record(tmp_path, payload)
    verdict = verifier.verify_output("count_coauthor_papers", given(), made(4), str(tmp_path))
    assert verdict["valid"] is False
    assert "union_count minus 1" in verdict["message"]
    payload = record(source_hits=0)
    write_record(tmp_path, payload)
    hits = verifier.verify_output("count_coauthor_papers", given(), made(4), str(tmp_path))
    assert hits["valid"] is False
    assert "source_hits" in hits["message"]
    payload = record()
    payload["source_hits"] = True
    write_record(tmp_path, payload)
    flagged = verifier.verify_output("count_coauthor_papers", given(), made(4), str(tmp_path))
    assert flagged["valid"] is False
    assert "source_hits" in flagged["message"]


def test_verify_output_rejects_a_term_or_author_list_that_does_not_match(tmp_path: Path):
    payload = record(term='"Smith JA"[Author]')
    write_record(tmp_path, payload)
    verdict = verifier.verify_output("count_coauthor_papers", given(), made(4), str(tmp_path))
    assert verdict["valid"] is False
    assert "term" in verdict["message"]
    payload = record()
    payload["authors"] = ["Doe JB", "Smith JA"]
    write_record(tmp_path, payload)
    swapped = verifier.verify_output("count_coauthor_papers", given(), made(4), str(tmp_path))
    assert swapped["valid"] is False
    assert "authors" in swapped["message"]
    payload = record()
    payload["pmid"] = "101"
    write_record(tmp_path, payload)
    pmid = verifier.verify_output("count_coauthor_papers", given(), made(4), str(tmp_path))
    assert pmid["valid"] is False
    assert "pmid" in pmid["message"]


def test_verify_output_rejects_a_negative_count(tmp_path: Path):
    write_record(tmp_path, record())
    verdict = verifier.verify_output("count_coauthor_papers", given(), made(-1), str(tmp_path))
    assert verdict["valid"] is False
    assert "zero or greater" in verdict["message"]


def test_pin_output_does_not_need_a_file(tmp_path: Path):
    verdict = verifier.verify_output("pin_coauthor_count", given(), made(4), str(tmp_path))
    assert verdict["valid"] is True


def test_pin_output_rejects_a_negative_count_and_a_bad_pmid(tmp_path: Path):
    negative = verifier.verify_output("pin_coauthor_count", given(), made(-1), str(tmp_path))
    assert negative["valid"] is False
    assert "zero or greater" in negative["message"]
    pmid = verifier.verify_output("pin_coauthor_count", given(pmid="0"), made(4), str(tmp_path))
    assert pmid["valid"] is False
    assert "PubMed id" in pmid["message"]


def test_verify_task_accepts_the_reference(tmp_path: Path):
    write_record(tmp_path, record())
    verdict = verifier.verify_task("pubmed-coauthor-paper-count", given(), made(4), made(4), str(tmp_path))
    assert verdict["valid"] is True
    assert verdict["score"] == 1.0


def test_verify_task_rejects_a_wrong_count(tmp_path: Path):
    write_record(tmp_path, record())
    wrong = verifier.verify_task("pubmed-coauthor-paper-count", given(), made(5), made(4), str(tmp_path))
    assert wrong["valid"] is False
    assert "reference" in wrong["message"]


def test_verify_task_accepts_the_workspace_when_the_reference_is_absent(tmp_path: Path):
    write_record(tmp_path, record())
    verdict = verifier.verify_task("pubmed-coauthor-paper-count", given(), made(4), None, str(tmp_path))
    assert verdict["valid"] is True
    absent = verifier.verify_task("pubmed-coauthor-paper-count", given(), made(4), None, str(tmp_path / "empty"))
    assert absent["valid"] is False
    assert "missing" in absent["message"]


def test_verify_task_rejects_a_file_that_does_not_support_the_reference(tmp_path: Path):
    write_record(tmp_path, record())
    (tmp_path / "coauthors.json").unlink()
    missing = verifier.verify_task("pubmed-coauthor-paper-count", given(), made(4), made(4), str(tmp_path))
    assert missing["valid"] is False
    assert "coauthors.json is missing" in missing["message"]
    write_record(tmp_path, record(union_count=6, other_papers=5))
    unsupported = verifier.verify_task("pubmed-coauthor-paper-count", given(), made(4), made(4), str(tmp_path))
    assert unsupported["valid"] is False
    assert "does not support" in unsupported["message"]


def test_verify_task_rejects_a_malformed_reference(tmp_path: Path):
    write_record(tmp_path, record())
    verdict = verifier.verify_task("pubmed-coauthor-paper-count", given(), made(4), made(-1), str(tmp_path))
    assert verdict["valid"] is False
    assert "zero or greater" in verdict["message"]
    pmid = verifier.verify_task(
        "pubmed-coauthor-paper-count",
        given(pmid="0100"),
        made(4),
        made(4),
        str(tmp_path),
    )
    assert pmid["valid"] is False
    assert "PubMed id" in pmid["message"]


def test_boundary_zero_other_papers_and_a_repeated_author_are_valid(tmp_path: Path):
    solo = record(pmid="7", authors=["Solo AB"], union_count=1, other_papers=0)
    write_record(tmp_path, solo)
    empty = verifier.verify_task(
        "pubmed-coauthor-paper-count",
        given(pmid="7", authors=["Solo AB"]),
        made(0),
        made(0),
        str(tmp_path),
    )
    assert empty["valid"] is True
    repeated = ["Smith JA", "smith ja", "Doe JB"]
    payload = record(authors=repeated, union_count=5, other_papers=4)
    write_record(tmp_path, payload)
    verdict = verifier.verify_task(
        "pubmed-coauthor-paper-count",
        given(authors=repeated),
        made(4),
        made(4),
        str(tmp_path),
    )
    assert verdict["valid"] is True
    assert payload["authors"] == ["Smith JA", "Doe JB"]
