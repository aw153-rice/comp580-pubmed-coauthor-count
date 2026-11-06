# PubMed Coauthor Paper Count

A `nanoagent.plugin/v0001` plugin, created by `nanoagent plugin new` with the
structure of NanoAgent's reference plugin,
[arxiv-source](https://github.com/zeyuyang8/arxiv-source).

Given one paper's PMID and author list, it counts the other PubMed records
that match at least one of those coauthors.

## Tools

| Tool | Does | Code |
|---|---|---|
| `count_coauthor_papers` | Counts distinct PubMed records for the author list, excluding the source PMID | `src/plugin/papers.py` |
| `pin_coauthor_count` | Computes the same count as the task's answer key, and writes no file | `src/plugin/pin.py` |

`count_coauthor_papers` writes `coauthors.json` in the workspace: the PMID, the normalized author list, the union term, the union count, one source hit, and `other_papers`. Each name is a quoted `[Author]` term. Repeated names are searched once. The source PMID is excluded only when a second search shows it is one hit of that union. At most 20 names are accepted.

### Tasks

| Task | Does | Runner |
|---|---|---|
| `pubmed-coauthor-paper-count` | Returns how many other PubMed papers those coauthors have | `tool`, with `count_coauthor_papers` and reference `pin_coauthor_count` |

The input is `pmid` and `authors`. The output is `other_papers`, the union count minus one.

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
counts papers when they are absent. No workspace
file is required before a run; `count_coauthor_papers` creates `coauthors.json`.
