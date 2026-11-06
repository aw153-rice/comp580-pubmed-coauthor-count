"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    COUNT_PAPER_COAUTHORS = "count_paper_coauthors"
    PIN_PAPER_COAUTHORS = "pin_paper_coauthors"


class Task(Enum):
    PUBMED_COAUTHOR_PAPER_COUNT = "pubmed-coauthor-paper-count"


@dataclass
class CoauthorCountInput(Output):
    pmid: Annotated[str, "PMID of the paper whose coauthors are counted"]


@dataclass
class CoauthorCountOutput(Output):
    coauthor_count: Annotated[int, "Number of personal authors PubMed lists on that paper, including the first"]


TOOLS = {
    Tool.COUNT_PAPER_COAUTHORS: (CoauthorCountInput, CoauthorCountOutput),
    Tool.PIN_PAPER_COAUTHORS: (CoauthorCountInput, CoauthorCountOutput),
}
TASKS = {Task.PUBMED_COAUTHOR_PAPER_COUNT: (CoauthorCountInput, CoauthorCountOutput)}
