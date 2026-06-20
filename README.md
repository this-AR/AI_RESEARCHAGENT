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
- A Groq API key and compatible Groq model name
- Optional Serper API key for search

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .
copy .env.example .env
```

Edit `.env` and provide `GROQ_API_KEY` and `GROQ_MODEL`. Never commit `.env`.

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

## Configuration

| Variable | Required | Purpose |
|---|---:|---|
| `GROQ_API_KEY` | Yes | Authenticates model requests |
| `GROQ_MODEL` | Yes | Selects the model explicitly |
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
