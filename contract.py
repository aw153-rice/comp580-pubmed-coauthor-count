"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    COUNT_COAUTHOR_PAPERS = "count_coauthor_papers"
    PIN_COAUTHOR_COUNT = "pin_coauthor_count"


class Task(Enum):
    PUBMED_COAUTHOR_PAPER_COUNT = "pubmed-coauthor-paper-count"


@dataclass
class CoauthorCountInput(Output):
    pmid: Annotated[str, "PMID of the source paper, excluded from the other-paper count"]
    authors: Annotated[list[str], "Author list of that paper, in byline order, at most 20 names"]


@dataclass
class CoauthorCountOutput(Output):
    other_papers: Annotated[int, "Distinct PubMed records matching at least one author, excluding the source PMID"]


TOOLS = {
    Tool.COUNT_COAUTHOR_PAPERS: (CoauthorCountInput, CoauthorCountOutput),
    Tool.PIN_COAUTHOR_COUNT: (CoauthorCountInput, CoauthorCountOutput),
}
TASKS = {Task.PUBMED_COAUTHOR_PAPER_COUNT: (CoauthorCountInput, CoauthorCountOutput)}
