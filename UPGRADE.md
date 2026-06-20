# AI Research Agent Upgrade Roadmap

## Goal

Transform the current CrewAI notebook prototype into a reliable, evidence-grounded application that demonstrates production Python, AI orchestration, testing, evaluation, and user-interface skills.

## Current State

The project already demonstrates:

- A sequential four-agent CrewAI workflow
- Company and decision-maker research
- Personalized outreach generation
- Search-provider fallback logic
- Basic retry and offline-checking functions

The largest gaps are reproducibility, genuine tool implementation, verifiable outputs, automated tests, and a deployable interface.

## Priority 0: Repository Cleanup

Complete these items before adding features.

- [x] Resolve merge-conflict markers in `README.md`
- [x] Repair broken character and emoji encoding
- [x] Remove stale notebook widget metadata
- [x] Prevent the notebook from automatically starting a paid/API-backed run
- [x] Add `.gitignore` for `.env`, `.venv`, caches, and generated results
- [x] Add `.env.example` containing documented variable names only
- [x] Add the license referenced by the README
- [x] Initialize or restore Git history

### Completion criteria

- A new user can clone the repository without generated or secret files.
- The README renders correctly and contains no conflict markers.
- Opening the notebook does not execute external calls automatically.

## Priority 1: Convert the Notebook into an Application

Keep the notebook as a demonstration, but move application logic into reusable modules.

Suggested structure:

```text
ai-research-agent/
|-- src/ai_research_agent/
|   |-- agents.py
|   |-- tasks.py
|   |-- workflow.py
|   |-- config.py
|   |-- schemas.py
|   |-- cli.py
|   `-- tools/
|       |-- search.py
|       |-- lead_scoring.py
|       |-- sentiment.py
|       `-- file_parser.py
|-- tests/
|-- examples/
|-- app.py
|-- pyproject.toml
|-- .env.example
`-- README.md
```

### Tasks

- [x] Add a `pyproject.toml` with bounded dependencies
- [x] Load configuration from environment variables
- [x] Validate required configuration at startup
- [x] Create a CLI entry point
- [x] Separate provider selection from workflow logic
- [x] Add structured logging in place of most `print` statements
- [x] Define explicit exceptions for configuration, dependency, and workflow failures

Example CLI:

```bash
research-agent run --company "DeepLearning.AI" --industry "Education"
```

### Completion criteria

- The workflow runs without opening Jupyter.
- Modules can be imported without installing packages at runtime.
- Configuration errors produce short, actionable messages.

## Priority 2: Implement Real Research Tools

The current lead profiler and file parser return mostly static templates. Replace them with deterministic, testable implementations.

### Lead scoring

- [ ] Define scoring factors such as company fit, recent activity, decision-maker confidence, pain-point evidence, and data freshness
- [ ] Return a score from 0 to 100
- [ ] Include a factor-by-factor explanation
- [ ] Distinguish missing evidence from negative evidence

### File parsing

- [ ] Parse CSV and JSON inputs genuinely
- [ ] Validate required fields
- [ ] Normalize company names, URLs, and contact data
- [ ] Report malformed rows without claiming successful extraction

### Search and research

- [ ] Normalize results from every search provider
- [ ] Deduplicate URLs and substantially similar results
- [ ] Record source URL, title, retrieval time, and provider
- [ ] Cache repeated queries
- [ ] Apply bounded retries and exponential backoff

### Completion criteria

- Tool outputs depend on their inputs and contain no placeholder values.
- Every tool has unit tests for success, empty input, and failure cases.
- Repeated searches can reuse cached results.

## Priority 3: Add Structured, Evidence-Grounded Outputs

Use Pydantic models instead of asking agents to produce "JSON-like" text.

Recommended models:

- `ResearchSource`
- `EvidenceClaim`
- `DecisionMaker`
- `CompanyProfile`
- `LeadScore`
- `EmailMessage`
- `EmailCampaign`
- `QualityReport`
- `ResearchRun`

Each factual claim should contain:

- The claim text
- Its supporting source URL
- Retrieval date
- Confidence score
- Whether the claim is verified or inferred

### Safety and grounding rules

- [ ] Do not generate unsupported company facts
- [ ] Do not invent testimonials, case studies, or performance metrics
- [ ] Mark uncertain decision-maker information clearly
- [ ] Reject malformed agent output and retry with validation feedback
- [ ] Preserve evidence links through the email-generation stage

### Exports

- [ ] JSON for machine-readable results
- [ ] Markdown for human review
- [ ] CSV for lead and CRM import

### Completion criteria

- Every run produces schema-valid output.
- Important factual claims are traceable to sources.
- Unsupported claims are removed or labeled as inference.

## Priority 4: Testing and AI Evaluation

This milestone provides the strongest résumé differentiation.

### Automated tests

- [ ] Unit tests for tools, schemas, configuration, and retry behavior
- [ ] Mocked integration test for the complete workflow
- [ ] Provider-fallback tests
- [ ] Tests that require no API key or network access
- [ ] A small optional live-test suite

### Evaluation dataset

Create several representative companies with manually reviewed expected evidence and output requirements.

Track:

- Schema-valid output rate
- Citation coverage
- Unsupported-claim rate
- Source freshness
- Lead-score consistency
- Email personalization coverage
- Latency
- Token usage and estimated cost

### Continuous integration

- [ ] Run tests on every pull request
- [ ] Run formatting and lint checks
- [ ] Add static type checking
- [ ] Publish a coverage report

Suggested quality gate:

```text
Tests passing:              100%
Schema-valid runs:          100%
Citation coverage:          >= 90%
Unsupported factual claims: <= 5%
```

### Completion criteria

- The README displays real evaluation results.
- A failing grounding or schema check makes CI fail.
- Core tests pass offline and deterministically.

## Priority 5: Build a Demonstration Interface

A lightweight Streamlit interface is sufficient.

### Features

- [ ] Company and decision-maker input form
- [ ] Live workflow progress
- [ ] Cited company research view
- [ ] Explainable lead-score breakdown
- [ ] Editable email sequence
- [ ] Quality and grounding report
- [ ] JSON, Markdown, and CSV downloads
- [ ] Graceful empty, loading, and error states

### Completion criteria

- A reviewer can understand and run the core workflow without reading code.
- The interface distinguishes sourced facts from model inference.
- The repository includes screenshots or a short demonstration GIF.

## Priority 6: Production Enhancements

Add these only after the main vertical slice is complete.

- [ ] Docker image and health check
- [ ] Persistent run history using SQLite or PostgreSQL
- [ ] Batch company processing with controlled concurrency
- [ ] Observability for latency, errors, model usage, and cost
- [ ] Prompt templates with explicit versions
- [ ] Optional human approval before exporting outreach
- [ ] CRM-ready export adapters
- [ ] A/B email variants with recorded evaluation results

Avoid adding more agents unless evaluation shows that a new role measurably improves output quality.

## Recommended Delivery Plan

### Milestone 1: Reliable foundation

Complete repository cleanup, package extraction, configuration, and CLI support.

**Portfolio result:** Demonstrates maintainable Python application design.

### Milestone 2: Trustworthy research pipeline

Implement real tools, structured schemas, citations, confidence scores, and exports.

**Portfolio result:** Demonstrates grounded AI engineering rather than prompt-only orchestration.

### Milestone 3: Measured quality

Add offline tests, an evaluation dataset, quality metrics, and CI.

**Portfolio result:** Demonstrates the ability to evaluate and operate nondeterministic AI systems.

### Milestone 4: Recruiter-friendly demo

Add the Streamlit interface, example results, screenshots, and deployment documentation.

**Portfolio result:** Makes the engineering work immediately visible and usable.

## README Evidence Checklist

The final README should include:

- [ ] A concise problem statement
- [ ] Architecture diagram
- [ ] Setup instructions that work from a clean environment
- [ ] CLI and interface examples
- [ ] One sanitized output example with citations
- [ ] Evaluation methodology and measured results
- [ ] Test and CI status
- [ ] Screenshots or demonstration GIF
- [ ] Known limitations and responsible-use notes
- [ ] A short explanation of engineering tradeoffs

## Suggested Résumé Bullet

> Built an evidence-grounded multi-agent research pipeline that transforms web sources into validated lead profiles and personalized outreach, using typed schemas, citation verification, automated evaluations, caching, and an interactive dashboard.

Replace general claims with measured results after evaluation, for example:

> Achieved 94% citation coverage and reduced repeated search calls by 38% through schema validation, evidence checks, and query caching across a curated company-research benchmark.

Only publish metrics actually produced by the evaluation suite.

## Definition of Portfolio-Ready

The project is ready to feature prominently when:

- It installs and runs from a clean environment.
- A complete offline test suite passes.
- Live research generates schema-valid, cited output.
- Placeholder tools have been removed.
- Evaluation results are reproducible and documented.
- The demo can be understood in under two minutes.
- The repository contains no secrets, conflict markers, or generated environment files.
