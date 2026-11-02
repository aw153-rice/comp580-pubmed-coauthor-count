"""The task tool: count other PubMed papers by the coauthors and record the search."""

from __future__ import annotations

import json
from pathlib import Path

from contract import CoauthorCountInput, CoauthorCountOutput
from plugin.client import get_client
from plugin.count import count_papers

COAUTHORS_FILE = "coauthors.json"


def count_coauthor_papers(given: CoauthorCountInput, workspace: Path) -> CoauthorCountOutput:
    output, record = count_papers(given, get_client())
    (workspace / COAUTHORS_FILE).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return output
