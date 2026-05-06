#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║         Auto-Post — MidwestMade4U Video Publisher           ║
║         Bible Story Garden + The Mind Files                  ║
╚══════════════════════════════════════════════════════════════╝

Fully automated video creation and YouTube upload.
Picks a fresh topic, generates a script, creates the video,
and posts it — zero input required.

Usage:
    python3 auto_post.py --channel bsg
    python3 auto_post.py --channel tmf
    python3 auto_post.py --trigger-file /path/to/trigger.json

Runs with consistent settings:
  BSG:  Rachel voice (ElevenLabs), 8 scenes, warm ambient music
  TMF:  Adam voice (ElevenLabs), 8 scenes, atmospheric ambient music
"""

import argparse
import json
import os
import random
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "auto_post_log.json"

# ── Voice Settings ─────────────────────────────────────────────────────────────
CHANNEL_VOICES = {
    "bsg": "el_rachel",   # Rachel — calm female (ElevenLabs)
    "tmf": "el_adam",     # Adam   — deep male narrator (ElevenLabs)
}

CHANNEL_LABELS = {
    "bsg": "Bible Story Garden",
    "tmf": "The Mind Files",
}

# ── Topic Banks ────────────────────────────────────────────────────────────────
# These cycle in random order — once all are used, the cycle resets.
# Add more topics here any time to expand the content library.

BSG_TOPICS = [
    "Noah's Ark — Why God Chose ONE Man to Save All Life on Earth",
    "David vs Goliath — How a Boy Defeated an IMPOSSIBLE Giant",
    "Moses Parted the Red Sea — The Most INCREDIBLE Miracle Ever",
    "The Birth of Jesus — The Night That Changed EVERYTHING",
    "Daniel in the Lion's Den — Thrown to Certain Death, He Survived the IMPOSSIBLE",
    "Jonah and the Whale — Swallowed Alive, But God Had Other Plans",
    "Joseph's Coat of Many Colors — From SLAVE to POWERFUL Ruler",
    "The Good Samaritan — A Stranger's Act of Compassion That Changed EVERYTHING",
    "Zacchaeus — The HATED Man Jesus Chose to Save",
    "The Prodigal Son — A Father's Love THAT Never Fails",
    "Jesus Feeds 5000 — How One Miracle Fed an IMPOSSIBLE Crowd",
    "Moses and the Ten Commandments — The MOMENT God Gave His Law",
    "Ruth and Naomi — From DESPAIR to HOPE Against All Odds",
    "Esther Saves Her People — A Queen's Brave Act Prevented GENOCIDE",
    "The Creation Story — How God Made EVERYTHING in 6 Days",
    "Adam and Eve — The FIRST Humans and Their Forbidden Choice",
    "Abraham and Isaac — A Father's ULTIMATE Test of Faith",
    "The Tower of Babel — Why God CONFUSED All Human Languages",
    "Elijah on Mount Carmel — Fire From Heaven DEFEATS 450 Prophets",
    "Saul's Conversion — From PERSECUTOR to Apostle in ONE MOMENT",
    "Jesus Walks on Water — He Did What SEEMED IMPOSSIBLE",
    "The Easter Story — Jesus ROSE FROM THE DEAD (Here's What Happened)",
    "The Christmas Story — The Night Jesus Was BORN (What Really Happened)",
    "Solomon Asks for Wisdom — God Granted Him EVERYTHING Else Too",
    "Gideon's 300 Warriors — How a TINY Army Defeated 135,000 Enemies",
    "Samson's Incredible Strength — Betrayed, Blinded, Yet He Destroyed His Enemies",
    "Joshua and the Walls of Jericho — They FELL by Simply Walking Around Them",
    "Mary and Martha — Jesus Had SHOCKING News for Martha",
    "Lazarus Raised From the Dead — Dead 4 Days, Then Jesus Said ONE Thing",
    "Psalm 23 — The MOST Powerful Prayer of Protection Ever",
    "Jesus Calms the Storm — His Disciples Watched Him DO the IMPOSSIBLE",
    "Peter Walks on Water — Until He Made ONE Mistake",
    "The Beatitudes — Jesus Revealed the SECRET to True Happiness",
    "The Lost Sheep — Jesus Leaves 99 to Find ONE",
    "Shadrach, Meshach, Abednego — Thrown Into a Fiery Furnace, They SURVIVED",
    "Nehemiah Rebuilds Jerusalem — One Man's IMPOSSIBLE Mission to Rebuild the Walls",
    "Elisha and the Widow's Oil — An IMPOSSIBLE Miracle That Saved a Widow's Life",
    "Samuel Hears God's Voice — A Boy Chosen to Become a POWERFUL Prophet",
    "David and Jonathan — A Friendship STRONGER Than Family",
    "Deborah the Judge — A Woman Who DEFEATED an Entire Army",
]

# Topic mix is intentionally weighted:
#   ~55% dark-behavior / personality / manipulation (1.3%+ sub conversion in Apr data)
#   ~30% cognitive biases reframed with relational or behavioral stakes
#   ~15% classic experiments and uncomfortable-truth topics
# Weak-converting topics from the original list (Mere Exposure, Cocktail Party,
# Illusion of Transparency, abstract bias labels) have been dropped.

TMF_TOPICS = [
    # ── Dark behavior / personality / manipulation (high sub conversion) ──
    "The Dark Triad — Why Some People Charm You While Planning to Hurt You",
    "What Narcissists, Psychopaths and Sociopaths Actually Want From You",
    "Gaslighting — The Manipulation Most Victims Never See Coming",
    "Love Bombing — The Red Flag That Feels Like Romance",
    "Why Narcissists Target Empaths (And How They Pick Them)",
    "How Trauma Bonds Trap Victims With Their Abusers",
    "Why Charming People Are Often the Most Dangerous",
    "Why Abusers Always Apologize Before They Do It Again",
    "The 4 Tactics Every Cult Leader Uses On Their Followers",
    "The Psychology of Liars — 4 Tells That Give Them Away",
    "Dehumanization — How Ordinary People Become Capable of Cruelty",
    "The Milgram Experiment — Why 65% of People Will Hurt a Stranger",
    "The Stanford Prison Experiment — What Power Does to Good People",
    "How People Justify Cheating, Stealing, and Lying to Themselves",
    "Why You're Drawn to People Who Treat You Poorly",
    "The Hidden Reason Some People Enjoy Others' Failure",
    "Why Predators Always Test You Before They Strike",

    # ── Cognitive biases reframed with behavioral stakes ──
    "Why One Bad Thing Erases Ten Good Things You've Done",
    "Why the Least Skilled People Are the Most Confident",
    "Why You Can't Let Go of Bad Decisions You've Already Made",
    "Why Facts Make People Believe Their Lies Even Harder",
    "Why You Think Everyone Secretly Agrees With You",
    "Why You Feel Guilty for Things That Aren't Your Fault",
    "Why You Care What Strangers Think (Even Though You Shouldn't)",
    "Why You Overestimate How Much Others Notice Your Mistakes",
    "Why You Feel Obligated to People Who Are Mean to You",
    "Why You're Nicer to Strangers Than to People You Love",
    "Why You Always Underestimate How Long Things Will Take",
    "Why You Regret Things You DIDN'T Do More Than Things You Did",
    "Why You Don't Help Even When You Want To (Bystander Effect)",
    "Why You Obey People in Positions of Power — Even Bad Ones",
    "Why The First Number You Hear Changes Every Decision You Make",
    "Why You Only See Evidence That Proves You Right",
    "Why You Judge Other People Harsher Than You Judge Yourself",
    "Why You Feel Compelled to Return Favors — Even From Bad People",
    "Why Your Brain Only Sees What It Wants To See",
    "Why You Keep Going Back to Things You Know Are Bad For You",

    # ── Uncomfortable-truth / experimental ──
    "Why Most People Will Lie to Your Face and Believe They're Honest",
    "Why High Achievers Secretly Think They're Frauds",
    # "Why You Can't Stop Checking Your Phone" — published twice (Apr 21 + Apr 23) and underperformed; retired from the rotation.
    "Why You Make Worse Decisions When You're Even Slightly Tired",
    "Why You Act Like a Completely Different Person Around Different People",
    "The Real Reason You Procrastinate (It's Not Laziness)",
    "Why Smart People Still Make The Same Dumb Mistake Twice",
]

# ── Topic Log ──────────────────────────────────────────────────────────────────

def load_log() -> dict:
    """Load the topic usage log."""
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text())
        except Exception:
            pass
    return {"bsg": [], "tmf": [], "posts": []}


def save_log(log: dict) -> None:
    LOG_FILE.write_text(json.dumps(log, indent=2))


def pick_topic(channel: str) -> str:
    """Pick a topic not yet used in this cycle. Resets when all are used."""
    log = load_log()
    topics = BSG_TOPICS if channel == "bsg" else TMF_TOPICS
    used = set(log.get(channel, []))
    available = [t for t in topics if t not in used]

    if not available:
        print(f"  🔄 All {len(topics)} topics used — starting a new cycle!")
        log[channel] = []
        save_log(log)
        available = topics[:]

    return random.choice(available)


def mark_posted(channel: str, topic: str, title: str, url: str) -> None:
    """Record a successful post so the topic is not repeated."""
    log = load_log()
    if channel not in log:
        log[channel] = []
    if topic not in log[channel]:
        log[channel].append(topic)
    if "posts" not in log:
        log["posts"] = []
    log["posts"].append({
        "channel":   channel,
        "topic":     topic,
        "title":     title,
        "url":       url,
        "posted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_log(log)
    append_to_google_sheets(channel, title, url)


# ── Validators (post-generation guardrails) ──────────────────────────────────
# These exist because the LLM frequently violates the system-prompt rules.
# We catch the violations in code rather than trusting the model.

import re as _re

# Effect/jargon nouns the model tends to slap at the start of a title.
# If the FIRST word of a title (after "The ") matches one of these, reject.
_TMF_BANNED_LEAD_NOUNS = {
    "halo", "anchoring", "bystander", "barnum", "pseudocertainty", "negativity",
    "dunning", "confirmation", "framing", "availability", "spotlight",
    "pratfall", "ikea", "hindsight", "recency", "primacy", "endowment",
    "illusion", "mere", "cocktail", "mind",
}

def _normalize_title(t: str) -> str:
    """Lowercase + strip punctuation/whitespace for fuzzy comparison."""
    s = (t or "").lower()
    s = _re.sub(r"[^a-z0-9 ]+", " ", s)
    return _re.sub(r"\s+", " ", s).strip()

def title_passes_tmf_rules(title: str) -> tuple[bool, str]:
    """
    Returns (ok, reason). False reason gets fed back into the retry prompt.
    Mirrors the TITLE RULES inside the system prompt — these are enforced here
    because gpt-4o regularly ignores them otherwise.
    """
    if not title or not title.strip():
        return False, "empty title"
    t = title.strip()

    if len(t) > 65:
        return False, f"title too long ({len(t)} chars; keep under 60)"

    # MUST start with "Why You" or "Why Your" — data shows this pattern drives 400-1300 views
    # vs "The [noun]" or other patterns averaging <50 views. Enforced May 6 2026.
    t_lower = t.lower()
    if not (t_lower.startswith("why you") or t_lower.startswith("why your")):
        return False, (
            'title must start with "Why You" or "Why Your" — '
            'e.g. "Why You Stay Loyal to Mean People". '
            'Data: "Why You..." titles avg 400-1300 views; other patterns avg <50 views. '
            'Rewrite as "Why You [verb] [observable behavior]".'
        )

    # No colon mid-title — kills CTR ("Why You're Right: The Mind Trap" flopped)
    if ":" in t:
        return False, 'no colon in title — "Why You [behavior]" only, no subtitle after colon'

    return True, ""

def script_word_count_ok(script: dict) -> tuple[bool, int]:
    """Total narration words must land in 300–360 (≈65–80 sec at Adam ElevenLabs voice rate).
    NOTE: Adam voice speaks at ~4.5 words/sec (not 2.7 as previously assumed).
    Calibrated May 6 2026 after analytics showed 38-57s videos from 180-235w scripts.
    """
    total = 0
    for scene in script.get("scenes", []):
        total += len((scene.get("narration") or "").split())
    return (300 <= total <= 370), total

def title_already_published(title: str, channel: str) -> bool:
    """Fuzzy-match the candidate title against past posts in auto_post_log.json."""
    log = load_log()
    norm = _normalize_title(title)
    if not norm:
        return False
    for post in log.get("posts", []):
        if post.get("channel") != channel:
            continue
        if _normalize_title(post.get("title", "")) == norm:
            return True
    return False

# Per-channel daily cap. The cron schedule already targets these counts;
# this guard exists to stop manual workflow_dispatch / re-runs from stacking
# 5–7 videos on a single day, which Apr 2026 analytics showed dilutes the
# algorithm and tanks per-video views.
DAILY_POST_CAPS = {
    "tmf": 3,
    "bsg": 2,
    "mz":  2,
}

def posts_today_count(channel: str) -> int:
    """Number of successful posts for `channel` today (America/Chicago)."""
    log = load_log()
    today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
    n = 0
    for post in log.get("posts", []):
        if post.get("channel") != channel:
            continue
        posted_at = post.get("posted_at", "")
        # posted_at format: "%Y-%m-%d %H:%M:%S" (server local). Treat the date prefix as the date.
        if posted_at.startswith(today):
            n += 1
    return n

def burst_guard_or_exit(channel: str) -> None:
    """Refuse to publish if today's count is already at the daily cap. Exits 0."""
    cap = DAILY_POST_CAPS.get(channel)
    if not cap:
        return
    today_n = posts_today_count(channel)
    if today_n >= cap:
        label = CHANNEL_LABELS.get(channel, channel)
        print(
            f"\n🛑 Burst-guard: {label} already has {today_n} successful posts today "
            f"(cap = {cap}). Skipping this run to protect algorithmic distribution.\n"
            f"   To override (rare — e.g., recovering from a failed run), set "
            f"BURST_GUARD_OVERRIDE=1 in env."
        )
        sys.exit(0)


def generate_script_for_topic(topic: str, channel: str, num_scenes: int = 8) -> dict:
    """Generate a full video script using OpenAI (standalone, no Flask needed)."""
    if not topic or not topic.strip():
        raise ValueError("Topic cannot be empty")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found. Check GitHub secrets are set correctly.")

    if not api_key.strip():
        raise ValueError("OPENAI_API_KEY is empty. Check GitHub secret value.")

    # Channel-specific instructions
    if channel == "tmf":
        style_guide = (
            "Dark psychology / human behavior educational content for adults. "
            "Tone: calm, analytical, slightly unsettling. "
            "Image prompts MUST be atmospheric and symbolic — NO faces, NO people, NO portraits. "
            "Use objects, environments, shadows, hands (no face), silhouettes, abstract compositions. "
            "Examples: burning money on a desk, broken clock, empty interrogation chair, heavy chains. "
            "Style: black and white / heavily desaturated film noir, high contrast, photorealistic."
        )
    else:
        style_guide = (
            "Bible story / children's educational content for families with young kids. "
            "Tone: warm, wonder-filled, simple, encouraging. "
            "Image prompts should be colorful, cheerful storybook illustration style. "
            "Scene 1 MUST be a dramatic hook that stops scrolling. "
            "Scene 1 image: VISUALLY STRIKING — bold colors, dramatic moment."
        )

    # TMF-specific retention/title rules. These are data-backed from the Mar 22 – Apr 18
    # analytics: top 6 videos = 56% of all views; pure-jargon titles avg ~20 views;
    # 90+ sec videos avg ~40 views; False Consensus had 78.7% swipe-away at 0:32 of 1:16.
    if channel == "tmf":
        channel_rules = """
TITLE RULES (strict — titles drive 20× view differences in this channel):
- MUST start with "Why You" or "Why Your". This is the #1 rule. No exceptions.
- "Why You [verb] [uncomfortable behavior the viewer recognizes in themselves]"
- Must describe an OBSERVABLE BEHAVIOR the viewer does, not a concept or named effect. Under 60 chars.
- GOOD examples (data-backed 400–1300 views):
  • "Why You Stay Loyal to Mean People" ← 576 views
  • "Why One Bad Thing Erases Ten Good Ones" ← 722 views
  • "Why the Least Skilled People Are Most Confident" ← strong
  • "Why You Can't Leave — The Sunk Cost Fallacy" ← effect name AFTER behavior
- BAD examples (data-backed <50 views each):
  • "The Secret Fear of High Achievers" ← starts with "The [noun]" — BANNED
  • "The Haunting Regret of Inaction" ← concept label, not behavior — BANNED
  • "The Dark Triad: Charm or Harm?" ← colon pattern, no "Why You" — BANNED
  • "Why You're Always Right: The Mind Trap" ← colon mid-title kills it
  • "Anchoring Bias: The Invisible Mind Trap" ← effect name lead — BANNED
- If your draft doesn't start with "Why You" or "Why Your", REWRITE it. No exceptions.

HOOK RULES (78.7% of viewers currently swipe away — this is the #1 fix):
- Scene 1 narration = ONE shocking claim or uncomfortable question. 10–18 words MAX.
- NO context. NO "Did you know." NO "Imagine." NO naming the effect. Drop them in mid-tension.
- Scene 2 must DEEPEN or PAY OFF the hook, not pivot or define a term.
- Never name the academic effect until scene 4 or later (if at all).
- GOOD hook: "Most people will lie to your face and genuinely believe they're being honest."
- BAD hook: "The false consensus effect is when people assume others share their views."

BODY & PAYOFF:
- Sentences average 10–14 words. Short, punchy, spoken rhythm.
- Use the word "you" at least 3 times across the full script — create personal confrontation.
- Final scene = an uncomfortable reframe. NOT a motivational quote. NOT a call to action.
- Leave the viewer slightly disturbed, thinking, re-examining their own behavior.
"""
    else:
        channel_rules = """
TITLE RULES:
- Warm, wonder-filled, under 60 chars. Create curiosity for kids + parents.
- Example: "Noah's Ark — Why God Chose ONE Man to Save All Life"

HOOK RULES:
- Scene 1: a dramatic moment or question that stops the scroll.
- Scene 2: deepen the stakes, introduce the problem.
"""

    system_prompt = f"""You are a short-form video script writer for YouTube Shorts.

TARGET LENGTH: 65–80 seconds. NEVER under 60 or over 85 seconds.
- Total narration across ALL scenes combined: 300–360 words. Do not go below 300 or above 370.
- Adam voice speaks at ~4.5 words/sec. 300w = ~67s, 360w = ~80s. Hit this range every time.
- Top performing TMF videos (800–1300 views) averaged 65–85s. Short videos (~45s) get suppressed.

Channel style: {style_guide}
{channel_rules}
Output ONLY valid JSON in this exact format:
{{
  "title": "Title following TITLE RULES above",
  "scenes": [
    {{
      "narration": "Spoken narration, 20–32 words, sentences averaging 10–14 words.",
      "image_prompt": "Vivid scene description for AI image generation. Be specific."
    }}
  ]
}}

Structural rules:
- Exactly {num_scenes} scenes
- SCENE 1 follows HOOK RULES above — shortest scene, highest tension
- Each image_prompt: specific, visual, cinematic — NOT abstract.
- No markdown, no explanation, ONLY the JSON object"""

    try:
        import openai
        print(f"    Connecting to OpenAI API...")
        client = openai.OpenAI(api_key=api_key)

        user_msg = f"Write a {num_scenes}-scene script about: {topic}"
        extra_constraints = ""  # accumulated feedback for retries
        last_script: dict | None = None
        last_title_reason = ""
        last_word_count = 0

        # Up to 3 attempts (1 original + 2 retries) for TMF.
        # BSG validates only word count loosely; title is far less viral-sensitive there.
        max_attempts = 3 if channel == "tmf" else 1

        for attempt in range(1, max_attempts + 1):
            print(f"    Making script generation request (attempt {attempt}/{max_attempts})...")
            messages = [
                {"role": "system", "content": system_prompt + extra_constraints},
                {"role": "user", "content": user_msg},
            ]
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=2000,
                temperature=0.8,
            )
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            script = json.loads(raw.strip())
            last_script = script

            # ── Channel-specific guardrails ──
            if channel == "tmf":
                title_ok, title_reason = title_passes_tmf_rules(script.get("title", ""))
                wc_ok, word_count = script_word_count_ok(script)
                dup = title_already_published(script.get("title", ""), channel)

                problems = []
                if not title_ok:
                    problems.append(f"TITLE FAIL: {title_reason}")
                    last_title_reason = title_reason
                if not wc_ok:
                    problems.append(
                        f"LENGTH FAIL: total narration is {word_count} words "
                        f"(must be 300–370; current = ~{int(word_count/4.5)}s at Adam voice rate, target 65–80s)"
                    )
                    last_word_count = word_count
                if dup:
                    problems.append(
                        f'DUPLICATE FAIL: title "{script.get("title")}" already published — pick a different angle.'
                    )

                if not problems:
                    print(f"    ✅ Script passed validators (title + {word_count}w + unique)")
                    return script

                print(f"    ⚠️  Validator problems on attempt {attempt}: {' | '.join(problems)}")
                extra_constraints = (
                    "\n\nIMPORTANT — your previous draft was REJECTED for these reasons:\n- "
                    + "\n- ".join(problems)
                    + "\nFix ALL of them in this next draft. The title MUST start with \"Why You\" or \"Why Your\" "
                      "and describe an observable behavior the viewer recognizes in themselves. No colons. "
                      "Total narration MUST be 300–360 words across all scenes combined. "
                      "Adam voice speaks at 4.5 words/sec — 300w = 67s, 360w = 80s. DO NOT write short scripts."
                )
            else:
                # BSG: keep behavior — accept first valid JSON.
                print(f"    ✅ OpenAI responded")
                return script

        # All retries exhausted: return last script with a warning so the run still completes.
        print(
            f"    🚨 All {max_attempts} attempts failed validators — "
            f"posting last draft anyway (title issue: {last_title_reason or 'n/a'}, "
            f"word count: {last_word_count or 'n/a'})."
        )
        return last_script  # type: ignore[return-value]

    except json.JSONDecodeError as e:
        raise ValueError(f"OpenAI returned invalid JSON: {str(e)[:100]}")
    except ConnectionError as e:
        raise RuntimeError(f"Network error connecting to OpenAI: {str(e)[:120]}")
    except Exception as e:
        error_type = type(e).__name__
        raise RuntimeError(f"Script generation failed ({error_type}): {str(e)[:150]}")


def append_to_google_sheets(channel: str, title: str, url: str) -> None:
    """Append posted video to Google Sheets Auto-Post Log (GitHub Actions only)."""
    # Only run in GitHub Actions environment
    if not os.getenv("GITHUB_ACTIONS"):
        return

    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        print("⚠️  Google API libraries not available for Sheets logging")
        return

    try:
        # Load service account credentials from GitHub secret
        creds_json = os.getenv("GOOGLE_SHEETS_KEY")
        if not creds_json:
            print("  ❌ GOOGLE_SHEETS_KEY secret is EMPTY or not set in GitHub")
            return

        print(f"  ✓ GOOGLE_SHEETS_KEY found ({len(creds_json)} chars)")
        creds_dict = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )

        # Build Sheets API client
        service = build("sheets", "v4", credentials=creds)
        spreadsheet_id = "1JKlBnYdv-_r3FcjozBtpRxLNRiAoA1ezLRz2W-7vVWI"
        sheet_name = "Auto-Post Log"

        # Prepare row data
        channel_label = CHANNEL_LABELS.get(channel, channel)
        # Central Time (auto-handles CDT/CST switch twice a year)
        timestamp = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M:%S")

        row = [timestamp, channel_label, title, "Success", url, ""]

        # Append to sheet
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:G",
            valueInputOption="USER_ENTERED",
            body={"values": [row]}
        ).execute()

        print(f"  📊 Logged to Google Sheets: {channel_label} — {title}")

    except Exception as e:
        # Log error but don't break the workflow
        import traceback
        error_msg = f"Sheets logging failed: {str(e)[:100]}"
        print(f"  ⚠️  {error_msg}")
        # Still save locally for debugging
        print(f"     (Video posted but not logged to Sheets. Check logs.)")


# ── Dependency Management ──────────────────────────────────────────────────────

def ensure_dependencies() -> bool:
    """Install missing Python packages needed for video_app.py. Returns True if ready."""
    needed = []
    try:
        import flask  # noqa: F401
    except ImportError:
        needed.append("flask")
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        needed.append("edge-tts")
    try:
        import openai  # noqa: F401
    except ImportError:
        needed.append("openai")
    try:
        import googleapiclient  # noqa: F401
    except ImportError:
        needed.extend(["google-api-python-client", "google-auth-httplib2", "google-auth-oauthlib"])

    if not needed:
        return True

    print(f"  📦 Installing missing packages: {', '.join(needed)}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "--break-system-packages"] + needed,
            capture_output=True, timeout=120
        )
        if result.returncode != 0:
            # Try without --break-system-packages (older pip)
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet"] + needed,
                capture_output=True, timeout=120
            )
        if result.returncode == 0:
            print(f"  ✅ Packages installed successfully.")
            return True
        else:
            err = result.stderr.decode("utf-8", errors="replace")[:200]
            print(f"  ⚠️ pip install failed: {err}")
            return False
    except Exception as e:
        print(f"  ⚠️ Could not install packages: {e}")
        return False


# ── Server Management ──────────────────────────────────────────────────────────

SERVER_URL = "http://localhost:5002"


def server_running() -> bool:
    try:
        urllib.request.urlopen(SERVER_URL, timeout=2)
        return True
    except Exception:
        return False


def wait_for_server(timeout: int = 60) -> bool:
    print("  ⏳ Waiting for server to start...")
    for _ in range(timeout):
        if server_running():
            print("  ✅ Server ready!")
            return True
        time.sleep(1)
    return False


# ── API Helpers ────────────────────────────────────────────────────────────────

def api_post(path: str, data: dict, timeout: int = 600) -> dict:
    url     = f"{SERVER_URL}{path}"
    payload = json.dumps(data).encode()
    req     = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        # Show the actual error response from Flask
        error_body = e.read().decode()
        try:
            error_json = json.loads(error_body)
            raise RuntimeError(f"Flask error: {error_json.get('error', error_body)}")
        except:
            raise RuntimeError(f"Flask error (HTTP {e.code}): {error_body[:200]}")


def api_get(path: str, timeout: int = 30) -> dict:
    url = f"{SERVER_URL}{path}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


# ── YouTube Metadata ───────────────────────────────────────────────────────────

def build_yt_metadata(channel: str, title: str) -> dict:
    if channel == "bsg":
        description = (
            f"✝️ {title}\n\n"
            "Bible Stories for Kids — brought to you by Bible Story Garden! "
            "Faith-filled, family-friendly shorts that bring Scripture to life.\n\n"
            "#BibleStories #KidsFaith #BibleForKids #ChristianKids #YouTubeShorts"
        )
        tags = "Bible,Bible Stories,Kids,Faith,Jesus,God,Christian,Children,YouTube Shorts,Bible for Kids"
    else:
        description = (
            f"🧠 {title}\n\n"
            "Dark psychology and human behavior explained — brought to you by The Mind Files. "
            "Why humans do what they do.\n\n"
            "#Psychology #DarkPsychology #HumanBehavior #MindFiles #YouTubeShorts"
        )
        tags = "psychology,dark psychology,human behavior,mind,mental health,behavioral science,YouTube Shorts,The Mind Files"

    return {"description": description, "tags": tags}


# ── Trigger File Support ───────────────────────────────────────────────────────

def write_trigger_file(channel: str, topic: str, script: dict) -> Path:
    """Write a trigger file so auto_watcher.sh can run the pipeline on Mac."""
    ts       = time.strftime("%Y%m%d_%H%M")
    filename = BASE_DIR / f"auto_trigger_{channel}_{ts}.json"
    payload  = {
        "channel":      channel,
        "topic":        topic,
        "script":       script,
        "scheduled_at": time.strftime("%Y-%m-%d %H:%M"),
        "status":       "pending",
    }
    filename.write_text(json.dumps(payload, indent=2))
    return filename


def load_trigger_file(path: str) -> dict:
    """Load a trigger file written by the scheduled task."""
    return json.loads(Path(path).read_text())


# ── Run Pipeline via Server ────────────────────────────────────────────────────

def run_headless(channel: str, topic: str, script: dict) -> str:
    """Generate and upload video directly without Flask server (CI mode)."""
    label  = CHANNEL_LABELS[channel]
    voice  = CHANNEL_VOICES[channel]
    title  = script["title"]
    scenes = script["scenes"]

    print(f"  Title : {title}")
    print(f"  Scenes: {len(scenes)}")

    # Import video generation from video_app.py directly
    try:
        from video_app import run_video_job
        import urllib.request
    except ImportError as e:
        print(f"❌ Could not import video generation: {e}")
        sys.exit(1)

    print(f"\n🎬 Creating video...")
    try:
        # Run video job directly (no Flask server needed)
        video_path = run_video_job(
            title=title,
            scenes=scenes,
            voice=voice,
            fmt="vertical",
            channel=channel
        )
        print(f"  ✅ Video created: {Path(video_path).name}")
    except Exception as e:
        print(f"❌ Video generation failed: {e}")
        sys.exit(1)

    print(f"\n📤 Uploading to YouTube ({label})...")
    yt_meta = build_yt_metadata(channel, title)
    try:
        # Use the Flask server's upload endpoint via direct import
        from video_app import youtube_upload as yt_upload_func
        upload_result = yt_upload_func(
            channel=channel,
            video_path=str(Path(video_path).name),
            title=title,
            description=yt_meta["description"],
            tags=yt_meta["tags"],
            privacy="public"
        )
        yt_url = upload_result.get("url", f"https://youtube.com/@{channel}")
        print(f"  ✅ Uploaded: {yt_url}")
        return yt_url
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        sys.exit(1)


def run_via_server(channel: str, topic: str, script: dict) -> str:
    """Send pre-generated script to the running video server. Returns video URL."""
    label  = CHANNEL_LABELS[channel]
    voice  = CHANNEL_VOICES[channel]
    title  = script["title"]
    scenes = script["scenes"]

    print(f"  Title : {title}")
    print(f"  Scenes: {len(scenes)}")

    # ── Step: Create video ────────────────────────────────────────────────────
    print(f"\n🎬 Creating video...")
    try:
        gen_resp = api_post("/generate", {
            "title":   title,
            "scenes":  scenes,
            "voice":   voice,
            "format":  "vertical",
            "channel": channel,
        }, timeout=10)
    except Exception as e:
        print(f"❌ Video generation request failed: {e}")
        sys.exit(1)

    if "error" in gen_resp:
        print(f"❌ Video start error: {gen_resp['error']}")
        sys.exit(1)

    # Poll until video is done (can take 3-10 minutes)
    print("  ⏳ Processing video (this takes a few minutes)...")
    deadline = time.time() + 900   # 15 min max
    while time.time() < deadline:
        time.sleep(5)
        try:
            status = api_get("/job-status")
        except Exception:
            time.sleep(5)
            continue
        if not status.get("running"):
            break
        elapsed = int(time.time() - (deadline - 900))
        if elapsed % 30 == 0:
            print(f"  ... still working ({elapsed}s)")

    try:
        status = api_get("/job-status")
    except Exception as e:
        print(f"❌ Could not get final job status: {e}")
        sys.exit(1)

    if status.get("error"):
        print(f"❌ Video generation error: {status['error']}")
        sys.exit(1)

    video_path = status.get("output", "")
    if not video_path:
        print("❌ No output video reported.")
        sys.exit(1)

    filename = Path(video_path).name
    print(f"  ✅ Video ready: {filename}")

    # ── Step: Upload to YouTube ───────────────────────────────────────────────
    yt_meta = build_yt_metadata(channel, title)
    print(f"\n📤 Uploading to YouTube ({label})...")
    try:
        upload_resp = api_post("/youtube-upload", {
            "channel":     channel,
            "video_path":  filename,
            "title":       title,
            "description": yt_meta["description"],
            "tags":        yt_meta["tags"],
            "privacy":     "public",
        }, timeout=600)
    except Exception as e:
        print(f"❌ Upload request failed: {e}")
        sys.exit(1)

    if "error" in upload_resp:
        print(f"❌ Upload error: {upload_resp['error']}")
        sys.exit(1)

    return upload_resp.get("url", "(unknown)")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Auto-create and post a YouTube Short")
    parser.add_argument("--channel", choices=["bsg", "tmf"],
                        help="Which channel to post to: bsg or tmf")
    parser.add_argument("--trigger-file",
                        help="Path to a trigger JSON file (written by scheduled task)")
    args = parser.parse_args()

    # ── Determine mode ────────────────────────────────────────────────────────
    if args.trigger_file:
        # Trigger-file mode: script was pre-generated by the scheduled task
        trigger = load_trigger_file(args.trigger_file)
        channel = trigger["channel"]
        topic   = trigger["topic"]
        script  = trigger["script"]
        print(f"\n{'═' * 60}")
        print(f"  🎬 Auto-Post (trigger)  |  {CHANNEL_LABELS[channel]}  |  {time.strftime('%Y-%m-%d %H:%M')}")
        print(f"{'═' * 60}")
        print(f"\n📖 Topic: {topic}  (from scheduled task at {trigger.get('scheduled_at', '?')})")
    else:
        # Standard mode: pick topic and generate script via server
        if not args.channel:
            parser.error("--channel is required unless --trigger-file is provided")
        channel = args.channel
        topic   = None
        script  = None

    label = CHANNEL_LABELS[channel]
    voice = CHANNEL_VOICES[channel]

    # ── Burst-publishing guard ────────────────────────────────────────────────
    # Stop manual re-runs / workflow_dispatch from stacking >cap videos in a day.
    if not os.getenv("BURST_GUARD_OVERRIDE"):
        burst_guard_or_exit(channel)

    if not args.trigger_file:
        print(f"\n{'═' * 60}")
        print(f"  🎬 Auto-Post  |  {label}  |  {time.strftime('%Y-%m-%d %H:%M')}")
        print(f"{'═' * 60}")
        topic = pick_topic(channel)
        print(f"\n📖 Topic: {topic}")

    # ── Ensure dependencies installed ─────────────────────────────────────────
    print("\n🔍 Checking dependencies...")
    deps_ok = ensure_dependencies()
    if not deps_ok:
        print("  ⚠️ Could not install all dependencies (likely running in restricted environment).")
        if script:
            # We have a pre-generated script — save trigger file for Mac watcher
            tf = write_trigger_file(channel, topic, script)
            print(f"\n📁 Trigger file saved for Mac watcher: {tf.name}")
            print("   The Mac watcher (auto_watcher.sh) will pick this up and complete the post.")
        else:
            print("   Run this script manually on your Mac to complete the post.")
        sys.exit(0)

    # ── Start server if needed ────────────────────────────────────────────────
    server_proc        = None
    server_was_running = server_running()

    if server_was_running:
        print("\n🔌 Video server already running — using it.")
    else:
        print("\n🚀 Starting video server...")
        server_proc = subprocess.Popen(
            [sys.executable, str(BASE_DIR / "video_app.py")],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not wait_for_server(timeout=90):
            print("❌ Server failed to start within 90 seconds.")
            sys.exit(1)

    try:
        # ── Generate or use pre-generated script ──────────────────────────────
        if script is None:
            # Generate script via Flask server
            print(f"\n✍️  Generating 8-scene script  (voice: {voice})...")
            try:
                script_resp = api_post("/generate-script", {
                    "topic":      topic,
                    "channel":    channel,
                    "num_scenes": 8,
                })
                if "error" in script_resp:
                    raise ValueError(script_resp["error"])
                script = script_resp["script"]
            except Exception as e:
                print(f"❌ Script generation failed: {e}")
                sys.exit(1)

        title = script["title"]

        # ── Run the pipeline ──────────────────────────────────────────────────
        print(f"\n✍️  Script ready: {title}")
        video_url = run_via_server(channel, topic, script)

        print(f"  ✅ Posted! {video_url}")

        # ── Log success ───────────────────────────────────────────────────────
        mark_posted(channel, topic, title, video_url)

        # Clean up trigger file if it was used
        if args.trigger_file:
            try:
                Path(args.trigger_file).unlink()
            except Exception:
                pass

        print(f"\n{'═' * 60}")
        print(f"  🎉 SUCCESS — {label}")
        print(f"  Topic : {topic}")
        print(f"  Title : {title}")
        print(f"  URL   : {video_url}")
        print(f"{'═' * 60}\n")

    finally:
        # Only stop the server if WE started it
        if server_proc and not server_was_running:
            print("  🛑 Stopping video server...")
            server_proc.terminate()
            server_proc.wait(timeout=10)


if __name__ == "__main__":
    main()
