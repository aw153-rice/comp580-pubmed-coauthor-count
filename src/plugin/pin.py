"""Reference tool: the same other-paper count, with no workspace file, pinned before the task runs."""

from __future__ import annotations

from pathlib import Path

from contract import CoauthorCountInput, CoauthorCountOutput
from plugin.client import get_client
from plugin.count import count_papers


def pin_coauthor_count(given: CoauthorCountInput, _workspace: Path) -> CoauthorCountOutput:
    output, _record = count_papers(given, get_client())
    return output
