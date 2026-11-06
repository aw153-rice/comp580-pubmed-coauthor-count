"""Tool tests. The HTTP client is a fake, so nothing here opens a socket."""

import json
from pathlib import Path

import httpx
import pytest
from slimconfig import build_output

from contract import CoauthorCountInput
from plugin.authors import personal_names
from plugin.client import ESUMMARY_URL, HttpxClient, set_client
from plugin.papers import COAUTHORS_FILE, count_paper_coauthors
from plugin.pin import pin_paper_coauthors
from verifier.names import personal_names as check_names

PMID = "100"
BYLINE = [
    {"name": "Smith JA", "authtype": "Author"},
    {"name": "COVID Consortium", "authtype": "CollectiveName"},
    {"name": "Doe JB", "authtype": "Author"},
]


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


def given(pmid=PMID):
    return build_output({"pmid": pmid}, CoauthorCountInput)


def summary(byline, pmid=PMID, error=None):
    record = {"uid": pmid, "authors": byline}
    if error is not None:
        record["error"] = error
    return {"result": {"uids": [pmid], pmid: record}}


def rows(*pairs):
    return [{"name": name, "authtype": kind} for name, kind in pairs]


@pytest.fixture
def sample(fake):
    return fake(lambda url, params: summary(BYLINE))


def test_counts_personal_authors_and_writes_the_record(sample, tmp_path: Path):
    output = count_paper_coauthors(given(), tmp_path)
    assert output.coauthor_count == 2
    assert len(sample.calls) == 1
    url, params = sample.calls[0]
    assert url == ESUMMARY_URL
    assert params["db"] == "pubmed"
    assert params["id"] == "100"
    assert params["retmode"] == "json"
    assert params["version"] == "2.0"
    saved = json.loads((tmp_path / COAUTHORS_FILE).read_text(encoding="utf-8"))
    assert saved == {"pmid": "100", "byline": BYLINE, "coauthor_count": 2}


def test_pin_matches_the_tool_and_writes_nothing(fake, tmp_path: Path):
    fake(lambda url, params: summary(BYLINE))
    pinned = pin_paper_coauthors(given(), tmp_path)
    assert not (tmp_path / COAUTHORS_FILE).exists()
    assert pinned.coauthor_count == count_paper_coauthors(given(), tmp_path).coauthor_count


def test_one_author_returns_one(fake, tmp_path: Path):
    client = fake(lambda url, params: summary(rows(("Solo AB", "Author")), pmid="7"))
    output = count_paper_coauthors(given(pmid="7"), tmp_path)
    assert output.coauthor_count == 1
    assert client.calls[0][1]["id"] == "7"
    saved = json.loads((tmp_path / COAUTHORS_FILE).read_text(encoding="utf-8"))
    assert saved["coauthor_count"] == 1
    assert saved["byline"] == [{"name": "Solo AB", "authtype": "Author"}]


def test_a_repeated_name_is_counted_twice(fake, tmp_path: Path):
    byline = rows(("Smith JA", "Author"), ("Smith JA", "Author"))
    client = fake(lambda url, params: summary(byline))
    output = count_paper_coauthors(given(), tmp_path)
    assert output.coauthor_count == 2
    assert len(client.calls) == 1
    saved = json.loads((tmp_path / COAUTHORS_FILE).read_text(encoding="utf-8"))
    assert saved["byline"] == byline


def test_whitespace_in_a_name_is_collapsed(fake, tmp_path: Path):
    byline = [{"name": "  Smith   JA ", "authtype": "Author"}, {"name": "Doe JB", "authtype": "Author"}]
    fake(lambda url, params: summary(byline))
    output = count_paper_coauthors(given(), tmp_path)
    assert output.coauthor_count == 2
    saved = json.loads((tmp_path / COAUTHORS_FILE).read_text(encoding="utf-8"))
    assert saved["byline"][0]["name"] == "Smith JA"


def test_apostrophe_hyphen_and_accent_stay_in_the_name(fake, tmp_path: Path):
    byline = rows(("O'Brien K", "Author"), ("García-López M", "Author"))
    fake(lambda url, params: summary(byline))
    count_paper_coauthors(given(), tmp_path)
    saved = json.loads((tmp_path / COAUTHORS_FILE).read_text(encoding="utf-8"))
    assert saved["byline"] == byline
    assert saved["coauthor_count"] == 2


def test_a_two_hundred_character_name_and_boundary_pmids_are_accepted(fake, tmp_path: Path):
    long_name = "A" + ("b" * 199)
    client = fake(lambda url, params: summary(rows((long_name, "Author")), pmid="1"))
    output = count_paper_coauthors(given(pmid="1"), tmp_path)
    assert output.coauthor_count == 1
    assert client.calls[0][1]["id"] == "1"
    saved = json.loads((tmp_path / COAUTHORS_FILE).read_text(encoding="utf-8"))
    assert saved["byline"][0]["name"] == long_name
    client = fake(lambda url, params: summary(rows(("Ng A", "Author")), pmid="123456789"))
    count_paper_coauthors(given(pmid="123456789"), tmp_path)
    assert client.calls[0][1]["id"] == "123456789"


def test_the_byline_cap_is_accepted_and_one_past_it_raises(fake, tmp_path: Path):
    capped = rows(*((f"Author {index}", "Author") for index in range(10000)))
    client = fake(lambda url, params: summary(capped))
    output = count_paper_coauthors(given(), tmp_path)
    assert output.coauthor_count == 10000
    assert len(client.calls) == 1
    saved = (tmp_path / COAUTHORS_FILE).read_text(encoding="utf-8")
    over = fake(lambda url, params: summary([*capped, {"name": "Author extra", "authtype": "Author"}]))
    with pytest.raises(RuntimeError, match="more than 10000"):
        count_paper_coauthors(given(), tmp_path)
    assert len(over.calls) == 1
    assert (tmp_path / COAUTHORS_FILE).read_text(encoding="utf-8") == saved


def test_a_bad_pmid_raises_before_any_call_or_file(fake, tmp_path: Path):
    client = fake(lambda url, params: summary(BYLINE))
    with pytest.raises(ValueError, match="pmid is empty"):
        count_paper_coauthors(given(pmid="   "), tmp_path)
    with pytest.raises(ValueError, match="not a PubMed id"):
        count_paper_coauthors(given(pmid="0100"), tmp_path)
    with pytest.raises(ValueError, match="not a PubMed id"):
        count_paper_coauthors(given(pmid="1234567890"), tmp_path)
    assert client.calls == []
    assert not (tmp_path / COAUTHORS_FILE).exists()


def test_a_missing_paper_or_empty_byline_raises_and_writes_nothing(fake, tmp_path: Path):
    client = fake(lambda url, params: summary([], error="cannot get document summary"))
    with pytest.raises(RuntimeError, match="ESummary error"):
        count_paper_coauthors(given(), tmp_path)
    assert len(client.calls) == 1
    assert not (tmp_path / COAUTHORS_FILE).exists()

    fake(lambda url, params: summary([]))
    with pytest.raises(RuntimeError, match="no authors"):
        pin_paper_coauthors(given(), tmp_path)
    assert not (tmp_path / COAUTHORS_FILE).exists()

    fake(lambda url, params: summary(rows(("COVID Consortium", "CollectiveName"))))
    with pytest.raises(RuntimeError, match="no personal authors"):
        count_paper_coauthors(given(), tmp_path)
    assert not (tmp_path / COAUTHORS_FILE).exists()


def test_a_bad_author_row_raises_and_writes_nothing(fake, tmp_path: Path):
    cases = [
        ([{"name": "Smith JA"}], "no name and authtype"),
        ([{"name": "Smith JA", "authtype": "Editor"}], "not Author or CollectiveName"),
        ([{"name": "   ", "authtype": "Author"}], "name is empty"),
        ([{"name": "A" * 201, "authtype": "Author"}], "longer than 200"),
        ([{"name": "Smith\nJA", "authtype": "Author"}], "control character"),
        (["Smith JA"], "not an object"),
    ]
    for byline, match in cases:
        client = fake(lambda url, params, byline=byline: summary(byline))
        with pytest.raises((RuntimeError, TypeError), match=match):
            count_paper_coauthors(given(), tmp_path)
        assert len(client.calls) == 1
        assert not (tmp_path / COAUTHORS_FILE).exists()


def test_esummary_error_shapes_raise(fake, tmp_path: Path):
    def error(_url, _params):
        return {"error": "busy"}

    fake(error)
    with pytest.raises(RuntimeError, match="ESummary error"):
        count_paper_coauthors(given(), tmp_path)
    assert not (tmp_path / COAUTHORS_FILE).exists()

    def shapeless(_url, _params):
        return {}

    fake(shapeless)
    with pytest.raises(TypeError, match="no result"):
        count_paper_coauthors(given(), tmp_path)

    def no_uids(_url, _params):
        return {"result": {"100": {"authors": BYLINE}}}

    fake(no_uids)
    with pytest.raises(TypeError, match="no uids"):
        count_paper_coauthors(given(), tmp_path)

    def other_paper(_url, _params):
        return summary(BYLINE, pmid="101")

    fake(other_paper)
    with pytest.raises(RuntimeError, match="did not return that paper"):
        count_paper_coauthors(given(), tmp_path)

    def repeated(_url, _params):
        body = summary(BYLINE)
        body["result"]["uids"] = ["100", "100"]
        return body

    fake(repeated)
    with pytest.raises(RuntimeError, match="did not return that paper"):
        count_paper_coauthors(given(), tmp_path)

    def no_record(_url, _params):
        return {"result": {"uids": ["100"]}}

    fake(no_record)
    with pytest.raises(TypeError, match="not an object"):
        count_paper_coauthors(given(), tmp_path)

    def no_authors(_url, _params):
        return {"result": {"uids": ["100"], "100": {"uid": "100"}}}

    fake(no_authors)
    with pytest.raises(TypeError, match="no author list"):
        count_paper_coauthors(given(), tmp_path)

    def bad_uid(_url, _params):
        body = summary(BYLINE)
        body["result"]["uids"] = [True]
        return body

    fake(bad_uid)
    with pytest.raises(TypeError, match="invalid pmid"):
        count_paper_coauthors(given(), tmp_path)


def test_sends_the_tool_name_and_credentials(fake, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("NCBI_API_KEY", "secret-key")
    monkeypatch.setenv("NCBI_EMAIL", "a@example.com")
    client = fake(lambda url, params: summary(BYLINE))
    count_paper_coauthors(given(), tmp_path)
    params = client.calls[0][1]
    assert params["tool"] == "pubmed-coauthor-paper-count"
    assert params["api_key"] == "secret-key"
    assert params["email"] == "a@example.com"


def test_blank_credentials_are_omitted(fake, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("NCBI_API_KEY", "  ")
    monkeypatch.setenv("NCBI_EMAIL", " ")
    client = fake(lambda url, params: summary(BYLINE))
    count_paper_coauthors(given(), tmp_path)
    params = client.calls[0][1]
    assert "api_key" not in params
    assert "email" not in params


def test_personal_names_match_the_verifier():
    samples = [
        BYLINE,
        rows(("Smith JA", "Author"), ("Smith JA", "Author")),
        rows(("Solo AB", "Author")),
        rows(("O'Brien K", "Author"), ("Group", "CollectiveName")),
    ]
    for byline in samples:
        assert personal_names(byline) == check_names(byline)


def test_client_rejects_transport_failures():
    def json_handler(_request):
        return httpx.Response(200, text="nope")

    client = HttpxClient(transport=httpx.MockTransport(json_handler), pause=0)
    with pytest.raises(RuntimeError, match="not JSON"):
        client.get_json(ESUMMARY_URL, {})

    def list_handler(_request):
        return httpx.Response(200, json=["nope"])

    client = HttpxClient(transport=httpx.MockTransport(list_handler), pause=0)
    with pytest.raises(TypeError, match="not a JSON object"):
        client.get_json(ESUMMARY_URL, {})

    def down_handler(_request):
        return httpx.Response(503, text="no")

    client = HttpxClient(transport=httpx.MockTransport(down_handler), pause=0)
    with pytest.raises(RuntimeError, match="HTTP 503"):
        client.get_json(ESUMMARY_URL, {})


def test_pause_follows_the_api_key(monkeypatch):
    slept = []
    monkeypatch.setattr("plugin.client.time.sleep", slept.append)

    def ok(_request):
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setenv("NCBI_API_KEY", "secret-key")
    client = HttpxClient(transport=httpx.MockTransport(ok), pause=None)
    client.get_json(ESUMMARY_URL, {})
    client.get_json(ESUMMARY_URL, {})
    assert slept == [0.11]

    slept.clear()
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    client = HttpxClient(transport=httpx.MockTransport(ok), pause=None)
    client.get_json(ESUMMARY_URL, {})
    client.get_json(ESUMMARY_URL, {})
    assert slept == [0.34]
