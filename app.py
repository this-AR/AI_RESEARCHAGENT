"""Streamlit demonstration interface for the AI Research Agent.

Run with:
    streamlit run app.py

Requires:
    - GROQ_API_KEY and GROQ_MODEL in .env
    - Optional SERPER_API_KEY
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from ai_research_agent.config import Settings
from ai_research_agent.errors import ResearchAgentError
from ai_research_agent.exports import export_csv, export_json, export_markdown
from ai_research_agent.lead_scoring import score_lead
from ai_research_agent.models import ResearchTarget
from ai_research_agent.schemas import (
    CompanyProfile,
    DecisionMaker,
    EmailCampaign,
    EmailMessage,
    EvidenceClaim,
    EvidenceStatus,
    LeadScore,
    QualityReport,
    ResearchRun,
    ResearchSource,
)
from ai_research_agent.search_engine import search
from ai_research_agent.workflow import run_research

st.set_page_config(page_title="AI Research Agent", page_icon="🔍", layout="wide")


# ---------------------------------------------------------------------------
# Sidebar / Setup
# ---------------------------------------------------------------------------

st.sidebar.title("🔍 AI Research Agent")
st.sidebar.caption("Company research and outreach generation")

with st.sidebar.expander("Setup"):
    st.markdown("""
    1. Copy `.env.example` to `.env`
    2. Set `GROQ_API_KEY` and `GROQ_MODEL`
    3. Optional: set `SERPER_API_KEY` for better search
    """)

settings: Settings | None = None

@st.cache_resource(show_spinner=False)
def load_settings(require_live: bool = False) -> Settings:
    return Settings.from_env(require_live_credentials=require_live)

try:
    settings = load_settings(require_live=False)
    st.sidebar.success(f"Search provider: {settings.search_provider}")
except ResearchAgentError as exc:
    st.sidebar.error(str(exc))


# ---------------------------------------------------------------------------
# Input Form
# ---------------------------------------------------------------------------

st.header("Target Company")

with st.form("target_form"):
    col1, col2 = st.columns(2)
    with col1:
        company = st.text_input("Company name", value="DeepLearning.AI")
        industry = st.text_input("Industry", value="Online education")
    with col2:
        decision_maker = st.text_input("Decision maker", value="Andrew Ng")
        position = st.text_input("Position", value="Founder")
    milestone = st.text_input("Recent milestone", value="a recent AI education initiative")
    submitted = st.form_submit_button("Run Research", use_container_width=True)


# ---------------------------------------------------------------------------
# Workflow execution
# ---------------------------------------------------------------------------

if submitted:
    if not company or not industry or not decision_maker or not position or not milestone:
        st.warning("Please fill in all fields.")
        st.stop()

    try:
        live_settings = load_settings(require_live=True)
    except ResearchAgentError as exc:
        st.error(f"Configuration error: {exc}")
        st.stop()

    target = ResearchTarget(
        company_name=company,
        industry=industry,
        key_decision_maker=decision_maker,
        position=position,
        recent_milestone=milestone,
    )

    progress = st.progress(0, text="Starting research...")

    try:
        # Phase 1: web search (independent, evidence-gathering)
        progress.progress(10, text="Searching the web...")
        search_query = f"{company} {industry} {milestone}"
        search_results = search(search_query, provider=live_settings.search_provider.lower(), api_key=live_settings.serper_api_key)

        # Phase 2: run CrewAI workflow
        progress.progress(40, text="Running research agents...")
        raw_result, md_path = run_research(target, live_settings)

        progress.progress(80, text="Scoring lead and building exports...")

        # Build structured run from available data
        # Note: raw_result is CrewAI free-text.  We supplement with structured
        # search results and deterministic lead scoring.
        company_profile = CompanyProfile(
            company_name=company,
            industry=industry,
            sources=search_results,
        )
        dm = DecisionMaker(
            name=decision_maker,
            position=position,
        )
        lead_score = score_lead(company_profile, dm)

        # Parse simple email structure from raw_result if possible
        emails: list[EmailMessage] = []
        raw_text = str(raw_result)
        # Heuristic: split on "Subject:" lines
        chunks = raw_text.split("Subject:")
        for chunk in chunks[1:]:
            lines = chunk.strip().splitlines()
            subject = lines[0].strip() if lines else ""
            body = "\n".join(lines[1:]).strip() if len(lines) > 1 else chunk.strip()
            emails.append(EmailMessage(subject=subject, body=body))

        if not emails:
            # Fallback: treat entire result as one message
            emails = [EmailMessage(subject=f"Outreach to {company}", body=raw_text)]

        campaign = EmailCampaign(
            target_company=company,
            target_contact=decision_maker,
            emails=emails,
        )

        quality = QualityReport(
            passed=bool(search_results and len(emails) >= 1),
            recommendations=["Review emails for factual accuracy before sending."],
        )

        run = ResearchRun(
            target=target.as_inputs(),
            company_profile=company_profile,
            decision_maker=dm,
            lead_score=lead_score,
            campaign=campaign,
            quality=quality,
        )

        progress.progress(100, text="Done!")
        st.session_state["last_run"] = run
        st.session_state["last_raw"] = raw_text
        st.session_state["last_md_path"] = str(md_path)

    except Exception as exc:
        progress.progress(100, text="Error")
        st.error(f"Workflow failed: {exc}")
        st.stop()


# ---------------------------------------------------------------------------
# Results display
# ---------------------------------------------------------------------------

if "last_run" in st.session_state:
    run: ResearchRun = st.session_state["last_run"]

    tab1, tab2, tab3, tab4 = st.tabs(["Research & Score", "Email Campaign", "Quality Report", "Downloads"])

    with tab1:
        st.subheader("Lead Score Breakdown")
        if run.lead_score:
            st.metric("Total Score", f"{run.lead_score.total} / 100")
            for factor in run.lead_score.factors:
                col_a, col_b = st.columns([1, 3])
                col_a.write(f"**{factor.name}**")
                col_b.progress(factor.score / factor.max_score, text=f"{factor.score}/{factor.max_score} — {factor.explanation}")
                if factor.evidence_missing:
                    col_b.caption("⚠️ Missing evidence")
        else:
            st.info("No lead score available.")

        st.subheader("Web Sources")
        if run.company_profile and run.company_profile.sources:
            for src in run.company_profile.sources:
                with st.expander(f"{src.title} ({src.provider})"):
                    st.write(src.snippet or "No snippet.")
                    st.markdown(f"[Open source]({src.url})")
        else:
            st.info("No search results.")

    with tab2:
        st.subheader("Generated Emails")
        if run.campaign:
            for idx, email in enumerate(run.campaign.emails, start=1):
                with st.expander(f"Message {idx}: {email.subject}", expanded=idx == 1):
                    st.text_input("Subject", value=email.subject, key=f"sub_{idx}")
                    st.text_area("Body", value=email.body, height=200, key=f"body_{idx}")
                    st.text_input("Call to action", value=email.call_to_action, key=f"cta_{idx}")
                    st.text_input("Timing", value=email.suggested_timing, key=f"timing_{idx}")
        else:
            st.info("No emails generated.")

    with tab3:
        st.subheader("Quality & Grounding")
        if run.quality:
            st.write("**Passed:**", "✅ Yes" if run.quality.passed else "❌ No")
            if run.quality.unsupported_claims:
                st.write("**Unsupported claims:**")
                for c in run.quality.unsupported_claims:
                    st.error(c)
            if run.quality.missing_evidence:
                st.write("**Missing evidence:**")
                for m in run.quality.missing_evidence:
                    st.warning(m)
            if run.quality.recommendations:
                st.write("**Recommendations:**")
                for r in run.quality.recommendations:
                    st.info(r)
        st.markdown("---")
        st.caption("Raw agent output (unedited)")
        st.text_area("Raw output", st.session_state.get("last_raw", ""), height=300, label_visibility="collapsed")

    with tab4:
        st.subheader("Export Results")
        run_id = run.run_id

        json_path = export_json(run, f"outputs/{run_id}.json")
        md_path = export_markdown(run, f"outputs/{run_id}.md")
        csv_path = export_csv([run], f"outputs/{run_id}.csv")

        col_dl1, col_dl2, col_dl3 = st.columns(3)
        with col_dl1:
            with open(json_path, "rb") as f:
                st.download_button("📄 JSON", f, file_name=f"{run_id}.json", mime="application/json", use_container_width=True)
        with col_dl2:
            with open(md_path, "rb") as f:
                st.download_button("📝 Markdown", f, file_name=f"{run_id}.md", mime="text/markdown", use_container_width=True)
        with col_dl3:
            with open(csv_path, "rb") as f:
                st.download_button("📊 CSV", f, file_name=f"{run_id}.csv", mime="text/csv", use_container_width=True)

        st.markdown("---")
        st.caption(f"CrewAI Markdown also saved to: `{st.session_state.get('last_md_path', 'N/A')}`")

else:
    st.info("Fill in the form above and click **Run Research** to get started.")
