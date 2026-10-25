# Production Design: Making the Pipeline Reliable

Researched 2026-10-25 against the installed `crewai` 1.15.5 and the live evaluation runs in the README. Each recommendation names the problem it fixes, the evidence for that problem, and the design. `UPGRADE.md` remains the feature roadmap; this document is about reliability.

## Where the pipeline stands

Measured over three 5-company eval runs with `gemini/gemini-3.1-flash-lite`:

- Schema-valid output 100% and inline citations 95% after the prompt fix, but both are enforced only by prompt wording. Before the fix, citations were 0%; one change to the wording made the model drop an email (3 of 4) and fail validation.
- Every eval run logged provider `503 UNAVAILABLE` errors. Runs survived, but latency ranged from 20 s to 262 s per company.
- The QA agent runs *before* the final rewrite, so nothing checks the emails that are actually delivered.
- "Grounded" currently means the cited URL appears in `CompanyProfile.sources`, which the LLM also writes. That check is circular.

## Status (2026-10-25)

Items 1–3 are implemented. Building item 2 exposed a bigger problem: a diagnostic run counted **zero** search-tool calls by the research agent. Every earlier "source" came from model memory. `run_research` now runs three searches before the crew (`workflow._gather_sources`) and fails before any LLM call if none return results. The guardrail in `evaluation.check_campaign` enforces the email rules on the `rewrite` task. One crewai detail: a guardrail retry receives only the feedback as context, so the feedback includes the allowed URLs.

Measured on the same 5 companies: runs completed 5/5, inline citations 100%, cited URLs returned by search 100% (previously about 0% in reality), at about 139k tokens per company (+56%) and 172 s mean latency.

Items 4, 5 and 7 are also implemented:
- **7:** each run writes a `ResearchRun` JSON artifact; `research-agent eval --rescore DIR` reproduces the live metrics with no API calls.
- **5:** retries are decided by exception type (Gemini `APIError` with code 429/5xx; litellm rate-limit, overload, timeout and connection errors), with a message-token fallback and equal-jitter backoff. The first live test hit exactly the case this fixes: Gemini returned 503 "high demand" until crewai's own task retries ran out, twice. The old substring check would have failed the run; the new one retried and the third attempt succeeded. The cost shows what's still open: each whole-crew retry re-ran earlier steps (203k tokens for that company). Step-level resume still needs item 6.
- **4:** `LLM_FALLBACK_MODEL` / `LLM_FALLBACK_API_KEY` (Groq chosen). When the primary's retries end on a transient error, the crew is rebuilt with the fallback, reusing the same search results. Proven by unit test; a Groq crew builds through litellm. Not yet exercised live.

## P0: Enforce, don't ask

### 1. Deterministic guardrail on the final task

**Problem:** output rules live in prompts, and prompts drift (see the 0% citation and 3-email runs above).

**Design:** attach a Python function guardrail to the `rewrite` task. CrewAI calls it with the task output; it returns `(True, output)` or `(False, feedback)`, and on failure the agent retries with the feedback, up to `guardrail_max_retries` ([CrewAI Tasks docs](https://docs.crewai.com/en/concepts/tasks)). Check:

- exactly four emails, each with subject and body
- every email body has at least one inline `[Source](url)` link
- every cited URL (inline and `personalization_evidence`) is in the retrieved-source registry from item 2

Reuse the regex and logic in `evaluation.score_outputs`, so the gate and the eval agree. A guardrail retry repeats one task. Today a missing structured output retries the whole five-task crew (~90k tokens per company).

### 2. Ground citations against what search actually returned

**Problem:** the grounding metric trusts LLM-reported sources.

**Design:** `SearchTool` records every URL it returns during a run in a per-run registry (a set on the tool instance, created in `build_tools`). The guardrail and the eval check cited URLs against that registry, not against `CompanyProfile.sources`. Fail closed: a claim whose URL was never retrieved is dropped or sent back, never passed through. This is the "verbatim-or-drop" pattern from [sealmindset/grounding-verifier](https://github.com/sealmindset/grounding-verifier), which also argues against fuzzy or embedding matches because they let fabricated citations through.

Later step: check that the claim text is supported by the fetched page content, not just that the URL is real. Note the limit raised in [How Do LLMs Cite?](https://arxiv.org/html/2606.28358v1): a post-hoc check shows a source *could* support a claim, not that it caused it.

### 3. Gate the delivered output, not the draft

**Problem:** QA's verdict describes the draft.

**Design:** item 1 becomes the blocking gate on the final emails. Keep the QA agent only for subjective feedback (tone, personalization) that feeds the rewrite, and stop reporting its verdict as the pipeline's pass/fail. Do not use CrewAI's `HallucinationGuardrail`: in the open-source package it is a no-op placeholder (`crewai/tasks/hallucination_guardrail.py`).

## P1: Survive provider failures

### 4. Fallback model

**Problem:** one provider, one model; 503s on every run.

**Design:** add an optional `LLM_FALLBACK_MODEL` (plus key). LiteLLM's Router supports retries, cooldowns (`allowed_fails`, `cooldown_time`), and cross-provider fallbacks ([LiteLLM routing docs](https://docs.litellm.ai/docs/routing)). However, crewai sends Gemini through its *native* SDK, bypassing LiteLLM, so the fallback must live in our code: when `run_research` exhausts retries on a provider error, rebuild the crew with the fallback model and try once more. Route the LLM-backed tools through the same choice.

### 5. Typed retry classification and smaller retry units

**Problem:** `run_research` decides whether to retry by matching substrings in error messages (`"rate limit"`, `"timeout"`), and retries the whole crew.

**Design:** classify by exception type (provider rate-limit, timeout, 5xx) with a substring fallback, add jitter to the backoff, and retry the failed step instead of the whole crew. That needs item 6.

### 6. CrewAI Flow with persisted state

**Problem:** results are read by task index (`crew.tasks[4]`), and a failure late in the run discards earlier, paid-for steps.

**Design:** wrap the steps in a CrewAI Flow with a typed Pydantic state (`profile`, `campaign`, `quality`). CrewAI's production guidance recommends Flows for managing state across steps ([production architecture](https://docs.crewai.com/en/concepts/production-architecture)). `@persist` saves state to SQLite after each step, so a rerun can resume. Caveat: this is checkpointing, not durable execution. Detecting crashes and avoiding duplicate work remain our job ([Diagrid](https://www.diagrid.io/learn/crewai-durable-execution)). That is fine for a single-process CLI.

## P2: Operate and measure

### 7. Persist structured run artifacts

Write the full `ResearchRun` (target, profile, campaign, quality, retrieved sources, token usage) as JSON with its `run_id` next to the Markdown. The eval could then be re-scored offline at no API cost. This session could not re-score grounding for an earlier run because only the final campaign was saved.

### 8. Tracing

Emit a trace per run (per task: model, tokens, latency, retries). Options: CrewAI's built-in tracing, or OpenTelemetry via OpenLLMetry or OpenLIT exported to Langfuse's OTLP endpoint ([Langfuse OTel docs](https://langfuse.com/docs/opentelemetry/get-started)). The GenAI semantic conventions are still evolving, so keep custom attributes few.

### 9. Evaluation as a release gate

- Pull requests: offline tests only (already in CI). Add `mypy`, which is listed in the dev extras but never run.
- Manual or nightly GitHub workflow: run `research-agent eval` with secrets, and fail if schema-valid < 100%, inline citations < 90%, or grounded < 100%. Keep LLM-judged scores advisory; one guide recommends deterministic checks as blocking and graded ones as advisory ([DEV: gating CI on LLM eval frameworks](https://dev.to/ethanwritesai/we-gated-ci-on-six-open-source-llm-eval-frameworks-only-two-survived-the-merge-queue-5elf)).
- Dataset: refresh stale milestones (for example "Released Claude 3.5 Sonnet"), add non-AI-industry companies, and add hand-checked expected facts per company, so accuracy can be measured, not just format.

### 10. Smaller hardening

- Pin `crewai` to a minor range: its 1.x releases moved LiteLLM and Gemini into optional extras, which silently broke live runs here.
- Make the search-cache path configurable and enable SQLite WAL mode before running several evals in parallel.
- Find out why `cache_breakpoint` must be stripped from messages; replace the global LiteLLM monkeypatch in `cli.py` with a targeted fix, or drop it.

## Not recommended

- More agents: `UPGRADE.md` already requires evaluation evidence first, and the failures above are enforcement gaps, not missing roles.
- Embedding or fuzzy citation matching: lets fabricated citations pass (item 2).
- An LLM judge as a blocking gate: costly and nondeterministic; keep it advisory.

## Suggested order

1 + 2 + 3 together (one PR, measurable with the existing eval: expect citations at 100% and grounding measured honestly), then 7 (cheap, unlocks offline re-scoring), then 4 and 5, then 6, 8 and 9.
