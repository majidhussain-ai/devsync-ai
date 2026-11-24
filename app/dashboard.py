"""
DevSync AI Dashboard
Core entry point for the autonomous intelligence pipeline UI.
Manages authentication, global state, and core styling.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import altair as alt
import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.agent.curator_agent import CuratorAgent
from app.database.models import AnthropicArticle, Digest, OpenAIArticle, Recipient, YouTubeVideo
from app.database.repository import Repository
# Ensure USER_PROFILE exists in app.profiles.user_profile if still needed, else we rely on Recipient DB
from app.profiles.user_profile import USER_PROFILE 


def generate_magic_token(email: str) -> str:
    """Generates a secure, reproducible short token for Magic Link authentication."""
    hash_object = hashlib.md5(email.lower().strip().encode())
    return f"usr_{hash_object.hexdigest()[:10]}"


def _initialize_session_state() -> None:
    """Bootstraps essential session variables to prevent KeyError during rendering."""
    defaults = {
        "role": "Public",
        "current_user_email": None,
        "current_user_name": "Default User",
        "current_user_interests": "AI"
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

_initialize_session_state()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Core UI Configuration
st.set_page_config(
    page_title="DevSync AI • Intelligence Pipeline",
    layout="wide",
    page_icon="🧠",
    initial_sidebar_state="expanded",
)

# Global Theme & Micro-interactions
st.markdown(
    """
<style>
    :root {
        --bg: #0b1220;
        --panel: rgba(255,255,255,0.06);
        --border: rgba(255,255,255,0.10);
        --text: rgba(255,255,255,0.92);
        --muted: rgba(255,255,255,0.70);
        --shadow: 0 12px 32px rgba(0,0,0,0.35);
        --radius: 16px;
        --radius-sm: 12px;
    }

    .stApp {
        background: radial-gradient(1200px 800px at 15% 10%, rgba(124, 58, 237, 0.20), transparent 60%),
                    radial-gradient(1200px 800px at 85% 0%, rgba(6, 182, 212, 0.16), transparent 55%),
                    linear-gradient(180deg, #0b1220 0%, #070b14 100%);
        color: var(--text);
        font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1200px; }
    div[data-testid="stSidebar"] { background: rgba(255,255,255,0.04); border-right: 1px solid var(--border); }

    .hero {
        padding: 18px;
        border: 1px solid var(--border);
        background: linear-gradient(135deg, rgba(124, 58, 237, 0.18), rgba(6, 182, 212, 0.10));
        box-shadow: var(--shadow);
        border-radius: var(--radius);
        margin-bottom: 18px;
    }
    .hero h1 { margin: 0; font-size: 26px; letter-spacing: 0.2px; }
    .hero p { margin: 6px 0 0 0; color: var(--muted); font-size: 13px; }

    .metric-tile {
        border: 1px solid var(--border);
        background: var(--panel);
        border-radius: var(--radius);
        box-shadow: var(--shadow);
        padding: 14px;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .metric-tile:hover { transform: translateY(-4px); box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2); }

    .pill-wrap { display: flex; gap: 8px; flex-wrap: wrap; }
    .pill {
        display: inline-flex; align-items: center; padding: 6px 10px;
        border-radius: 999px; border: 1px solid var(--border);
        background: rgba(255,255,255,0.06); font-size: 12px; line-height: 1;
    }

    .card {
        border: 1px solid rgba(255,255,255,0.1);
        background: linear-gradient(180deg, rgba(255,255,255,0.07), rgba(255,255,255,0.05));
        border-radius: var(--radius); padding: 16px; margin-bottom: 12px;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .card:hover { transform: translateY(-4px); box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2); }
    
    .card-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
    .card-title { font-size: 16px; font-weight: 650; margin: 0; }
    .card-sub { margin: 6px 0 0 0; color: var(--muted); font-size: 13px; line-height: 1.6; }

    .badge { border-radius: 999px; padding: 6px 10px; font-size: 12px; border: 1px solid var(--border); white-space: nowrap; }
    .badge-yt { border-color: rgba(239,68,68,0.35); background: rgba(239,68,68,0.12); }
    .badge-oa { border-color: rgba(124,58,237,0.35); background: rgba(124,58,237,0.16); }
    .badge-an { border-color: rgba(6,182,212,0.35); background: rgba(6,182,212,0.14); }

    .score-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
    .score-chip {
        border: 1px solid var(--border); background: rgba(255,255,255,0.05);
        border-radius: 999px; padding: 6px 10px; font-size: 12px;
    }
    .score-chip strong { color: white; }

    .thumb {
    width: 100%; height: 110px; border-radius: var(--radius-sm);
    background: radial-gradient(100px 60px at 25% 35%, rgba(255,255,255,0.12), transparent 60%),
                linear-gradient(135deg, rgba(239,68,68,0.18), rgba(0,0,0,0.00));
    border: 1px solid rgba(255,255,255,0.10);
    display: flex; align-items: center; justify-content: center;
    color: rgba(255,255,255,0.85); font-weight: 650;
    }
    .thumb img { width: 100%; height: 100%; object-fit: cover; border-radius: var(--radius-sm); display: block; }

    .term {
        border: 1px solid rgba(255,255,255,0.14); background: #05070c;
        border-radius: var(--radius); padding: 12px; height: 260px; overflow: auto;
        font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12.5px;
        color: rgba(255,255,255,0.86); white-space: pre-wrap;
    }
    .term-hint { color: rgba(255,255,255,0.55); font-size: 12px; margin-top: 6px; }

    details { border-radius: var(--radius-sm) !important; }
    details summary { font-weight: 650; }
    a { color: #93c5fd !important; }
    div[data-testid="InputInstructions"] { display: none !important; }
</style>
""",
    unsafe_allow_html=True,
)

# ------------------------------------
# Data Contracts & Helpers
# ------------------------------------

class FeedItem(BaseModel):
    """Pydantic v2 contract for unified feed rendering."""
    digest_id: str
    article_type: str
    article_id: str
    title: str
    summary: str
    url: str
    created_at: Any
    image_url: Optional[str] = None 
    rank: Optional[int] = None
    relevance_score: Optional[float] = None
    reasoning: Optional[str] = None


def _source_badge(article_type: str) -> Tuple[str, str]:
    t = (article_type or "").lower()
    if t == "youtube":
        return "badge badge-yt", "YouTube"
    if t == "openai":
        return "badge badge-oa", "OpenAI"
    if t == "anthropic":
        return "badge badge-an", "Anthropic"
    return "badge", (article_type or "Unknown").title()


def _today_utc_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)


def _estimate_reading_time(summary: str) -> int:
    words = len((summary or "").split())
    return (words // 200) + 1


def _extract_youtube_video_id(item: FeedItem) -> Optional[str]:
    if (item.article_type or "").lower() != "youtube":
        return None

    article_id = (item.article_id or "").strip()
    if article_id and re.match(r"^[A-Za-z0-9_-]{11}$", article_id):
        return article_id

    url = (item.url or "").strip()
    patterns = [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/embed/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _format_reasoning_points(reasoning: str) -> List[str]:
    raw_parts = [p.strip(" -•\n\t") for p in re.split(r"[\n•]+|(?<=[.!?])\s+", reasoning or "") if p.strip()]
    points = raw_parts[:6] if raw_parts else []
    if not points:
        return []

    formatted = []
    for idx, point in enumerate(points):
        lowered = point.lower()
        if any(k in lowered for k in ["risk", "warning", "urgent", "caution", "concern", "medium"]):
            icon = "⚠️"
        elif any(k in lowered for k in ["match", "relevant", "strong", "high", "good", "aligned"]):
            icon = "✅"
        else:
            icon = "🧠" if idx == 0 else "•"
        formatted.append(f"{icon} {point}")
    return formatted


# ------------------------------------
# Core Backend Processing
# ------------------------------------

@st.cache_data(ttl=30, show_spinner=False)
def load_metrics_and_recent_digests(hours: int) -> Dict[str, Any]:
    repo = None
    try:
        repo = Repository()
        session = repo.session

        # Modern SQLAlchemy 2.0 count queries (resolves N+1 & legacy query syntax)
        yt_count = session.scalar(select(func.count()).select_from(YouTubeVideo)) or 0
        oa_count = session.scalar(select(func.count()).select_from(OpenAIArticle)) or 0
        an_count = session.scalar(select(func.count()).select_from(AnthropicArticle)) or 0
        total_articles = yt_count + oa_count + an_count

        today_start = _today_utc_start()
        processed_today = session.scalar(
            select(func.count()).select_from(Digest).where(Digest.created_at >= today_start)
        ) or 0

        sources = {"youtube": yt_count, "openai": oa_count, "anthropic": an_count}
        active_sources = sum(1 for c in sources.values() if c > 0)
        digests = repo.get_recent_digests(hours=hours)
        
        return {
            "total_articles": total_articles,
            "processed_today": processed_today,
            "active_sources": active_sources,
            "sources": sources,
            "digests": digests,
        }
    finally:
        if repo is not None:
            repo.session.close()


@st.cache_data(ttl=90, show_spinner=False)
def compute_ranked_feed(hours: int, top_n: int, user_name: str, user_interests: str) -> List[FeedItem]:
    repo = None
    try:
        repo = Repository()
        digests = repo.get_recent_digests(hours=hours)
        if not digests:
            return []

        dynamic_profile = {
            "name": user_name,
            "background": "AI Professional", 
            "expertise_level": "Advanced", 
            "interests": [i.strip() for i in (user_interests or "AI").split(",")],
            "preferences": {
                "format": "technical depth",
                "focus": "practical applications",
                "style": "to the point explanations"
            } 
        }
        
        curator = CuratorAgent(dynamic_profile)
        ranked = curator.rank_digests(digests)
        
        if not ranked:
            # Fixed: Explicit mapping to match Pydantic schema and prevent ValidationError
            return [
                FeedItem(
                    digest_id=d["id"], 
                    article_type=d["article_type"], 
                    article_id=d["article_id"],
                    title=d["title"], 
                    summary=d["summary"], 
                    url=d["url"], 
                    created_at=d.get("created_at"),
                    image_url=d.get("image_url")
                ) for d in digests[:top_n]
            ]

        digest_by_id = {d["id"]: d for d in digests}
        items: List[FeedItem] = []
        for r in ranked:
            d = digest_by_id.get(r.digest_id)
            if not d:
                continue
            
            items.append(
                FeedItem(
                    digest_id=d["id"], 
                    article_type=d["article_type"], 
                    article_id=d["article_id"],
                    title=d["title"], 
                    summary=d["summary"], 
                    url=d["url"], 
                    created_at=d.get("created_at"),
                    image_url=d.get("image_url"),
                    rank=getattr(r, "rank", None), 
                    relevance_score=getattr(r, "relevance_score", None),
                    reasoning=getattr(r, "reasoning", None),
                )
            )

        items.sort(key=lambda x: (x.rank if x.rank is not None else 10**9, -(x.relevance_score or 0.0)))
        return items[:top_n]
    finally:
        if repo is not None:
            repo.session.close()


def _pipeline_cmd() -> List[str]:
    return [sys.executable, "-m", "app.daily_runner"]


def _start_pipeline_process() -> None:
    if st.session_state.get("pipeline_running"):
        st.toast("Pipeline is already running.", icon="⏳")
        return

    cmd = _pipeline_cmd()
    st.session_state["pipeline_log"] = ""
    st.session_state["pipeline_running"] = True
    st.session_state["pipeline_started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        env={**os.environ},
    )
    st.session_state["pipeline_proc"] = proc
    st.toast("Pipeline started.")


def _stream_pipeline_output(term_slot: DeltaGenerator) -> None:
    proc: Optional[subprocess.Popen] = st.session_state.get("pipeline_proc")
    if not proc or proc.stdout is None:
        st.session_state["pipeline_running"] = False
        return

    start = time.time()
    while time.time() - start < 0.6:
        line = proc.stdout.readline()
        if not line:
            break
        st.session_state["pipeline_log"] += line

    log_text = st.session_state.get("pipeline_log", "")
    term_slot.markdown(f"<div class='term'>{log_text}</div>", unsafe_allow_html=True)

    rc = proc.poll()
    if rc is None:
        return

    st.session_state["pipeline_running"] = False
    st.session_state["pipeline_returncode"] = rc
    if rc == 0:
        st.toast("Pipeline completed successfully.", icon="✅")
    else:
        st.toast("Pipeline failed. Check output.", icon="❌")
# ------------------------------------
# Sidebar Controls & Authentication
# ------------------------------------

# Initialize repository for UI operations
repo = Repository()

with st.sidebar:
    st.markdown("### 🔐 System Access")
    
    # 1. Map all live users to magic tokens
    all_users = repo.get_all_recipients()
    LIVE_DATABASE_TOKENS = {}
    if all_users:
        for u in all_users:
            tok = generate_magic_token(u.email)
            LIVE_DATABASE_TOKENS[tok] = u
            
    # 2. Check Magic Link Token in URL (For Subscribers)
    query_params = st.query_params
    url_token = query_params.get("token")
    
    # If token exists in URL and matches a user, log them in as Subscriber
    if url_token and url_token in LIVE_DATABASE_TOKENS:
        st.session_state.role = "Subscriber"
        u = LIVE_DATABASE_TOKENS[url_token]
        st.session_state.current_user_email = u.email
        st.session_state.current_user_name = u.name
        st.session_state.current_user_interests = u.interests or "AI"

    # 3. Admin Login Logic
    if st.session_state.role != "Admin":
        pwd_input = st.text_input("Admin Login", type="password", placeholder="Enter password...")
        if st.button("Login as Admin"):
            if pwd_input == ADMIN_PASSWORD:
                st.session_state.role = "Admin"
                st.session_state.current_user_email = "Admin"
                st.session_state.current_user_name = "Architect"
                st.rerun()
            else:
                st.error("Incorrect Password!")

    # 4. Subscriber Exit Logic
    if st.session_state.role == "Subscriber":
        st.success(f"Logged in as: {st.session_state.current_user_name}")
        if st.button("Exit Personal Feed"):
            st.session_state.role = "Public"
            st.session_state.current_user_email = None
            st.session_state.current_user_name = "Default User"
            st.session_state.current_user_interests = "AI"
            st.query_params.clear() # Clear token from URL
            st.rerun()

    # 5. Admin Private Controls (Visible ONLY to Admin)
    if st.session_state.role == "Admin":
        st.success("Logged in as Architect (Admin)")
        if st.button("Logout"):
            st.session_state.role = "Public"
            st.session_state.current_user_email = None
            st.session_state.current_user_name = "Default User"
            st.rerun()
            
        st.markdown("---")
        st.markdown("### ⚙️ Control Center")
        
        # --- Dynamic Profile Engine (Admin Testing) ---
        st.markdown("#### Test AI Feed Profile")
        if all_users:
            user_options = {f"{u.name} ({u.email})": u for u in all_users}
            # Default option to avoid forcing a selection
            selected_user_key = st.selectbox("Select Subscriber to Test:", ["Select..."] + list(user_options.keys()))
            
            if selected_user_key != "Select...":
                selected_user = user_options[selected_user_key]
                st.session_state.current_user_name = selected_user.name
                st.session_state.current_user_interests = selected_user.interests or "AI"
                
                user_interests_list = [i.strip() for i in st.session_state.current_user_interests.split(",") if i.strip()]
                
                st.markdown(
                    f"""
<div class="metric-tile">
    <div style="font-size:14px; font-weight:650;">{st.session_state.current_user_name}</div>
    <div style="color:rgba(255,255,255,0.70); font-size:12.5px; margin-top:2px;">
        {selected_user.email}
    </div>
    <div style="height:10px;"></div>
    <div class="pill-wrap">
    {''.join([f"<span class='pill'>#{i}</span>" for i in user_interests_list])}
</div>
</div>
""",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No subscribers found.")

        # --- Trigger Daily Pipeline ---
        st.markdown("#### Trigger Daily Pipeline")
        cols = st.columns([1, 1])
        with cols[0]:
            if st.button("Fetch Latest Insights", width="stretch", type="primary"):
                _start_pipeline_process()
        with cols[1]:
            if st.button("Refresh UI", width="stretch", type="secondary"):
                st.rerun()
        st.caption("Runs `python -m app.daily_runner` and streams stdout live.")
        
        st.markdown("---")
        st.subheader("Premium Subscribers")

        # --- Add Subscriber ---
        with st.expander("Add Subscriber"):
            with st.form("add_subscriber_form", clear_on_submit=True):
                new_name = st.text_input("User Name", placeholder="Enter your name")
                new_email = st.text_input("User Email", placeholder="Enter your email")
                new_interests = st.text_input("User Interests", placeholder="e.g. MLOps, LLMs, Docker")
                submit_btn = st.form_submit_button("Add Subscriber")
                if submit_btn:
                    if new_name and "@" in new_email:
                        result = repo.add_recipient(
                            name=new_name.strip(), 
                            email=new_email.strip(),
                            interests=new_interests.strip() if new_interests else "AI"
                        )
                        if result:
                            st.success(f"{new_name} added successfully!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Email already exists!")
                    else:
                        st.error("Please enter a valid name and email.")

        # --- Remove Subscriber ---
        with st.expander("Remove Subscriber"):
            with st.form("remove_subscriber_form", clear_on_submit=True):
                del_email = st.text_input("Email to Remove", placeholder="Enter exact email to delete...")
                remove_btn = st.form_submit_button("Remove Subscriber")
                if remove_btn:
                    if del_email:
                        # Refactored: Modern SQLAlchemy 2.0 select statement
                        user_to_delete = repo.session.scalar(
                            select(Recipient).where(Recipient.email == del_email.strip())
                        )
                        if user_to_delete:
                            repo.session.delete(user_to_delete)
                            repo.session.commit()
                            st.success(f"{del_email} removed successfully!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Email not found in database.")
                    else:
                        st.error("Please enter an email address.")

        # --- Update Subscriber ---
        with st.expander("Update Subscriber"):
            with st.form("update_subscriber_form", clear_on_submit=True):
                st.markdown("<small>Enter current email to find user, then enter new details.</small>", unsafe_allow_html=True)
                target_email = st.text_input("Current Email (Required)", placeholder="e.g. old@gmail.com")
                updated_email = st.text_input("New Email", placeholder="New email address")
                updated_name = st.text_input("New Name (Optional)", placeholder="Leave blank to keep current")
                updated_interests = st.text_input("New Interests (Optional)", placeholder="e.g. Docker, Python, Generative AI")
                update_btn = st.form_submit_button("Update Subscriber")
                if update_btn:
                    if target_email:
                        # Refactored: Modern SQLAlchemy 2.0 select statement
                        user_to_update = repo.session.scalar(
                            select(Recipient).where(Recipient.email == target_email.strip())
                        )
                        if user_to_update:
                            changes_made = False
                            if updated_name and updated_name.strip():
                                user_to_update.name = updated_name.strip()
                                changes_made = True
                            if updated_email and updated_email.strip():
                                existing_check = repo.session.scalar(
                                    select(Recipient).where(Recipient.email == updated_email.strip())
                                )
                                if existing_check and existing_check.email != target_email:
                                    st.error("The new email is already in use!")
                                else:
                                    user_to_update.email = updated_email.strip()
                                    changes_made = True
                            if updated_interests and updated_interests.strip():
                                user_to_update.interests = updated_interests.strip()
                                changes_made = True
                                    
                            if changes_made:
                                repo.session.commit()
                                st.success("Subscriber updated successfully!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.warning("No new info provided to update.")
                        else:
                            st.error("Current email not found in database.")
                    else:
                        st.error("Please enter the current email.")

        # --- View Active Subscribers (With Magic Links) ---
        with st.expander("View Active Subscribers"):
            if all_users:
                user_data = []
                for u in all_users:
                    token = generate_magic_token(u.email)
                    magic_link = f"http://localhost:8501/?token={token}"
                    user_data.append({
                        "Name": u.name, 
                        "Email": u.email, 
                        "Interests": u.interests,
                        "Magic Link": magic_link
                    })
                df = pd.DataFrame(user_data)
                df.index = df.index + 1
                st.dataframe(df, width="stretch")
            else:
                st.info("No subscribers in database yet.")

# Global variables sync so downstream components don't break
current_user_name = st.session_state.current_user_name
current_user_interests = st.session_state.current_user_interests

# ------------------------------------
# Main Header & UX Pipeline Logs
# ------------------------------------

st.markdown(
    f"""
<div class="hero">
    <h1>🧠 DevSync AI</h1>
    <p style='font-size: 1.2rem; font-weight: 500;'>An Autonomous Intelligence Pipeline for Multi-Domain Tech Professionals</p>
    <p style='font-size: 0.9rem; opacity: 0.8;'>The AI Brain View • Last refresh: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
</div>
""",
    unsafe_allow_html=True,
)

# Admin Pipeline Status
if st.session_state.role == "Admin":
    st.markdown("### 🧠 AI Pipeline Status")
    with st.container():
        status_slot = st.empty()
        
        with st.expander("👨‍💻 View Developer Logs (Hidden)", expanded=False):
            term_slot = st.empty()
            hint_slot = st.empty()

        if st.session_state.get("pipeline_running"):
            status_slot.info("⏳ **AI is active:** Scraping, processing, and ranking the latest news... Please wait.")
            
            hint_slot.markdown(
                f"<div class='term-hint'>Running since <strong>{st.session_state.get('pipeline_started_at','')}</strong> • streaming output…</div>",
                unsafe_allow_html=True,
            )
            _stream_pipeline_output(term_slot)
            time.sleep(0.25)
            st.rerun()
        else:
            log_text = st.session_state.get("pipeline_log", "")
            if log_text:
                term_slot.code(log_text, language="text")

                rc = st.session_state.get("pipeline_returncode")
                if rc == 0:
                    status_slot.success(" **Pipeline finished successfully!** AI Digest is ready.")
                    hint_slot.markdown("<div class='term-hint'> Pipeline finished successfully.</div>", unsafe_allow_html=True)
                elif rc is not None:
                    status_slot.error(" **Pipeline finished with errors.** Please check the developer logs.")
                    hint_slot.markdown("<div class='term-hint'> Pipeline finished with errors.</div>", unsafe_allow_html=True)
            else:
                status_slot.info(" **System Idle:** Click 'Fetch Latest Insights' in the sidebar to get fresh news.")
                term_slot.code("# Output will appear here.\n# Click \"Fetch Latest Insights\" in the sidebar.", language="text")
                hint_slot.markdown("<div class='term-hint'>Tip: keep this page open to watch scrapers & agents in real-time.</div>", unsafe_allow_html=True)

# ------------------------------------
# Analytics & Data Visualization
# ------------------------------------

st.markdown("### Analytics & Insights Dashboard")

with st.container():
    hours_window = st.slider("Recent window (hours)", min_value=24, max_value=720, value=168, step=24)
    top_n = st.slider("Top N for AI Brain View", min_value=5, max_value=25, value=10, step=1)

with st.spinner("Loading production metrics…"):
    metrics = load_metrics_and_recent_digests(hours=hours_window)

with st.container():
    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        st.metric("Total Articles in DB", metrics["total_articles"], delta="Live")
    with mc2:
        st.metric("Processed Today (Digests)", metrics["processed_today"])
    with mc3:
        st.metric("Active Sources", metrics["active_sources"])

    src_counts = metrics["sources"]
    df = pd.DataFrame(
        {
            "Source": ["YouTube", "OpenAI", "Anthropic"],
            "Count": [src_counts.get("youtube", 0), src_counts.get("openai", 0), src_counts.get("anthropic", 0)],
        }
    )

    color_scale = alt.Scale(
        domain=["YouTube", "OpenAI", "Anthropic"],
        range=["#FF6B6B", "#6EE7B7", "#8B5CF6"],
    )

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8)
        .encode(
            x=alt.X(
                "Source:N", 
                title="", 
                axis=alt.Axis(labelAngle=0, labelFontSize=14, labelPadding=10),
                scale=alt.Scale(paddingInner=0.4, paddingOuter=0.2) 
            ),
            y=alt.Y(
                "Count:Q",
                title="Articles Count",
                axis=alt.Axis(labelFontSize=13, tickMinStep=1, titleFontSize=14, titlePadding=10),
            ),
            color=alt.Color("Source:N", scale=color_scale, legend=None),
            tooltip=[
                alt.Tooltip("Source:N", title="Source"),
                alt.Tooltip("Count:Q", title="Articles", format=".0f"),
            ],
        )
        .properties(height=450) 
    )
    # Refactored: Modern canonical flag for responsive charts
    st.altair_chart(chart, width="stretch")
# ------------------------------------
# Explainable AI Feed
# ------------------------------------

st.markdown("### Explainable AI Feed — \"The AI Brain View\"")

with st.container():
    digests: List[Dict[str, Any]] = metrics.get("digests") or []
    
    if not digests:
        st.warning("No digests found yet. Run the pipeline to populate the database.")
    else:
        if st.session_state.role in ["Subscriber", "Admin"]:
            xai_mode = st.toggle("Compute AI ranking & reasoning (CuratorAgent)", value=True)
        else:
            st.info("🔒 **Premium Feature:** Log in via your Magic Link to unlock personalized AI rankings and reasoning.")
            xai_mode = False

        if xai_mode:
            with st.spinner("CuratorAgent is ranking digests and generating reasoning…"):
                feed = compute_ranked_feed(
                    hours=hours_window, 
                    top_n=top_n,
                    user_name=st.session_state.current_user_name,
                    user_interests=st.session_state.current_user_interests
                )
        else:
            feed = [
                FeedItem(
                    digest_id=d["id"],
                    article_type=d["article_type"],
                    article_id=d["article_id"],
                    title=d["title"],
                    summary=d["summary"],
                    url=d["url"],
                    created_at=d.get("created_at"),
                    image_url=d.get("image_url")
                )
                for d in digests[:top_n]
            ]

        for item in feed:
            badge_cls, badge_label = _source_badge(item.article_type)
            is_youtube = (item.article_type or "").lower() == "youtube"
            reading_time = _estimate_reading_time(item.summary or "")

            left, right = st.columns([0.72, 0.28], gap="large")
            
            with left:
                st.markdown(
                    f"""
<div class="card">
    <div class="card-header">
        <div>
        <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
            <span class="{badge_cls}">{badge_label}</span>
            <span class="score-chip"><strong>Rank</strong>: {item.rank if item.rank is not None else "—"}</span>
            <span class="score-chip"><strong>Score</strong>: {f"{item.relevance_score:.1f}" if item.relevance_score is not None else "—"}</span>
            <span class="score-chip">⏱ {reading_time} min read</span>
        </div>
        <h3 class="card-title" style="margin-top:10px;">{item.title}</h3>
        <p class="card-sub">{item.summary}</p>
        <div class="score-row">
            <span class="score-chip"><strong>ID</strong>: {item.digest_id}</span>
            <span class="score-chip"><strong>Created</strong>: {item.created_at}</span>
        </div>
        <div style="margin-top:10px;">
            <a href="{item.url}" target="_blank">Read original →</a>
        </div>
        </div>
    </div>
</div>
""",
                    unsafe_allow_html=True,
                )
                with st.expander("View AI Reasoning", expanded=False):
                    if item.reasoning:
                        points = _format_reasoning_points(item.reasoning)
                        if points:
                            for p in points:
                                st.markdown(p)
                        else:
                            st.info("Reasoning was generated, but no clear bullet points could be parsed.")
                    else:
                        if st.session_state.role == "Public":
                            st.warning("Reasoning is only available for premium subscribers.")
                        else:
                            st.info("Reasoning unavailable (ranking disabled or agent returned no rationale).")

            with right:
                if is_youtube:
                    video_id = _extract_youtube_video_id(item)
                    if video_id:
                        thumb_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                        st.markdown(
                            f"<div class='thumb'><img src='{thumb_url}' alt='YouTube thumbnail'></div>",
                            unsafe_allow_html=True,
                        )
                        st.caption("YouTube Preview")
                    else:
                        st.markdown("<div class='thumb'>▶ YouTube • Video</div>", unsafe_allow_html=True)
                        st.caption("Video preview unavailable.")
                else:
                    if item.image_url:
                        st.markdown(
                            f"""
                            <div class='thumb'>
                                <img src='{item.image_url}' alt='Article thumbnail' 
                                style='width:100%; height:100%; object-fit:cover; border-radius:12px;'>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        st.caption(f"Source: {item.article_type.title()}")
                    else:
                        source_type = (item.article_type or "").lower()
                        if source_type == "openai":
                            bg, icon, name = "rgba(16, 163, 127, 0.2)", "🤖", "OpenAI"
                        elif source_type == "anthropic":
                            bg, icon, name = "rgba(212, 175, 55, 0.2)", "🧠", "Anthropic"
                        else:
                            bg, icon, name = "rgba(124, 58, 237, 0.1)", "📝", "Article"
                        
                        st.markdown(
                            f"<div class='thumb' style='background:{bg}; border:1px solid rgba(255,255,255,0.1);'>{icon} {name}</div>", 
                            unsafe_allow_html=True
                        )
                        st.caption(f"{name} (No Image)")

# ------------------------------------
# Footer
# ------------------------------------
st.markdown(
    "<div style='margin-top:22px; color:rgba(255,255,255,0.55); text-align:center; font-size:12px;'>"
    "DevSync AI: An Autonomous Intelligence Pipeline for Multi-Domain Tech Professionals © 2026"
    "</div>",
    unsafe_allow_html=True,
)