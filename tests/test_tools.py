"""Tool tests. The HTTP client is a fake, so nothing here opens a socket."""

import json
from pathlib import Path

import httpx
import pytest
from slimconfig import build_output

from contract import CoauthorCountInput
from plugin.client import ESEARCH_URL, HttpxClient, set_client
from plugin.count import membership_term, union_term, unique_authors
from plugin.papers import COAUTHORS_FILE, count_coauthor_papers
from plugin.pin import pin_coauthor_count
from verifier.names import union_term as check_term
from verifier.names import unique_authors as check_authors

PMID = "100"
AUTHORS = ["Smith JA", "Doe JB"]


class FakeClient:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def get_json(self, url, params):
        self.calls.append((url, dict(params)))
        body = self.handler(url, params)
        if not isinstance(body, dict):
            raise TypeError(type(body))
        return body


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    monkeypatch.delenv("NCBI_EMAIL", raising=False)
    holder = {}

    def install(handler):
        client = FakeClient(handler)
        holder["client"] = client
        set_client(client)
        return client

    yield install
    set_client(None)


def given(pmid=PMID, authors=None):
    return build_output({"pmid": pmid, "authors": AUTHORS if authors is None else authors}, CoauthorCountInput)


def hits(union, source):
    def handler(url, params):
        if url != ESEARCH_URL:
            raise AssertionError(url)
        assert params["db"] == "pubmed"
        assert params["retmode"] == "json"
        assert params["retmax"] == "0"
        assert params["retstart"] == "0"
        count = source if "[uid]" in params["term"] else union
        return {"esearchresult": {"count": str(count), "idlist": []}}

    return handler


def test_counts_other_papers_and_writes_the_record(fake, tmp_path: Path):
    client = fake(hits(5, 1))
    output = count_coauthor_papers(given(), tmp_path)
    assert output.other_papers == 4
    assert [url for url, _params in client.calls] == [ESEARCH_URL, ESEARCH_URL]
    term = '("Smith JA"[Author] OR "Doe JB"[Author])'
    assert client.calls[0][1]["term"] == term
    assert client.calls[1][1]["term"] == f"{term} AND 100[uid]"
    saved = json.loads((tmp_path / COAUTHORS_FILE).read_text(encoding="utf-8"))
    assert saved == {
        "pmid": "100",
        "authors": ["Smith JA", "Doe JB"],
        "term": term,
        "union_count": 5,
        "source_hits": 1,
        "other_papers": 4,
    }


def test_pin_matches_the_tool_and_writes_nothing(fake, tmp_path: Path):
    fake(hits(5, 1))
    pinned = pin_coauthor_count(given(), tmp_path)
    assert not (tmp_path / COAUTHORS_FILE).exists()
    assert pinned.other_papers == count_coauthor_papers(given(), tmp_path).other_papers


def test_one_author_with_no_other_papers_returns_zero(fake, tmp_path: Path):
    client = fake(hits(1, 1))
    output = count_coauthor_papers(given(pmid="7", authors=["Solo AB"]), tmp_path)
    assert output.other_papers == 0
    assert client.calls[0][1]["term"] == '"Solo AB"[Author]'
    assert client.calls[1][1]["term"] == '"Solo AB"[Author] AND 7[uid]'
    saved = json.loads((tmp_path / COAUTHORS_FILE).read_text(encoding="utf-8"))
    assert saved["union_count"] == 1
    assert saved["other_papers"] == 0


def test_a_repeated_author_is_searched_once(fake, tmp_path: Path):
    client = fake(hits(3, 1))
    authors = ["  Smith   JA ", "smith ja", "Doe JB"]
    output = count_coauthor_papers(given(authors=authors), tmp_path)
    assert output.other_papers == 2
    assert len(client.calls) == 2
    assert client.calls[0][1]["term"] == '("Smith JA"[Author] OR "Doe JB"[Author])'
    saved = json.loads((tmp_path / COAUTHORS_FILE).read_text(encoding="utf-8"))
    assert saved["authors"] == ["Smith JA", "Doe JB"]


def test_apostrophe_and_hyphen_stay_inside_the_quotes(fake, tmp_path: Path):
    client = fake(hits(2, 1))
    authors = ["O'Brien K", "Garcia-Lopez M"]
    count_coauthor_papers(given(authors=authors), tmp_path)
    assert client.calls[0][1]["term"] == '("O\'Brien K"[Author] OR "Garcia-Lopez M"[Author])'


def test_twenty_names_are_accepted_and_twenty_one_raises(fake, tmp_path: Path):
    client = fake(hits(20, 1))
    twenty = [f"Author {chr(65 + index)}" for index in range(20)]
    output = count_coauthor_papers(given(authors=twenty), tmp_path)
    assert output.other_papers == 19
    assert len(client.calls) == 2
    saved = (tmp_path / COAUTHORS_FILE).read_text(encoding="utf-8")
    client.calls.clear()
    with pytest.raises(ValueError, match="more than 20"):
        count_coauthor_papers(given(authors=[*twenty, "Author U"]), tmp_path)
    assert client.calls == []
    assert (tmp_path / COAUTHORS_FILE).read_text(encoding="utf-8") == saved


def test_a_bad_list_raises_before_any_call_or_file(fake, tmp_path: Path):
    client = fake(hits(5, 1))
    with pytest.raises(ValueError, match="authors is empty"):
        count_coauthor_papers(given(authors=[]), tmp_path)
    with pytest.raises(ValueError, match="pmid is empty"):
        count_coauthor_papers(given(pmid="   "), tmp_path)
    with pytest.raises(ValueError, match="author is empty"):
        count_coauthor_papers(given(authors=["Smith JA", "  "]), tmp_path)
    with pytest.raises(ValueError, match="not a PubMed id"):
        count_coauthor_papers(given(pmid="0100"), tmp_path)
    with pytest.raises(ValueError, match="not an author name"):
        count_coauthor_papers(given(authors=["Smith 3"]), tmp_path)
    with pytest.raises(ValueError, match="cannot contain"):
        count_coauthor_papers(given(authors=["José M"]), tmp_path)
    with pytest.raises(ValueError, match="longer than 80"):
        count_coauthor_papers(given(authors=["A" * 81]), tmp_path)
    assert client.calls == []
    assert not (tmp_path / COAUTHORS_FILE).exists()


def test_an_eighty_character_name_and_boundary_pmids_are_accepted(fake, tmp_path: Path):
    client = fake(hits(2, 1))
    long_name = "A" + ("b" * 79)
    count_coauthor_papers(given(pmid="1", authors=[long_name]), tmp_path)
    assert client.calls[0][1]["term"] == f'"{long_name}"[Author]'
    client.calls.clear()
    count_coauthor_papers(given(pmid="123456789", authors=["Ng A"]), tmp_path)
    assert "123456789[uid]" in client.calls[1][1]["term"]


def test_a_source_paper_outside_the_search_raises_and_writes_nothing(fake, tmp_path: Path):
    client = fake(hits(5, 0))
    with pytest.raises(RuntimeError, match="not one hit"):
        count_coauthor_papers(given(), tmp_path)
    assert len(client.calls) == 2
    assert not (tmp_path / COAUTHORS_FILE).exists()

    client = fake(hits(0, 0))
    with pytest.raises(RuntimeError, match="not one hit"):
        pin_coauthor_count(given(), tmp_path)
    assert len(client.calls) == 2
    assert not (tmp_path / COAUTHORS_FILE).exists()


def test_more_than_one_source_hit_raises(fake, tmp_path: Path):
    fake(hits(5, 2))
    with pytest.raises(RuntimeError, match="not one hit"):
        count_coauthor_papers(given(), tmp_path)
    assert not (tmp_path / COAUTHORS_FILE).exists()


def test_a_failed_second_search_writes_no_file(fake, tmp_path: Path):
    def flaky(url, params):
        if "[uid]" in params["term"]:
            raise RuntimeError("HTTP 500 from esearch")
        return hits(5, 1)(url, params)

    fake(flaky)
    with pytest.raises(RuntimeError, match="HTTP 500"):
        count_coauthor_papers(given(), tmp_path)
    assert not (tmp_path / COAUTHORS_FILE).exists()


def test_esearch_error_shapes_raise(fake, tmp_path: Path):
    def error(_url, _params):
        return {"error": "busy"}

    fake(error)
    with pytest.raises(RuntimeError, match="ESearch error"):
        count_coauthor_papers(given(), tmp_path)
    assert not (tmp_path / COAUTHORS_FILE).exists()

    def shapeless(_url, _params):
        return {}

    fake(shapeless)
    with pytest.raises(TypeError, match="esearchresult"):
        count_coauthor_papers(given(), tmp_path)

    def no_count(_url, _params):
        return {"esearchresult": {"idlist": []}}

    fake(no_count)
    with pytest.raises(TypeError, match="no count"):
        count_coauthor_papers(given(), tmp_path)

    def bad_count(_url, _params):
        return {"esearchresult": {"count": "nope", "idlist": []}}

    fake(bad_count)
    with pytest.raises(RuntimeError, match="no count"):
        count_coauthor_papers(given(), tmp_path)

    def negative(_url, _params):
        return {"esearchresult": {"count": "-1", "idlist": []}}

    fake(negative)
    with pytest.raises(RuntimeError, match="no count"):
        count_coauthor_papers(given(), tmp_path)

    def flagged(_url, _params):
        return {"esearchresult": {"count": True, "idlist": []}}

    fake(flagged)
    with pytest.raises(TypeError, match="no count"):
        count_coauthor_papers(given(), tmp_path)

    def not_a_list(_url, _params):
        return {"esearchresult": {"count": "5", "idlist": "100"}}

    fake(not_a_list)
    with pytest.raises(TypeError, match="id list"):
        count_coauthor_papers(given(), tmp_path)

    def phrases(_url, _params):
        return {"esearchresult": {"count": "0", "idlist": [], "errorlist": {"phrasesnotfound": ["Smith"]}}}

    fake(phrases)
    with pytest.raises(RuntimeError, match="ESearch error"):
        count_coauthor_papers(given(), tmp_path)


def test_sends_the_tool_name_and_credentials(fake, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("NCBI_API_KEY", "secret-key")
    monkeypatch.setenv("NCBI_EMAIL", "a@example.com")
    client = fake(hits(5, 1))
    count_coauthor_papers(given(), tmp_path)
    params = client.calls[0][1]
    assert params["tool"] == "pubmed-coauthor-paper-count"
    assert params["api_key"] == "secret-key"
    assert params["email"] == "a@example.com"


def test_blank_credentials_are_omitted(fake, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("NCBI_API_KEY", "  ")
    monkeypatch.setenv("NCBI_EMAIL", " ")
    client = fake(hits(5, 1))
    count_coauthor_papers(given(), tmp_path)
    params = client.calls[0][1]
    assert "api_key" not in params
    assert "email" not in params


def test_the_term_matches_the_verifier():
    samples = [
        ["Smith JA", "Doe JB"],
        ["  O'Brien   K ", "o'brien k", "Garcia-Lopez M"],
        ["A"],
        ["Ng A"],
    ]
    for names in samples:
        assert unique_authors(names) == check_authors(names)
        assert union_term(unique_authors(names)) == check_term(check_authors(names))
        assert membership_term(union_term(unique_authors(names)), "100").endswith(" AND 100[uid]")


def test_client_rejects_transport_failures():
    def json_handler(_request):
        return httpx.Response(200, text="nope")

    client = HttpxClient(transport=httpx.MockTransport(json_handler), pause=0)
    with pytest.raises(RuntimeError, match="not JSON"):
        client.get_json(ESEARCH_URL, {})

    def list_handler(_request):
        return httpx.Response(200, json=["nope"])

    client = HttpxClient(transport=httpx.MockTransport(list_handler), pause=0)
    with pytest.raises(TypeError, match="not a JSON object"):
        client.get_json(ESEARCH_URL, {})

    def down_handler(_request):
        return httpx.Response(503, text="no")

    client = HttpxClient(transport=httpx.MockTransport(down_handler), pause=0)
    with pytest.raises(RuntimeError, match="HTTP 503"):
        client.get_json(ESEARCH_URL, {})


def test_pause_follows_the_api_key(monkeypatch):
    slept = []
    monkeypatch.setattr("plugin.client.time.sleep", slept.append)

    def ok(_request):
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setenv("NCBI_API_KEY", "secret-key")
    client = HttpxClient(transport=httpx.MockTransport(ok), pause=None)
    client.get_json(ESEARCH_URL, {})
    client.get_json(ESEARCH_URL, {})
    assert slept == [0.11]

    slept.clear()
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    client = HttpxClient(transport=httpx.MockTransport(ok), pause=None)
    client.get_json(ESEARCH_URL, {})
    client.get_json(ESEARCH_URL, {})
    assert slept == [0.34]
