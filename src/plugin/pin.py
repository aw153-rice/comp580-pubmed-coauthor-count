"""Reference tool: the same coauthor count, with no workspace file, pinned before the task runs."""

from __future__ import annotations

from pathlib import Path

from contract import CoauthorCountInput, CoauthorCountOutput
from plugin.authors import count_coauthors
from plugin.client import get_client


def pin_paper_coauthors(given: CoauthorCountInput, _workspace: Path) -> CoauthorCountOutput:
    output, _record = count_coauthors(given, get_client())
    return output
