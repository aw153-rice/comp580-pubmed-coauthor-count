# PubMed Coauthor Paper Count

A `nanoagent.plugin/v0001` plugin, created by `nanoagent plugin new` with the
structure of NanoAgent's reference plugin,
[arxiv-source](https://github.com/zeyuyang8/arxiv-source).

Given one paper's PMID, it counts the personal authors PubMed lists on that paper.

## Tools

| Tool | Does | Code |
|---|---|---|
| `count_paper_coauthors` | Counts personal authors on one PMID | `src/plugin/papers.py` |
| `pin_paper_coauthors` | Computes the same count as the task's answer key, and writes no file | `src/plugin/pin.py` |

`count_paper_coauthors` writes `coauthors.json` in the workspace: the PMID, the byline, and `coauthor_count`. Each byline row is a name and an `authtype`. `Author` rows count, in order, including the first author. `CollectiveName` rows stay in the byline and do not count. A repeated personal name counts once per row. The file is written only after the summary parses and at least one personal author remains.

### Tasks

| Task | Does | Runner |
|---|---|---|
| `pubmed-coauthor-paper-count` | Returns how many coauthors that paper has | `tool`, with `count_paper_coauthors` and reference `pin_paper_coauthors` |

The input is `pmid`. The output is `coauthor_count`, the number of personal authors on that paper.

## Layout

```text
.
├── nanoagent.yaml   # manifest (a slimconfig ManifestConfig): id, runtime, permissions, tools, tasks
├── contract.py      # each tool's and task's typed input and output: slimconfig Output classes
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # environment variable NAMEs this plugin needs, never values
├── src/plugin/      # the MCP server: __main__.py, its IMPLEMENTATIONS, and the plugin's own modules
├── tests/
├── ui/              # how the page draws the outputs: renderers.js and renderers.css
├── product/         # the product page a catalog shows: product.yaml and icon.svg
└── verifier/        # deterministic verifier package
```

`contract.py` is the one place a value's shape is declared. Its `Output`
classes are the JSON Schemas the server offers and the agent sees, and every
input and output is built into its class on the way in and out: the server,
NanoAgent and the verifier all get typed values, never loose dicts. A tool
that fails raises; NanoAgent sees an MCP error.

## Develop and run

```bash
uv sync --extra dev
uv run pytest
```

The tests use a fake HTTP client and do not call NCBI. A live run needs
network access to `eutils.ncbi.nlm.nih.gov`. `.env` declares no variables. The client adds `NCBI_API_KEY` and `NCBI_EMAIL`
to the E-utilities request only when the process already has them, and still
counts coauthors when they are absent. No workspace
file is required before a run; `count_paper_coauthors` creates `coauthors.json`.
