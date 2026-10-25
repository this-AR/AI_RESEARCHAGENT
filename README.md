# AI Research Agent

A CrewAI-based research pipeline that collects company intelligence and creates a personalized outreach sequence through a four-agent workflow.

> The project is being upgraded from a notebook prototype into an evidence-grounded application. See [UPGRADE.md](UPGRADE.md) for the roadmap.

## Architecture

```text
CLI input
  -> lead discovery
  -> email generation
  -> workflow review
  -> quality validation
  -> timestamped Markdown result
```

Application code lives in `src/ai_research_agent`. The original `crew1.ipynb` remains available as a reference and demonstration, but it no longer starts a live API run automatically.

## Requirements

- Python 3.10 or newer
- An API key and model for your LLM provider (Groq by default; Gemini supported)
- Optional Serper API key for search

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .
copy .env.example .env
```

Edit `.env` and provide `LLM_API_KEY` and `LLM_MODEL`. Never commit `.env`.

## Usage

Validate configuration without making external calls:

```bash
research-agent doctor
```

Run the workflow:

```bash
research-agent run \
  --company "DeepLearning.AI" \
  --industry "Online education" \
  --decision-maker "Andrew Ng" \
  --position "Founder" \
  --milestone "a recent AI education initiative"
```

Use `research-agent --help` to see all options. Results are written to `outputs/` unless `--output` specifies another path.

Evaluate the pipeline live over a dataset (defaults to `data/eval_dataset.csv`):

```bash
research-agent eval --limit 1
```

Each run is scored automatically (schema validity, citation coverage, share of cited links that the research step actually found, QA verdict, latency, tokens). The report is written to `outputs/eval/<timestamp>/eval_report.json`. There is no hand-labelled ground truth; QA fields reflect the quality agent's own judgement.

### Latest results

`gemini/gemini-3.1-flash-lite`, the 5 companies in `data/eval_dataset.csv`, one run each (2026-10-25):

| Metric | Before citation fix | Current |
|---|---:|---:|
| Schema-valid runs | 100% | 100% |
| Emails with inline source links (target ≥ 90%) | 0% | 95% |
| Cited URLs found by the research step | not measured | 100% |
| Draft passed QA | 0% | 20% |
| Unsupported claims flagged per run | 1.4 | 0.8 |
| Mean latency per company | 140 s | 101 s |
| Tokens per company | ~93k | ~89k |

QA runs before the final rewrite, so its pass rate describes the draft, not the delivered emails. With 5 companies and one run each, treat differences as indicative; provider 503 retries add latency variance.

## Configuration

| Variable | Required | Purpose |
|---|---:|---|
| `LLM_API_KEY` | Yes | Authenticates model requests (`GROQ_API_KEY` also accepted) |
| `LLM_MODEL` | Yes | LiteLLM model id, e.g. `gemini/gemini-2.0-flash`; a bare name is treated as `groq/<name>` (`GROQ_MODEL` also accepted) |
| `SERPER_API_KEY` | No | Enables Serper-backed search |
| `RESEARCH_OUTPUT_DIR` | No | Changes the output directory |
| `RESEARCH_MAX_RPM` | No | Controls request rate; defaults to `5` |
| `RESEARCH_VERBOSE` | No | Enables verbose CrewAI output |

## Development

```bash
python -m compileall src
python -m ai_research_agent --help
```

The next milestone adds real lead scoring, structured evidence schemas, and comprehensive tests.

## Responsible Use

Generated research can be incomplete or incorrect. Verify decision-maker information, claims, and outreach content before use. Respect privacy, applicable anti-spam law, and website terms.

## License

MIT. See [LICENSE](LICENSE).
