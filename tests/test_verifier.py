"""Verifier cases: correct, wrong, missing, malformed, and boundary."""

import json
from pathlib import Path

from slimconfig import build_output

import verifier
from contract import CoauthorCountInput, CoauthorCountOutput

PMID = "100"
BYLINE = [
    {"name": "Smith JA", "authtype": "Author"},
    {"name": "COVID Consortium", "authtype": "CollectiveName"},
    {"name": "Doe JB", "authtype": "Author"},
]


def given(pmid=PMID):
    return build_output({"pmid": pmid}, CoauthorCountInput)


def made(coauthor_count):
    return build_output({"coauthor_count": coauthor_count}, CoauthorCountOutput)


def record(pmid=PMID, byline=None, coauthor_count=2):
    return {"pmid": pmid, "byline": BYLINE if byline is None else byline, "coauthor_count": coauthor_count}


def write_record(workspace: Path, payload) -> None:
    (workspace / "coauthors.json").write_text(json.dumps(payload), encoding="utf-8")


def test_verify_input_accepts_the_sample():
    assert verifier.verify_input("count_paper_coauthors", given())["valid"] is True
    assert verifier.verify_input("pin_paper_coauthors", given())["valid"] is True


def test_verify_input_rejects_a_blank_pmid():
    blank = verifier.verify_input("count_paper_coauthors", given(pmid="   "))
    assert blank["valid"] is False
    assert "empty" in blank["message"]
    spaces = verifier.verify_input("pin_paper_coauthors", given(pmid=""))
    assert spaces["valid"] is False
    assert "empty" in spaces["message"]


def test_verify_input_rejects_a_malformed_pmid():
    leading = verifier.verify_input("count_paper_coauthors", given(pmid="0100"))
    assert leading["valid"] is False
    assert "PubMed id" in leading["message"]
    too_long = verifier.verify_input("pin_paper_coauthors", given(pmid="1234567890"))
    assert too_long["valid"] is False
    assert "PubMed id" in too_long["message"]
    zero = verifier.verify_input("count_paper_coauthors", given(pmid="0"))
    assert zero["valid"] is False
    assert "PubMed id" in zero["message"]


def test_verify_input_accepts_boundary_pmids():
    assert verifier.verify_input("count_paper_coauthors", given(pmid="1"))["valid"] is True
    assert verifier.verify_input("pin_paper_coauthors", given(pmid="123456789"))["valid"] is True


def test_verify_output_accepts_the_count(tmp_path: Path):
    write_record(tmp_path, record())
    verdict = verifier.verify_output("count_paper_coauthors", given(), made(2), str(tmp_path))
    assert verdict["valid"] is True
    assert verdict["score"] == 1.0


def test_verify_output_rejects_a_count_that_keeps_or_drops_an_author(tmp_path: Path):
    write_record(tmp_path, record())
    kept = verifier.verify_output("count_paper_coauthors", given(), made(3), str(tmp_path))
    assert kept["valid"] is False
    assert kept["score"] == 0.0
    assert "coauthors.json" in kept["message"]
    dropped = verifier.verify_output("count_paper_coauthors", given(), made(1), str(tmp_path))
    assert dropped["valid"] is False
    assert "coauthors.json" in dropped["message"]


def test_verify_output_rejects_a_missing_file(tmp_path: Path):
    verdict = verifier.verify_output("count_paper_coauthors", given(), made(2), str(tmp_path))
    assert verdict["valid"] is False
    assert "missing" in verdict["message"]


def test_verify_output_rejects_malformed_json(tmp_path: Path):
    (tmp_path / "coauthors.json").write_text("{", encoding="utf-8")
    verdict = verifier.verify_output("count_paper_coauthors", given(), made(2), str(tmp_path))
    assert verdict["valid"] is False
    assert "JSON" in verdict["message"]
    (tmp_path / "coauthors.json").write_text("[]", encoding="utf-8")
    verdict = verifier.verify_output("count_paper_coauthors", given(), made(2), str(tmp_path))
    assert verdict["valid"] is False
    assert "not an object" in verdict["message"]


def test_verify_output_rejects_a_count_that_does_not_match_the_byline(tmp_path: Path):
    write_record(tmp_path, record(coauthor_count=3))
    verdict = verifier.verify_output("count_paper_coauthors", given(), made(3), str(tmp_path))
    assert verdict["valid"] is False
    assert "personal authors" in verdict["message"]
    payload = record()
    payload["coauthor_count"] = True
    write_record(tmp_path, payload)
    flagged = verifier.verify_output("count_paper_coauthors", given(), made(2), str(tmp_path))
    assert flagged["valid"] is False
    assert "at least 1" in flagged["message"]


def test_verify_output_rejects_a_byline_that_cannot_be_counted(tmp_path: Path):
    write_record(tmp_path, record(byline=[{"name": "smith ja", "authtype": "author"}]))
    kind = verifier.verify_output("count_paper_coauthors", given(), made(2), str(tmp_path))
    assert kind["valid"] is False
    assert "author type" in kind["message"]
    write_record(tmp_path, record(byline=[{"name": "  Smith JA", "authtype": "Author"}], coauthor_count=1))
    spaced = verifier.verify_output("count_paper_coauthors", given(), made(1), str(tmp_path))
    assert spaced["valid"] is False
    assert "not normalized" in spaced["message"]
    payload = record()
    payload["pmid"] = "101"
    write_record(tmp_path, payload)
    pmid = verifier.verify_output("count_paper_coauthors", given(), made(2), str(tmp_path))
    assert pmid["valid"] is False
    assert "pmid" in pmid["message"]
    write_record(tmp_path, record(byline=[], coauthor_count=1))
    empty = verifier.verify_output("count_paper_coauthors", given(), made(1), str(tmp_path))
    assert empty["valid"] is False
    assert "empty" in empty["message"]
    group = [{"name": "COVID Consortium", "authtype": "CollectiveName"}]
    write_record(tmp_path, record(byline=group, coauthor_count=1))
    collective = verifier.verify_output("count_paper_coauthors", given(), made(1), str(tmp_path))
    assert collective["valid"] is False
    assert "no personal authors" in collective["message"]


def test_verify_output_rejects_a_count_below_one(tmp_path: Path):
    write_record(tmp_path, record())
    verdict = verifier.verify_output("count_paper_coauthors", given(), made(0), str(tmp_path))
    assert verdict["valid"] is False
    assert "at least 1" in verdict["message"]
    negative = verifier.verify_output("count_paper_coauthors", given(), made(-1), str(tmp_path))
    assert negative["valid"] is False
    assert "at least 1" in negative["message"]


def test_pin_output_does_not_need_a_file(tmp_path: Path):
    verdict = verifier.verify_output("pin_paper_coauthors", given(), made(2), str(tmp_path))
    assert verdict["valid"] is True


def test_pin_output_rejects_a_zero_count_and_a_bad_pmid(tmp_path: Path):
    zero = verifier.verify_output("pin_paper_coauthors", given(), made(0), str(tmp_path))
    assert zero["valid"] is False
    assert "at least 1" in zero["message"]
    pmid = verifier.verify_output("pin_paper_coauthors", given(pmid="0"), made(2), str(tmp_path))
    assert pmid["valid"] is False
    assert "PubMed id" in pmid["message"]


def test_verify_task_accepts_the_reference(tmp_path: Path):
    write_record(tmp_path, record())
    verdict = verifier.verify_task("pubmed-coauthor-paper-count", given(), made(2), made(2), str(tmp_path))
    assert verdict["valid"] is True
    assert verdict["score"] == 1.0


def test_verify_task_rejects_a_wrong_count(tmp_path: Path):
    write_record(tmp_path, record())
    wrong = verifier.verify_task("pubmed-coauthor-paper-count", given(), made(3), made(2), str(tmp_path))
    assert wrong["valid"] is False
    assert "reference" in wrong["message"]


def test_verify_task_accepts_the_workspace_when_the_reference_is_absent(tmp_path: Path):
    write_record(tmp_path, record())
    verdict = verifier.verify_task("pubmed-coauthor-paper-count", given(), made(2), None, str(tmp_path))
    assert verdict["valid"] is True
    absent = verifier.verify_task("pubmed-coauthor-paper-count", given(), made(2), None, str(tmp_path / "empty"))
    assert absent["valid"] is False
    assert "missing" in absent["message"]


def test_verify_task_rejects_a_file_that_does_not_support_the_reference(tmp_path: Path):
    write_record(tmp_path, record())
    (tmp_path / "coauthors.json").unlink()
    missing = verifier.verify_task("pubmed-coauthor-paper-count", given(), made(2), made(2), str(tmp_path))
    assert missing["valid"] is False
    assert "coauthors.json is missing" in missing["message"]
    solo = [{"name": "Smith JA", "authtype": "Author"}]
    write_record(tmp_path, record(byline=solo, coauthor_count=1))
    unsupported = verifier.verify_task("pubmed-coauthor-paper-count", given(), made(2), made(2), str(tmp_path))
    assert unsupported["valid"] is False
    assert "does not support" in unsupported["message"]


def test_verify_task_rejects_a_malformed_reference(tmp_path: Path):
    write_record(tmp_path, record())
    verdict = verifier.verify_task("pubmed-coauthor-paper-count", given(), made(2), made(0), str(tmp_path))
    assert verdict["valid"] is False
    assert "at least 1" in verdict["message"]
    pmid = verifier.verify_task(
        "pubmed-coauthor-paper-count",
        given(pmid="0100"),
        made(2),
        made(2),
        str(tmp_path),
    )
    assert pmid["valid"] is False
    assert "PubMed id" in pmid["message"]


def test_boundary_one_author_and_a_repeated_name_are_valid(tmp_path: Path):
    solo = [{"name": "Solo AB", "authtype": "Author"}]
    write_record(tmp_path, record(pmid="7", byline=solo, coauthor_count=1))
    one = verifier.verify_task(
        "pubmed-coauthor-paper-count",
        given(pmid="7"),
        made(1),
        made(1),
        str(tmp_path),
    )
    assert one["valid"] is True
    repeated = [
        {"name": "Smith JA", "authtype": "Author"},
        {"name": "Smith JA", "authtype": "Author"},
    ]
    write_record(tmp_path, record(byline=repeated, coauthor_count=2))
    verdict = verifier.verify_task(
        "pubmed-coauthor-paper-count",
        given(),
        made(2),
        made(2),
        str(tmp_path),
    )
    assert verdict["valid"] is True
    long_name = "Á" + ("é" * 199)
    write_record(tmp_path, record(pmid="1", byline=[{"name": long_name, "authtype": "Author"}], coauthor_count=1))
    long = verifier.verify_task(
        "pubmed-coauthor-paper-count",
        given(pmid="1"),
        made(1),
        None,
        str(tmp_path),
    )
    assert long["valid"] is True
