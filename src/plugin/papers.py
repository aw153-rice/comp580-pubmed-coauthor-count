"""The task tool: count the coauthors of one paper and record the byline."""

from __future__ import annotations

import json
from pathlib import Path

from contract import CoauthorCountInput, CoauthorCountOutput
from plugin.authors import count_coauthors
from plugin.client import get_client

COAUTHORS_FILE = "coauthors.json"


def count_paper_coauthors(given: CoauthorCountInput, workspace: Path) -> CoauthorCountOutput:
    output, record = count_coauthors(given, get_client())
    (workspace / COAUTHORS_FILE).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return output
