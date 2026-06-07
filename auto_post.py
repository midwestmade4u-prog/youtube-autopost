#!/usr/bin/env python3
"""
ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
â         Auto-Post â MidwestMade4U Video Publisher           â
â         Bible Story Garden + The Mind Files                  â
ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

Fully automated video creation and YouTube upload.
Picks a fresh topic, generates a script, creates the video,
and posts it â zero input required.

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
import re as _re_imports
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# ââ Paths âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
BASE_DIR = Path(__file__).parent
LOG_FILE     = BASE_DIR / "auto_post_log.json"
# Per-channel dedup files â each workflow only commits its own file, preventing
# merge conflicts when all three channels run concurrently in GH Actions.
BSG_LOG_FILE = BASE_DIR / "bsg_post_log.json"
TMF_LOG_FILE = BASE_DIR / "tmf_post_log.json"

# ââ Voice Settings âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
CHANNEL_VOICES = {
    "bsg": "en-US-JennyNeural",   # Jenny  â warm female (edge-tts; ElevenLabs Rachel retired May 2026)
    "tmf": "en-US-GuyNeural",     # Guy    â deep male (edge-tts; ElevenLabs Adam 401 issues May 2026)
}

CHANNEL_LABELS = {
    "bsg": "Bible Story Garden",
    "tmf": "The Mind Files",
}

# ââ Topic Banks ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# These cycle in random order â once all are used, the cycle resets.
# Add more topics here any time to expand the content library.

BSG_TOPICS = [
    "Noah's Ark â Why God Chose ONE Man to Save All Life on Earth",
    "David vs Goliath â How a Boy Defeated an IMPOSSIBLE Giant",
    "Moses Parted the Red Sea â The Most INCREDIBLE Miracle Ever",
    "The Birth of Jesus â The Night That Changed EVERYTHING",
    "Daniel in the Lion's Den â Thrown to Certain Death, He Survived the IMPOSSIBLE",
    "Jonah and the Whale â Swallowed Alive, But God Had Other Plans",
    "Joseph's Coat of Many Colors â From SLAVE to POWERFUL Ruler",
    "The Good Samaritan â A Stranger's Act of Compassion That Changed EVERYTHING",
    "Zacchaeus â The HATED Man Jesus Chose to Save",
    "The Prodigal Son â A Father's Love THAT Never Fails",
    "Jesus Feeds 5000 â How One Miracle Fed an IMPOSSIBLE Crowd",
    "Moses and the Ten Commandments â The MOMENT God Gave His Law",
    "Ruth and Naomi â From DESPAIR to HOPE Against All Odds",
    "Esther Saves Her People â A Queen's Brave Act Prevented GENOCIDE",
    "The Creation Story â How God Made EVERYTHING in 6 Days",
    "Adam and Eve â The FIRST Humans and Their Forbidden Choice",
    "Abraham and Isaac â A Father's ULTIMATE Test of Faith",
    "The Tower of Babel â Why God CONFUSED All Human Languages",
    "Elijah on Mount Carmel â Fire From Heaven DEFEATS 450 Prophets",
    "Saul's Conversion â From PERSECUTOR to Apostle in ONE MOMENT",
    "Jesus Walks on Water â He Did What SEEMED IMPOSSIBLE",
    "The Easter Story â Jesus ROSE FROM THE DEAD (Here's What Happened)",
    "The Christmas Story â The Night Jesus Was BORN (What Really Happened)",
    "Solomon Asks for Wisdom â God Granted Him EVERYTHING Else Too",
    "Gideon's 300 Warriors â How a TINY Army Defeated 135,000 Enemies",
    "Samson's Incredible Strength â Betrayed, Blinded, Yet He Destroyed His Enemies",
    "Joshua and the Walls of Jericho â They FELL by Simply Walking Around Them",
    "Lazarus Raised From the Dead â Dead 4 Days, Then Jesus Said ONE Thing",
    "Jesus Calms the Storm â His Disciples Watched Him DO the IMPOSSIBLE",
    "Peter Walks on Water â Until He Made ONE Mistake",
    "The Lost Sheep â Jesus Leaves 99 to Find ONE",
    "Shadrach, Meshach, Abednego â Thrown Into a Fiery Furnace, They SURVIVED",
    "Nehemiah Rebuilds Jerusalem â One Man's IMPOSSIBLE Mission to Rebuild the Walls",
    "Samuel Hears God's Voice â A Boy Chosen to Become a POWERFUL Prophet",
    "Deborah the Judge â A Woman Who DEFEATED an Entire Army",
    # Removed May 2026 (analytics confirm doctrine/teaching underperforms):
    # "Psalm 23" â no story arc, pure doctrine
    # "The Beatitudes" â moral teaching list, no action/conflict
    # "Mary and Martha" â low-stakes teaching moment
    # "David and Jonathan" â friendship theme, not high-stakes action
    # "Elisha and the Widow's Oil" â quiet miracle, limited visual spectacle
    # Added May 2026 â narrative-heavy, high-stakes, clear visual payoff:
    "The Ten Plagues of Egypt â God's Most DEVASTATING Display of Power",
    "Jacob Wrestles an Angel â The Night a Man Fought God and SURVIVED",
    "Paul and Silas in Prison â Chains FELL OFF at Midnight",
    "Balaam's Donkey â The Day a Donkey Spoke to SAVE a Prophet's Life",
    "The Transfiguration â Jesus Revealed His FULL GLORY on a Mountain",
    "Ananias and Sapphira â The Couple Who Lied to God and DIED Instantly",
    "Stephen's Stoning â The First Christian Martyr's FINAL Words",
    "The Feeding of 5000 â 5 Loaves, 2 Fish, 5,000 People FED",
    "Elijah Fed by Ravens â God Provided in the Most IMPOSSIBLE Way",
    "Jesus Clears the Temple â He Was FURIOUS and Flipped EVERYTHING",
    "Joshua Stops the Sun â God Made Time STAND STILL for One Battle",
]

# Topic mix is intentionally weighted:
#   ~55% dark-behavior / personality / manipulation (1.3%+ sub conversion in Apr data)
#   ~30% cognitive biases reframed with relational or behavioral stakes
#   ~15% classic experiments and uncomfortable-truth topics
# Weak-converting topics from the original list (Mere Exposure, Cocktail Party,
# Illusion of Transparency, abstract bias labels) have been dropped.

TMF_TOPICS = [
    # ââ Dark behavior / personality / manipulation (high sub conversion) ââ
    "The Dark Triad â Why Some People Charm You While Planning to Hurt You",
    "What Narcissists, Psychopaths and Sociopaths Actually Want From You",
    "Gaslighting â The Manipulation Most Victims Never See Coming",
    "Love Bombing â The Red Flag That Feels Like Romance",
    "Why Narcissists Target Empaths (And How They Pick Them)",
    "How Trauma Bonds Trap Victims With Their Abusers",
    "Why Charming People Are Often the Most Dangerous",
    "Why Abusers Always Apologize Before They Do It Again",
    "The 4 Tactics Every Cult Leader Uses On Their Followers",
    "The Psychology of Liars â 4 Tells That Give Them Away",
    "Dehumanization â How Ordinary People Become Capable of Cruelty",
    "The Milgram Experiment â Why 65% of People Will Hurt a Stranger",
    "The Stanford Prison Experiment â What Power Does to Good People",
    "How People Justify Cheating, Stealing, and Lying to Themselves",
    "Why You're Drawn to People Who Treat You Poorly",
    "The Hidden Reason Some People Enjoy Others' Failure",
    "Why Predators Always Test You Before They Strike",

    # ââ Cognitive biases reframed with behavioral stakes ââ
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
    "Why You Obey People in Positions of Power â Even Bad Ones",
    "Why The First Number You Hear Changes Every Decision You Make",
    "Why You Only See Evidence That Proves You Right",
    "Why You Judge Other People Harsher Than You Judge Yourself",
    "Why You Feel Compelled to Return Favors â Even From Bad People",
    "Why Your Brain Only Sees What It Wants To See",
    "Why You Keep Going Back to Things You Know Are Bad For You",

    # ââ Uncomfortable-truth / dark manipulation ââ
    "Why Most People Will Lie to Your Face and Believe They're Honest",
    "Why You Act Like a Completely Different Person Around Different People",
    "Why Smart People Still Make The Same Dumb Mistake Twice",
    "Why Narcissists Always Come Back After You Cut Them Off",
    "Why People Who Hurt You Act Like They're the Victim",
    "The Reason Nice People Are the Easiest to Manipulate",
    "Why You Freeze When Someone Confronts You With a Lie",
    "How Manipulators Use Silence as a Weapon Against You",
    "Why You Can't Trust Someone Who Never Admits They're Wrong",
    "Why Abusers Always Make You Feel Responsible for Their Behavior",
    "The Psychological Trick That Makes You Defend People Who Hurt You",
    "Why Dangerous People Always Seem Completely Normal at First",
    # Retired (soft behavioral, underperformed): procrastination, imposter syndrome,
    # planning fallacy, regret, tiredness â these drift away from dark psychology core.

    # ââ Cognitive bias + relatable behavior hybrids (added May 2026) ââââââââââ
    # Analytics confirmed: psychological mechanism framed as "Why You" behavior
    # outperforms pure toxic-relationship angles. Top performers blend both.
    "Why You Believe Lies You've Heard Twice â The Illusory Truth Effect",
    "Why Your Brain Ignores Logic When You're Emotionally Invested",
    "Why You Trust Someone More Just Because They Sound Confident",
    "Why You're Easier to Manipulate When You Think You're Immune",
    "Why You Give Away Your Power Without Realizing It",
    "Why You Misread Silence as Approval â And Manipulators Know It",
    "Why Smart People Are the Easiest to Fool With a Good Story",
    "Why You Remember Humiliation More Vividly Than Praise",
    "Why Being Watched Makes You Behave Differently â Even When You're Alone",
    "Why Your Brain Can't Tell the Difference Between Rejection and Physical Pain",
    "Why You Automatically Trust People Who Share One Thing in Common With You",
    "Why You Work Harder to Keep Something Than You Ever Did to Get It",
    "Why You Let People Interrupt You â And Why It's Not About Politeness",
    "Why You Assume Everyone Can See How Anxious You Really Are",
]

# ââ BSG Tier 1 stories (proven top performers â weighted 3Ã in topic selection) â
BSG_TIER1_KEYWORDS = [
    "noah", "david vs goliath", "moses parted", "birth of jesus",
    "daniel in the lion", "jonah", "joseph's coat", "adam and eve",
    "creation story", "easter story", "christmas story", "lazarus",
    "jesus walks on water", "jesus feeds 5000", "shadrach",
    "joshua and the walls", "elijah on mount carmel",
]

def _bsg_story_tier(topic: str) -> int:
    """Return 1 (Tier 1, weight 3Ã) or 2 (other, weight 1Ã)."""
    tl = topic.lower()
    for kw in BSG_TIER1_KEYWORDS:
        if kw in tl:
            return 1
    return 2


def _bsg_story_name(topic: str) -> str:
    """Extract core story name for dedup (text before first ' â ')."""
    return topic.split(" â ")[0].strip().lower()


# Canonical slug map: catches AI-generated title variations for the same story.
# Key = canonical slug, value = list of substrings that map to it.
_BSG_STORY_SLUGS: dict[str, list[str]] = {
    "daniel-lions-den":    ["daniel in the lion", "daniel's lion", "daniel and the lion"],
    "feeding-5000":        ["feeding 5,000", "feeding 5000", "jesus feeds 5,000", "jesus feeds 5000",
                            "feeding the 5,000", "feeds 5000", "feeds 5,000"],
    "good-samaritan":      ["good samaritan"],
    "prodigal-son":        ["prodigal son"],
    "moses-red-sea":       ["moses parts the red sea", "moses and the red sea", "moses red sea",
                            "parts the red sea", "red sea crossing"],
    "walls-of-jericho":    ["walls of jericho", "joshua's jericho", "joshua and the walls",
                            "wall of jericho", "jericho wall"],
    "david-goliath":       ["david and goliath", "david vs goliath", "david versus goliath"],
    "elijah-fire":         ["elijah's fiery", "elijah on mount carmel", "elijah and the fire",
                            "elijah's fire", "fire from heaven", "fiery challenge", "fiery showdown",
                            "elijah's challenge"],
    "noahs-ark":           ["noah's ark"],
    "deborah-judge":       ["deborah the judge", "deborah: the brave", "deborah brave judge"],
    "joseph-coat":         ["joseph's coat", "joseph and the coat", "coat of many colors"],
    "samson-strength":     ["samson and the lion", "samson's strength", "samson's incredible",
                            "samson's incredible strength"],
    "samson-chains":       ["samson breaks his chains", "samson breaks the chains",
                            "samson breaks", "samson and delilah"],
    "elisha-oil":          ["elisha's oil", "elisha's impossible oil"],
    "zacchaeus":           ["zacchaeus"],
    "ten-commandments":    ["ten commandments", "moses & the ten", "moses and the ten"],
    "ten-plagues":         ["ten plagues", "the plagues of egypt", "plagues of egypt",
                            "ten plagues of egypt", "god's devastating", "plague of frogs",
                            "plague of locusts", "plague of darkness"],
    "birth-of-jesus":      ["birth of jesus", "christmas bible story", "christmas story"],
    "easter-story":        ["easter story", "resurrection of jesus"],
    "jonah-whale":         ["jonah and the whale", "jonah swallowed", "jonah in the whale",
                            "jonah whale", "swallowed by the whale"],
    "shadrach-furnace":    ["shadrach in the fiery furnace", "shadrach meshach abednego",
                            "fiery furnace", "thrown into a fiery furnace"],
    "jesus-calms-storm":   ["jesus calms the storm", "calms the storm", "jesus calms storm",
                            "storm on the sea", "peace be still"],
    "elijah-ravens":       ["elijah fed by ravens", "elijah and the ravens", "fed by ravens"],
    "jacob-wrestles":      ["jacob wrestles", "jacob and the angel", "wrestles an angel",
                            "wrestles with god"],
    "paul-silas-prison":   ["paul and silas in prison", "paul and silas", "chains fell off"],
    "jesus-walks-water":   ["jesus walks on water", "walks on water", "peter walks on water"],
    "lazarus":             ["lazarus raised", "raising of lazarus", "lazarus from the dead",
                            "lazarus dead 4 days"],
    "gideon":              ["gideon's 300", "gideon and his", "gideon's army"],
    "joshua-stops-sun":    ["joshua stops the sun", "sun stood still", "god made time stand still"],
}


def _bsg_story_slug(topic: str) -> str:
    """Return a canonical story slug for dedup. Catches AI title variations."""
    name = _bsg_story_name(topic)
    for slug, aliases in _BSG_STORY_SLUGS.items():
        if any(alias in name for alias in aliases):
            return slug
    return name  # fallback: use normalized name as-is


def _bsg_story_posted_recently(topic: str, days: int = 60) -> bool:
    """True if the same Bible story (by canonical slug) was posted within `days` days.
    Uses per-channel log for reliable persistence across GH Actions runs.
    NOTE: kept for backward compatibility â new code should call _bsg_story_ever_posted()."""
    log = _load_channel_log("bsg")
    slug = _bsg_story_slug(topic)
    cutoff = datetime.now(ZoneInfo("America/Chicago")) - timedelta(days=days)
    for post in log.get("posts", []):
        if post.get("channel") != "bsg":
            continue
        try:
            post_dt = datetime.strptime(post.get("posted_at", ""), "%Y-%m-%d %H:%M:%S")
            post_dt = post_dt.replace(tzinfo=ZoneInfo("America/Chicago"))
        except ValueError:
            continue
        if post_dt < cutoff:
            continue
        if _bsg_story_slug(post.get("topic", "")) == slug:
            return True
    return False


def _bsg_story_ever_posted(topic: str) -> bool:
    """True if this Bible story (by canonical slug) has EVER been posted on BSG.
    Enforces the hard rule: one canonical version per story, ever.
    Replaces the 60-day rolling window that allowed Daniel 4x / Jericho 5x / David 4x."""
    log = _load_channel_log("bsg")
    slug = _bsg_story_slug(topic)
    for post in log.get("posts", []):
        if post.get("channel") != "bsg":
            continue
        if _bsg_story_slug(post.get("topic", "")) == slug:
            return True
    return False


# ââ TMF 14-day concept-level dedup ââââââââââââââââââââââââââââââââââââââââââââ
# Window raised from 7â14 days: at 2x/day (14 posts/week), a 7-day window was
# too narrow â exact-title duplicates slipped through on the boundary day.

_TMF_STOP_WORDS = {
    "your", "you're", "that", "they", "their", "with", "from", "have", "this",
    "even", "most", "some", "when", "what", "will", "more", "less", "just",
    "very", "always", "never", "every", "been", "after", "before", "into",
    "people", "person", "someone", "other", "about", "while", "think", "feel",
}

def _topic_keywords(topic: str) -> set:
    """Extract meaningful 5+ char keywords from a topic string."""
    words = _re_imports.findall(r"[a-z]+", topic.lower())
    return {w for w in words if len(w) >= 5 and w not in _TMF_STOP_WORDS}


def _tmf_topic_too_similar_to_recent(topic: str, days: int = 14) -> bool:
    """True if this topic shares â¥2 concept keywords with any TMF post in the last 14 days.
    Prevents toxic/guilt/manipulation cluster saturation. Uses per-channel log."""
    log = _load_channel_log("tmf")
    cutoff = datetime.now(ZoneInfo("America/Chicago")) - timedelta(days=days)
    candidate_kw = _topic_keywords(topic)
    if not candidate_kw:
        return False
    for post in log.get("posts", []):
        if post.get("channel") != "tmf":
            continue
        try:
            posted_str = post.get("posted_at", "")
            post_dt = datetime.strptime(posted_str, "%Y-%m-%d %H:%M:%S")
            post_dt = post_dt.replace(tzinfo=ZoneInfo("America/Chicago"))
        except ValueError:
            continue
        if post_dt < cutoff:
            continue
        recent_kw = _topic_keywords(post.get("topic", ""))
        if len(candidate_kw & recent_kw) >= 2:
            return True
    return False


# ââ Topic Log ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def _channel_log_file(channel: str) -> Path:
    """Return the per-channel log file path."""
    return BSG_LOG_FILE if channel == "bsg" else TMF_LOG_FILE if channel == "tmf" else LOG_FILE


def _load_channel_log(channel: str) -> dict:
    """Load per-channel log, merging any legacy entries from the shared log."""
    ch_file = _channel_log_file(channel)
    data: dict = {"posts": [], channel: []}
    if ch_file.exists():
        try:
            data = json.loads(ch_file.read_text())
        except Exception:
            pass
    # Backwards compat: pull in any entries from shared log not yet in channel file
    if LOG_FILE.exists():
        try:
            shared = json.loads(LOG_FILE.read_text())
            existing_ats = {p.get("posted_at") for p in data.get("posts", [])}
            for p in shared.get("posts", []):
                if p.get("channel") == channel and p.get("posted_at") not in existing_ats:
                    data.setdefault("posts", []).append(p)
            existing_topics = set(data.get(channel, []))
            for t in shared.get(channel, []):
                if t not in existing_topics:
                    data.setdefault(channel, []).append(t)
        except Exception:
            pass
    return data


def _save_channel_log(channel: str, log: dict) -> None:
    """Save to per-channel file (primary) and update shared log (compat)."""
    _channel_log_file(channel).write_text(json.dumps(log, indent=2))
    # Keep shared log updated for any tooling that reads it
    try:
        shared: dict = {"bsg": [], "tmf": [], "posts": []}
        if LOG_FILE.exists():
            shared = json.loads(LOG_FILE.read_text())
        shared_ats = {p.get("posted_at") for p in shared.get("posts", []) if p.get("channel") == channel}
        for p in log.get("posts", []):
            if p.get("posted_at") not in shared_ats:
                shared.setdefault("posts", []).append(p)
        shared[channel] = log.get(channel, [])
        LOG_FILE.write_text(json.dumps(shared, indent=2))
    except Exception:
        pass


def load_log() -> dict:
    """Load the shared topic usage log (legacy â new code uses _load_channel_log)."""
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text())
        except Exception:
            pass
    return {"bsg": [], "tmf": [], "posts": []}


def save_log(log: dict) -> None:
    LOG_FILE.write_text(json.dumps(log, indent=2))


def pick_topic(channel: str) -> str:
    """Pick a topic not yet used in this cycle, applying channel-specific guardrails.

    BSG: 60-day story slug dedup + Tier 1 weighted selection (proven stories 3Ã more likely).
    TMF: 14-day concept-overlap dedup (prevents toxic/guilt cluster saturation).
    Both now use per-channel log files for reliable GH Actions persistence.
    """
    log = _load_channel_log(channel)
    topics = BSG_TOPICS if channel == "bsg" else TMF_TOPICS
    used = set(log.get(channel, []))

    # ââ First pass: full guard (cycle dedup + channel-specific dedup) ââââââââââ
    if channel == "bsg":
        available = [
            t for t in topics
            if t not in used and not _bsg_story_ever_posted(t)
        ]
    elif channel == "tmf":
        available = [
            t for t in topics
            if t not in used and not _tmf_topic_too_similar_to_recent(t, days=14)
        ]
    else:
        available = [t for t in topics if t not in used]

    # ââ Cycle reset: all topics used (or all exhausted by strict dedup) ââââââââ
    if not available:
        print(f"  ð All {len(topics)} topics used (or filtered by dedup) â starting new cycle!")
        log[channel] = []
        _save_channel_log(channel, log)
        # Second pass: loosen cycle dedup only â keep slug/concept dedup
        # BSG: permanent dedup is intentional â if all stories exhausted, add new ones to BSG_TOPICS
        if channel == "bsg":
            available = [t for t in topics if not _bsg_story_ever_posted(t)]
        elif channel == "tmf":
            available = [t for t in topics if not _tmf_topic_too_similar_to_recent(t, days=14)]
        if not available:
            available = topics[:]  # Last resort: pick from full bank

    # ââ BSG: Tier 1 weighted selection âââââââââââââââââââââââââââââââââââââââââ
    if channel == "bsg":
        weights = [3 if _bsg_story_tier(t) == 1 else 1 for t in available]
        chosen = random.choices(available, weights=weights, k=1)[0]
        tier_label = "Tier 1 (3Ã)" if _bsg_story_tier(chosen) == 1 else "Tier 2"
        print(f"  ð BSG topic selected [{tier_label}]: {chosen[:70]}...")
        return chosen

    return random.choice(available)


def mark_posted(channel: str, topic: str, title: str, url: str) -> None:
    """Record a successful post so the topic is not repeated.
    Writes to per-channel log file (reliable GH Actions persistence)."""
    log = _load_channel_log(channel)
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
    _save_channel_log(channel, log)
    append_to_google_sheets(channel, title, url)


# ââ Validators (post-generation guardrails) ââââââââââââââââââââââââââââââââââ
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

# Hook phrases that are burned out / cannibalizing (Jun 7 2026 analytics).
# These may appear in a script body but NEVER as the title's core hook.
_TMF_BANNED_HOOK_PHRASES = [
    "toxic manipulator",
    "toxic manipulators",
    "toxic relationship",
    "toxic relationships",
    "toxic people",
    "charming manipulator",
    "manipulation red flags",
]

def _contains_banned_hook(title: str) -> bool:
    """True if title contains a burned-out hook phrase (case-insensitive)."""
    t = title.lower()
    return any(phrase in t for phrase in _TMF_BANNED_HOOK_PHRASES)

def _normalize_title(t: str) -> str:
    """Lowercase + strip punctuation/whitespace for fuzzy comparison."""
    s = (t or "").lower()
    s = _re.sub(r"[^a-z0-9 ]+", " ", s)
    return _re.sub(r"\s+", " ", s).strip()

def title_passes_tmf_rules(title: str) -> tuple[bool, str]:
    """
    Returns (ok, reason). False reason gets fed back into the retry prompt.
    Mirrors the TITLE RULES inside the system prompt â these are enforced here
    because gpt-4o regularly ignores them otherwise.
    """
    if not title or not title.strip():
        return False, "empty title"
    t = title.strip()

    if len(t) > 65:
        return False, f"title too long ({len(t)} chars; keep under 60)"

    # MUST start with "Why You" or "Why Your" â data shows this pattern drives 400-1300 views
    # vs "The [noun]" or other patterns averaging <50 views. Enforced May 6 2026.
    t_lower = t.lower()
    if not (t_lower.startswith("why you") or t_lower.startswith("why your")):
        return False, (
            'title must start with "Why You" or "Why Your" â '
            'e.g. "Why You Stay Loyal to Mean People". '
            'Data: "Why You..." titles avg 400-1300 views; other patterns avg <50 views. '
            'Rewrite as "Why You [verb] [observable behavior]".'
        )

    # No colon mid-title â kills CTR ("Why You're Right: The Mind Trap" flopped)
    if ":" in t:
        return False, 'no colon in title â "Why You [behavior]" only, no subtitle after colon'

    # Jun 7 2026: ban burned-out hook phrases as title hooks (toxic manipulator cluster)
    if _contains_banned_hook(t):
        banned = next(p for p in _TMF_BANNED_HOOK_PHRASES if p in t.lower())
        return False, (
            f'banned hook phrase in title: "{banned}". '
            'This cluster is burned out (380â291â185 view decay). '
            'Rewrite around a specific behavior â e.g. "Why You Trust People Who Lie to You."'
        )

    return True, ""

def script_word_count_ok(script: dict) -> tuple[bool, int]:
    """Total narration words must land in 140â180 (â42â55 sec at ~3.3 words/sec TTS rate).
    Recalibrated Jun 7 2026: May 10âJun 7 analytics show top-7 videos all 42â55s.
    Longer videos (65â80s) are underperforming relative to that cohort.
    Previous target was 300â370w (May 6 2026) â superseded by this window's data.
    """
    total = 0
    for scene in script.get("scenes", []):
        total += len((scene.get("narration") or "").split())
    return (140 <= total <= 180), total

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
# 5â7 videos on a single day, which Apr 2026 analytics showed dilutes the
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
            f"\nð Burst-guard: {label} already has {today_n} successful posts today "
            f"(cap = {cap}). Skipping this run to protect algorithmic distribution.\n"
            f"   To override (rare â e.g., recovering from a failed run), set "
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
            "Image prompts MUST feature a young woman (25â35) as the emotional focal point â this is data-backed: female-portrait images outperform all other visuals on this channel. "
            "Each prompt should describe: (1) what the woman is doing or feeling, (2) the lighting source, (3) the environment or background. "
            "She should feel psychologically present â pensive, guarded, introspective, or emotionally raw. Never smiling or posed. "
            "Examples: 'woman staring at her own reflection in a cracked mirror, single candle, dark room' / "
            "'woman sitting alone at a diner table at 2am, neon light through rain window, looking down' / "
            "'close-up of woman's face half in shadow, tears on cheek, blurred city lights behind her'. "
            "Style: cinematic, film noir, desaturated, photorealistic editorial photography. No text, no logos."
        )
    else:
        style_guide = (
            "Bible story / children's educational content for families with young kids. "
            "Tone: warm, wonder-filled, simple, encouraging. "
            "Image prompts should be colorful, cheerful storybook illustration style. "
            "Scene 1 MUST be a dramatic hook that stops scrolling. "
            "Scene 1 image: VISUALLY STRIKING â bold colors, dramatic moment."
        )

    # TMF-specific retention/title rules. These are data-backed from the Mar 22 â Apr 18
    # analytics: top 6 videos = 56% of all views; pure-jargon titles avg ~20 views;
    # 90+ sec videos avg ~40 views; False Consensus had 78.7% swipe-away at 0:32 of 1:16.
    if channel == "tmf":
        channel_rules = """
TITLE RULES (strict â titles drive 20Ã view differences in this channel):
- MUST start with "Why You" or "Why Your". This is the #1 rule. No exceptions.
- Lead with the CONTRADICTION or UNSETTLING PAYOFF â pair a trusted/positive action with a dark outcome.
  GOOD: "Why You Trust Liars Who Feel Honest" (802 views) â trusted action + dark outcome
  GOOD: "Why You Defend Those Who Hurt You" (598 views) â contradiction
  BAD:  "Why You Attract Toxic Manipulators" â flat category label, no contradiction
- Under 60 characters. Front-load the surprising word.
- No colon mid-title. If your draft doesn't start with "Why You/Your", REWRITE it.
- On TEST VEIN titles only: you may append the named effect in brackets for authority â
  e.g. "Why You're Nicer to Strangers [Spotlight Effect]". Use sparingly to test CTR.

TOPIC SELECTION â PILLAR MIX (enforce this ratio every batch):

  PILLAR 1 â TRUST / DECEPTION / BETRAYAL (~40%) â proven #1 vein
  Pattern: "Why You [trust/defend/forgive/believe] [person who does a bad thing]"
  Top performers: Trust Liars Who Feel Honest (802), Trust Those Who Never Apologize (778),
  Defend Those Who Hurt You (598), Trust Those Who Deceive (669).
  Mine: trust + calm/silence, forgive + betrayal, believe + contradiction, defend + harm.

  PILLAR 2 â MEMORY & EMOTIONAL DISTORTION (~25%) â proven #2 vein
  Test: why insults are remembered word-for-word, why embarrassing moments replay for years,
  false memories, hindsight bias, why one bad thing erases ten good ones, negativity bias,
  recency bias, why your worst memory feels most true.

  PILLAR 3 â TEST VEINS (~25%) â rotate to find the next winner
  Active rotation: cognitive biases (confirmation bias, illusory truth, framing effect),
  social hierarchy / status games, personality pathology mechanics (narcissism, psychopathy â
  frame as "why you [behavior around them]", NOT "how to spot").

  PILLAR 4 â SELF-PERCEPTION / SOCIAL CONTRADICTION (~10%)
  Pattern: behavior toward others that contradicts self-image.
  Proven: "Why You're Nicer to Strangers" (704 views). Mine the contradiction angle.

HARD RULES (enforced in code â violating these triggers a retry):
  1. BANNED TITLE HOOKS: Never use toxic manipulator(s), toxic relationship(s), toxic people,
     charming manipulator, manipulation red flags as the title's core hook. Burned out.
     (May appear inside the script body â just not in the title.)
  2. NO CONCEPT REPEATS within 30 days. Core idea must not duplicate a recent title.
  3. NO standalone time/procrastination/deadline titles â only allowed if reframed as
     memory or identity distortion (e.g. "Why You Remember Every Task You Left Unfinished").
  4. LENGTH: 42â55 seconds = 140â180 narration words. Enforced by word-count validator.

HOOK RULES (first 0â5 sec):
- Scene 1 = hook. First 3â4 words must carry the tension. Drop the viewer mid-claim.
- BANNED openers: "Most peopleâ¦", "Have you everâ¦", "Did you knowâ¦", "Imagineâ¦"
- Open with the unsettling claim itself. Use "you" within the first two sentences.
- Scene 2 must DEEPEN or PAY OFF the hook â never pivot or define a term.
- Never name the academic effect until scene 4 or later.

HOOK VARIANTS (REQUIRED â produce all 3. Algorithm penalizes repeated hook patterns):
  shocking_claim   â Flat, specific, uncomfortable truth stated as fact. No question mark.
                     Example: "You've already decided. You just don't know it yet."
  uncomfortable_question â Second-person question the viewer can't say no to.
                     Example: "Have you noticed you work harder to keep things you hate than to gain what you want?"
  behavioral_contradiction â Open with a paradox: two behaviors that contradict each other and both feel true.
                     Example: "The smarter someone is, the worse they are at spotting their own blind spots."

The script's Scene 1 narration = shocking_claim variant (default). Produce all 3 in hook_variants.

BODY & PAYOFF:
- Sentences average 10â14 words. Short, punchy, spoken rhythm.
- Use "you" at least 3 times â create personal confrontation.
- Final scene = an uncomfortable reframe. Not a motivational quote. Not a call to action.
- Leave the viewer slightly disturbed, thinking, re-examining their own behavior.
"""
    else:
        channel_rules = """
TITLE RULES (strict â must match EXACTLY this format):
- FORMAT: [Story Name] [single emoji] | Bible Story for Kids | Bible Story Garden
- The emoji must signal the DRAMATIC BEAT of the story â not a generic symbol:
    ð whale/sea creature  ð¥ fire/furnace  ðº trumpet/walls  ðª strength/chains
    âï¸ battle/giant  ð sea/flood/storm  ð´ talking animal  ð¦ lion  ð¸ plague/animals
- Story name = most action/drama-forward phrasing possible. Under 40 chars before the pipe.
- GOOD examples (data-backed top performers):
  â¢ "Balaam's Donkey ð´ | Bible Story for Kids | Bible Story Garden"
  â¢ "Daniel in the Lion's Den ð¦ | Bible Story for Kids | Bible Story Garden"
  â¢ "Elijah Calls Down Fire ð¥ | Bible Story for Kids | Bible Story Garden"
  â¢ "Jonah Swallowed by the Whale ð | Bible Story for Kids | Bible Story Garden"
  â¢ "Noah's Ark ð | Bible Story for Kids | Bible Story Garden"
  â¢ "David vs Goliath âï¸ | Bible Story for Kids | Bible Story Garden"
- BAD examples (confirmed 0-view format breaks â never reproduce these):
  â¢ "Jonah and the Whale: The Prophet Who Ran from God" â colon/subtitle format, BANNED
  â¢ "Paul on the Road to Damascus: The Most Dramatic Conversion" â colon, BANNED
  â¢ "Elisha's Impossible Oil Miracle" â missing tail entirely, BANNED
  â¢ "Deborah: The Brave Judge" â missing format, BANNED
- If your title doesn't follow the EXACT format, REWRITE it. No exceptions.

STORY SELECTION â DRAMA AND VISUAL PAYOFF FIRST (Jun 2026 analytics update):
- TIER 1 (highest-performing â action/animal/spectacle): Balaam's Donkey, Daniel in the Lion's Den,
  Elijah Calls Down Fire, David vs Goliath, Moses Parted the Red Sea, Noah's Ark,
  Jonah Swallowed by the Whale, Samson Breaks His Chains, The Ten Plagues of Egypt,
  Jesus Calms the Storm, Shadrach in the Fiery Furnace, The Walls of Jericho Fall,
  Gideon's 300 Warriors, Joshua Stops the Sun, Jesus Feeds 5000
- TIER 2 (strong visual payoff): Lazarus Raised from the Dead, Jesus Walks on Water,
  Jacob Wrestles the Angel, Peter Walks on Water, Paul and Silas in Prison,
  Esther Saves Her People, Joseph Sold by His Brothers
- TIER 3 (use sparingly â must reframe around a single dramatic moment): quiet/relational stories
- NEVER pick: verse cards, the Beatitudes, pure-teaching parables without physical conflict,
  out-of-season content (Christmas outside NovâDec, Easter outside MarâApr)

ACTION GATE (hard rule â if a story fails this, output "has_action_gate": false and stop):
Every script MUST have ALL FOUR:
  1. A named character facing danger or an impossible situation
  2. A specific dramatic moment (the lion attacks, the walls shake, the whale swallows)
  3. A turning point where God intervenes in a physically visible, dramatic way
  4. A concrete, visible outcome (character survives / enemy falls / sea parts / fire doesn't burn)
Signal in your JSON with: "has_action_gate": true
If any of the four are absent, output "has_action_gate": false â do not write the full script.

HOOK RULES:
- Scene 1: Drop into the peak dramatic moment. No setup. No "One day..." or "Long ago..."
- Scene 2: Deepen the stakes â who is this person, what impossible thing is happening?
- Never open with context-setting or character backstory. Start mid-action.

HOOK VARIANTS (REQUIRED â produce all 3 every time; pipeline rotates to prevent suppression):
  dramatic_peak    â Opens with the most visually shocking beat of the story as a flat statement.
                     Example: "A whale swallowed him whole. He was still alive inside."
  impossible_odds  â Opens with scale or numbers that make the situation feel hopeless.
                     Example: "One boy. One stone. One giant the size of a house."
  direct_question  â A second-person question that puts the viewer inside the scene.
                     Example: "What would you do if you were thrown into a furnace alive?"

IMAGE PROMPT RULES (critical â vague prompts produce identical AI images across videos):
- Every image_prompt MUST contain: (1) specific character name, (2) exact action they are
  doing RIGHT NOW in this scene, (3) specific location or environmental detail.
- BAD: "biblical figure in a landscape" â generic, produces same image every time.
- BAD: "colorful scene from the Bible" â completely generic.
- GOOD: "Jonah tumbling headfirst into the open jaws of a massive dark whale, ocean spray everywhere, stormy sky"
- GOOD: "Three boys â Shadrach, Meshach, Abednego â standing unharmed inside a roaring orange furnace, flames all around, calm expressions"
- GOOD: "Young David releasing a stone from his leather sling aimed at the towering giant Goliath in a rocky canyon"
- Scene 1 image_prompt: the single most dramatic PEAK visual â the moment that stops scrolling.

THUMBNAIL SPEC (REQUIRED â every video must include this; missing = invalid output):
Add a "thumbnail_spec" object to your JSON output:
{
  "thumbnail_spec": {
    "focal_subject": "One sentence: the single focal image at center of frame â the peak action/animal/moment (e.g., 'Jonah falling headfirst into the open mouth of a massive dark whale against a stormy sky')",
    "overlay_words": "2â4 ALL-CAPS words maximum â kid-legible at phone size with thick outline (e.g., 'SWALLOWED ALIVE' or 'GIANT FALLS' or 'WALLS COME DOWN')",
    "character_emotion": "One word: the dominant emotion on the main character's face (e.g., 'terror', 'awe', 'defiance', 'shock', 'wonder', 'joy')"
  }
}
Do not omit thumbnail_spec. A script without it is incomplete and will be rejected.
"""

    system_prompt = f"""You are a short-form video script writer for YouTube Shorts.

TARGET LENGTH: 42â55 seconds. NEVER under 40 or over 60 seconds.
- Total narration across ALL scenes combined: 140â180 words. Do not go below 140 or above 180.
- TTS speaks at ~3.3 words/sec. 140w = ~42s, 180w = ~55s. Hit this range every time.
- Jun 7 2026 data: top-7 TMF videos (462â802 views) all landed 42â55s. Keep scripts tight.

Channel style: {style_guide}
{channel_rules}
Output ONLY valid JSON in this exact format:
{{
  "title": "Title following TITLE RULES above",
  "hook_variants": {{
    "shocking_claim":            "<Scene 1 narration, shocking_claim style, 10â18 words>",
    "uncomfortable_question":    "<Scene 1 narration, uncomfortable_question style, 10â18 words>",
    "behavioral_contradiction":  "<Scene 1 narration, behavioral_contradiction style, 10â18 words>"
  }},
  "scenes": [
    {{
      "narration": "Spoken narration, 20â32 words, sentences averaging 10â14 words.",
      "image_prompt": "Vivid scene description for AI image generation. Be specific."
    }}
  ]
}}

Structural rules:
- Exactly {num_scenes} scenes
- SCENE 1 follows HOOK RULES above â shortest scene, highest tension
- Each image_prompt: specific, visual, cinematic â NOT abstract.
- No markdown, no explanation, ONLY the JSON object

PROSE QUALITY â NO AI TELLS (applies to every narration field):
- No adverbs. Cut "deeply," "truly," "completely," "suddenly," "ultimately," "essentially," "clearly."
- Active voice only. Every sentence needs a human subject doing something. Not: "The behavior is driven by fear." â "Fear drives the behavior."
- No inanimate subjects performing human actions. Not: "The pattern emerges from childhood." â "Children learn this pattern early."
- No em-dashes anywhere in narration.
- No throat-clearing openers: "What this means is," "Here's the thing," "It's worth noting," "In other words," "Make no mistake," "The truth is."
- Two items beat three. Cut the third item from every list.
- Vary sentence rhythm. Never three consecutive sentences of matching length."""

    try:
        import openai
        # ââ Model backend: DeepSeek V3 primary (95% cheaper), GPT-4o fallback ââ
        deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        openai_client = openai.OpenAI(api_key=api_key)   # always available as fallback
        if deepseek_key:
            client = openai.OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
            model_name = "deepseek-chat"
            _fallback_available = True
            print(f"    Connecting to DeepSeek API (deepseek-chat)...")
        else:
            client = openai_client
            model_name = "gpt-4o"
            _fallback_available = False
            print(f"    Connecting to OpenAI API (gpt-4o)...")

        user_msg = f"Write a {num_scenes}-scene script about: {topic}"
        extra_constraints = ""  # accumulated feedback for retries
        last_script: dict | None = None
        last_title_reason = ""
        last_word_count = 0

        # Up to 3 attempts for both TMF and BSG â title format is critical for both.
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            print(f"    Making script generation request (attempt {attempt}/{max_attempts})...")
            messages = [
                {"role": "system", "content": system_prompt + extra_constraints},
                {"role": "user", "content": user_msg},
            ]
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=2000,
                    temperature=0.8,
                )
            except Exception as api_err:
                if _fallback_available:
                    print(f"    â ï¸  DeepSeek failed ({type(api_err).__name__}: {str(api_err)[:80]})")
                    print(f"    ð Falling back to GPT-4o...")
                    client = openai_client
                    model_name = "gpt-4o"
                    _fallback_available = False
                    resp = client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        max_tokens=2000,
                        temperature=0.8,
                    )
                else:
                    raise
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            script = json.loads(raw.strip())
            last_script = script

            # ââ Channel-specific guardrails ââ
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
                        f"(must be 140â180 words = 42â55s at ~3.3 words/sec TTS rate)"
                    )
                    last_word_count = word_count
                if dup:
                    problems.append(
                        f'DUPLICATE FAIL: title "{script.get("title")}" already published â pick a different angle.'
                    )

                if not problems:
                    print(f"    â Script passed validators (title + {word_count}w + unique)")
                    # ââ Hook rotation (suppression filter) ââââââââââââââââââ
                    # YouTube 2026 penalises channels that repeat the same
                    # hook style every video. Rotate across the 3 variants so
                    # the channel never looks like a format-farm to the algo.
                    hook_variants = script.get("hook_variants", {})
                    HOOK_STYLES = [
                        "shocking_claim",
                        "uncomfortable_question",
                        "behavioral_contradiction",
                    ]
                    available_hooks = {
                        k: v for k, v in hook_variants.items()
                        if k in HOOK_STYLES and isinstance(v, str) and v.strip()
                    }
                    if available_hooks:
                        chosen_style = random.choice(list(available_hooks))
                        chosen_hook  = available_hooks[chosen_style].strip()
                        if script.get("scenes") and chosen_hook:
                            script["scenes"][0]["narration"] = chosen_hook
                            script["_hook_style_used"] = chosen_style
                            print(f"    ð£ Hook style selected: {chosen_style}")
                    return script

                print(f"    â ï¸  Validator problems on attempt {attempt}: {' | '.join(problems)}")
                extra_constraints = (
                    "\n\nIMPORTANT â your previous draft was REJECTED for these reasons:\n- "
                    + "\n- ".join(problems)
                    + "\nFix ALL of them in this next draft. The title MUST start with \"Why You\" or \"Why Your\" "
                      "and describe an observable behavior the viewer recognizes in themselves. No colons. "
                      "Total narration MUST be 140â180 words across all scenes combined. "
                      "TTS speaks at ~3.3 words/sec â 140w = 42s, 180w = 55s. Keep scripts tight."
                )
            else:
                # BSG title validator â enforce "X emoji | Bible Story for Kids | Bible Story Garden" format
                title = (script.get("title") or "").strip()
                bsg_format_ok = "| Bible Story for Kids | Bible Story Garden" in title
                if not bsg_format_ok:
                    print(f"    â ï¸  BSG title format FAIL on attempt {attempt}: \"{title}\"")
                    extra_constraints = (
                        f"\n\nIMPORTANT â your previous draft was REJECTED. "
                        f"Title was: \"{title}\"\n"
                        f"The BSG title MUST follow this EXACT format: "
                        f"[Story Name] [single emoji] | Bible Story for Kids | Bible Story Garden\n"
                        f"Examples: \"Noah's Ark ð | Bible Story for Kids | Bible Story Garden\"\n"
                        f"          \"David vs Goliath âï¸ | Bible Story for Kids | Bible Story Garden\"\n"
                        f"Rewrite the title to match this format exactly. No exceptions."
                    )
                    continue

                print(f"    â BSG title validator: {title}")

                # ââ BSG action gate validator ââââââââââââââââââââââââââââââââââ
                if not script.get("has_action_gate", True):
                    print(f"    â ï¸  BSG action gate FAIL on attempt {attempt}: story lacks dramatic peak")
                    extra_constraints = (
                        "\n\nIMPORTANT â your previous draft FAILED the action gate. "
                        "The story needs ALL FOUR: (1) named character in danger, "
                        "(2) specific dramatic moment, (3) physical divine intervention, "
                        "(4) a visible concrete outcome. "
                        "Reframe around the most dramatic moment in the story, or pick a more action-forward story."
                    )
                    continue
                print(f"    â BSG action gate: passed")

                # ââ BSG thumbnail spec validator âââââââââââââââââââââââââââââââ
                thumb = script.get("thumbnail_spec", {})
                thumb_ok = (
                    isinstance(thumb, dict)
                    and bool((thumb.get("focal_subject") or "").strip())
                    and bool((thumb.get("overlay_words") or "").strip())
                    and bool((thumb.get("character_emotion") or "").strip())
                )
                if not thumb_ok:
                    print(f"    â ï¸  BSG thumbnail_spec missing/incomplete on attempt {attempt}")
                    extra_constraints = (
                        "\n\nIMPORTANT â your previous draft was REJECTED: missing thumbnail_spec. "
                        "You MUST include a 'thumbnail_spec' object with three fields: "
                        "focal_subject (one sentence describing the peak action/image), "
                        "overlay_words (2â4 ALL-CAPS words only), and "
                        "character_emotion (one word). Do not omit it."
                    )
                    continue
                print(f"    â BSG thumbnail_spec: '{thumb.get('overlay_words')}' / {thumb.get('character_emotion')}")

                return script

        # All retries exhausted: intentionally skip this post rather than publish a bad title.
        # This is EXPECTED behavior, not a code error â exit 0 so GH Actions shows green.
        raise ValueError(
            f"TITLE_VALIDATION_SKIP: All {max_attempts} attempts failed â "
            f"last title: \"{(last_script or {}).get('title', 'n/a')}\" | "
            f"reason: {last_title_reason or 'format mismatch'}"
        )

    except json.JSONDecodeError as e:
        raise ValueError(f"OpenAI returned invalid JSON: {str(e)[:100]}")
    except ConnectionError as e:
        raise RuntimeError(f"Network error connecting to OpenAI: {str(e)[:120]}")
    except Exception as e:
        error_type = type(e).__name__
        raise RuntimeError(f"Script generation failed ({error_type}): {str(e)[:150]}")


def append_to_google_sheets(channel: str, title: str, url: str, status: str = "Success") -> None:
    """Append posted video to Google Sheets Auto-Post Log (GitHub Actions only)."""
    # Only run in GitHub Actions environment
    if not os.getenv("GITHUB_ACTIONS"):
        return

    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        print("â ï¸  Google API libraries not available for Sheets logging")
        return

    try:
        # Load service account credentials from GitHub secret
        creds_json = os.getenv("GOOGLE_SHEETS_KEY")
        if not creds_json:
            print("  â GOOGLE_SHEETS_KEY secret is EMPTY or not set in GitHub")
            return

        print(f"  â GOOGLE_SHEETS_KEY found ({len(creds_json)} chars)")
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

        row = [timestamp, channel_label, title, status, url, ""]

        # Append to sheet
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:G",
            valueInputOption="USER_ENTERED",
            body={"values": [row]}
        ).execute()

        print(f"  ð Logged to Google Sheets: {channel_label} â {title}")

    except Exception as e:
        # Log error but don't break the workflow
        import traceback
        error_msg = f"Sheets logging failed: {str(e)[:100]}"
        print(f"  â ï¸  {error_msg}")
        # Still save locally for debugging
        print(f"     (Video posted but not logged to Sheets. Check logs.)")


# ââ Dependency Management ââââââââââââââââââââââââââââââââââââââââââââââââââââââ

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

    print(f"  ð¦ Installing missing packages: {', '.join(needed)}")
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
            print(f"  â Packages installed successfully.")
            return True
        else:
            err = result.stderr.decode("utf-8", errors="replace")[:200]
            print(f"  â ï¸ pip install failed: {err}")
            return False
    except Exception as e:
        print(f"  â ï¸ Could not install packages: {e}")
        return False


# ââ Server Management ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

SERVER_URL = "http://localhost:5002"


def server_running() -> bool:
    try:
        urllib.request.urlopen(SERVER_URL, timeout=2)
        return True
    except Exception:
        return False


def wait_for_server(timeout: int = 60) -> bool:
    print("  â³ Waiting for server to start...")
    for _ in range(timeout):
        if server_running():
            print("  â Server ready!")
            return True
        time.sleep(1)
    return False


# ââ API Helpers ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

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


# ââ YouTube Metadata âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def build_yt_metadata(channel: str, title: str, topic: str = "") -> dict:
    """Build YouTube description + tags for a channel.

    Description is keyword-rich for Shorts search discoverability (Jan 2026 Shorts
    search filter update means descriptions now drive meaningful traffic). Topic string
    is embedded so each video gets unique, searchable copy rather than boilerplate.
    """
    # Extract the core subject from topic (everything before the " â " dash if present)
    topic_subject = topic.split(" â ")[0].strip() if " â " in topic else topic.strip()
    # Extract the hook/angle (everything after the " â " dash)
    topic_angle   = topic.split(" â ", 1)[1].strip() if " â " in topic else ""

    if channel == "bsg":
        if topic_subject:
            description = (
                f"âï¸ {title}\n\n"
                f"{topic_subject} â {topic_angle + ' ' if topic_angle else ''}"
                f"Bible Stories for Kids, brought to you by Bible Story Garden. "
                f"Faith-filled, family-friendly shorts that bring Scripture to life. "
                f"Perfect for Christian families, Sunday school, and kids who love God's Word.\n\n"
                "#BibleStories #KidsFaith #BibleForKids #ChristianKids #YouTubeShorts"
            )
        else:
            description = (
                f"âï¸ {title}\n\n"
                "Bible Stories for Kids â brought to you by Bible Story Garden! "
                "Faith-filled, family-friendly shorts that bring Scripture to life.\n\n"
                "#BibleStories #KidsFaith #BibleForKids #ChristianKids #YouTubeShorts"
            )
        tags = "Bible,Bible Stories,Kids,Faith,Jesus,God,Christian,Children,YouTube Shorts,Bible for Kids"
        if topic_subject:
            # Add topic keywords as extra tags (YouTube uses tags for search ranking too)
            topic_words = [w for w in topic_subject.replace("'", "").split() if len(w) > 3]
            tags += "," + ",".join(topic_words[:5])
    else:
        # TMF
        if topic_subject:
            description = (
                f"ð§  {title}\n\n"
                f"{topic_subject}"
                f"{' â ' + topic_angle if topic_angle else ''}. "
                f"Dark psychology and human behavior explained â brought to you by The Mind Files. "
                f"Why do people do what they do? Explore the science behind manipulation, "
                f"personality, and the hidden forces shaping every decision.\n\n"
                "#Psychology #DarkPsychology #HumanBehavior #MindFiles #YouTubeShorts"
            )
        else:
            description = (
                f"ð§  {title}\n\n"
                "Dark psychology and human behavior explained â brought to you by The Mind Files. "
                "Why humans do what they do.\n\n"
                "#Psychology #DarkPsychology #HumanBehavior #MindFiles #YouTubeShorts"
            )
        tags = "psychology,dark psychology,human behavior,mind,mental health,behavioral science,YouTube Shorts,The Mind Files"
        if topic_subject:
            topic_words = [w for w in topic_subject.replace("'", "").split() if len(w) > 3]
            tags += "," + ",".join(topic_words[:5])

    return {"description": description, "tags": tags}


# ââ Trigger File Support âââââââââââââââââââââââââââââââââââââââââââââââââââââââ

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


# ââ Run Pipeline via Server ââââââââââââââââââââââââââââââââââââââââââââââââââââ

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
        print(f"â Could not import video generation: {e}")
        sys.exit(1)

    print(f"\nð¬ Creating video...")
    try:
        # Run video job directly (no Flask server needed)
        video_path = run_video_job(
            title=title,
            scenes=scenes,
            voice=voice,
            fmt="vertical",
            channel=channel
        )
        print(f"  â Video created: {Path(video_path).name}")
    except Exception as e:
        print(f"â Video generation failed: {e}")
        sys.exit(1)

    print(f"\nð¤ Uploading to YouTube ({label})...")
    yt_meta = build_yt_metadata(channel, title, topic=topic)
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
        print(f"  â Uploaded: {yt_url}")
        return yt_url
    except Exception as e:
        print(f"â Upload failed: {e}")
        sys.exit(1)


def run_via_server(channel: str, topic: str, script: dict) -> str:
    """Send pre-generated script to the running video server. Returns video URL."""
    label  = CHANNEL_LABELS[channel]
    voice  = CHANNEL_VOICES[channel]
    title  = script["title"]
    scenes = script["scenes"]

    print(f"  Title : {title}")
    print(f"  Scenes: {len(scenes)}")

    # ââ Step: Create video ââââââââââââââââââââââââââââââââââââââââââââââââââââ
    print(f"\nð¬ Creating video...")
    try:
        gen_resp = api_post("/generate", {
            "title":   title,
            "scenes":  scenes,
            "voice":   voice,
            "format":  "vertical",
            "channel": channel,
        }, timeout=10)
    except Exception as e:
        print(f"â Video generation request failed: {e}")
        sys.exit(1)

    if "error" in gen_resp:
        print(f"â Video start error: {gen_resp['error']}")
        sys.exit(1)

    # Poll until video is done (can take 3-10 minutes)
    print("  â³ Processing video (this takes a few minutes)...")
    deadline = time.time() + 1500  # 25 min max (FALâDALL-EâPollinations chain can take ~15-20min for 8 scenes)
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
        print(f"â Could not get final job status: {e}")
        sys.exit(1)

    if status.get("error"):
        print(f"â Video generation error: {status['error']}")
        # Print video_server.log tail for debugging
        log_path = BASE_DIR / "video_server.log"
        if log_path.exists():
            print("\nââ video_server.log (last 40 lines) ââ")
            lines = log_path.read_text(errors="replace").splitlines()
            print("\n".join(lines[-40:]))
        sys.exit(1)

    video_path = status.get("output", "")
    if not video_path:
        print("â No output video reported.")
        # Print video_server.log tail so we can see what failed
        log_path = BASE_DIR / "video_server.log"
        if log_path.exists():
            print("\nââ video_server.log (last 40 lines) ââ")
            lines = log_path.read_text(errors="replace").splitlines()
            print("\n".join(lines[-40:]))
        sys.exit(1)

    filename = Path(video_path).name
    print(f"  â Video ready: {filename}")

    # ââ Step: Upload to YouTube âââââââââââââââââââââââââââââââââââââââââââââââ
    yt_meta = build_yt_metadata(channel, title, topic=topic)
    print(f"\nð¤ Uploading to YouTube ({label})...")
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
        print(f"â Upload request failed: {e}")
        sys.exit(1)

    if "error" in upload_resp:
        print(f"â Upload error: {upload_resp['error']}")
        sys.exit(1)

    return upload_resp.get("url", "(unknown)")


# ââ Main âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ


def post_tmf_channel_comment(youtube, video_id: str) -> None:
    """Post affiliate/lead-magnet comment as TMF channel owner on every Short."""
    _AMZN_TAG     = "themindf20-20"
    _AUDIBLE_LINK = f"https://www.amazon.com/hz/audible/mlp/membership/prime?tag={_AMZN_TAG}"
    _LEADMAGNET   = "PASTE_MAILERLITE_FORM_URL_HERE"

    if "YOUR_FORM" in _LEADMAGNET or "PASTE" in _LEADMAGNET:
        comment_text = (
            f"📚 The books behind this video are linked in the bio.\n"
            f"🎧 Free audiobook trial (Audible): {_AUDIBLE_LINK}\n"
            f"\nAs an Amazon Associate I earn from qualifying purchases."
        )
    else:
        comment_text = (
            f"📄 Free guide — 7 Dark Psychology Tactics: {_LEADMAGNET}\n"
            f"🎧 Free audiobook trial (Audible): {_AUDIBLE_LINK}\n"
            f"📚 Full book list in bio.\n"
            f"\nAs an Amazon Associate I earn from qualifying purchases."
        )
    try:
        youtube.commentThreads().insert(
            part="snippet",
            body={"snippet": {"videoId": video_id, "topLevelComment": {"snippet": {"textOriginal": comment_text}}}}
        ).execute()
        print(f"  💬 Affiliate comment posted on {video_id}")
    except Exception as e:
        print(f"  ⚠️ Comment post failed (non-fatal): {e}")

def main():
    parser = argparse.ArgumentParser(description="Auto-create and post a YouTube Short")
    parser.add_argument("--channel", choices=["bsg", "tmf"],
                        help="Which channel to post to: bsg or tmf")
    parser.add_argument("--trigger-file",
                        help="Path to a trigger JSON file (written by scheduled task)")
    args = parser.parse_args()

    # ââ Determine mode ââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
    if args.trigger_file:
        # Trigger-file mode: script was pre-generated by the scheduled task
        trigger = load_trigger_file(args.trigger_file)
        channel = trigger["channel"]
        topic   = trigger["topic"]
        script  = trigger["script"]
        print(f"\n{'â' * 60}")
        print(f"  ð¬ Auto-Post (trigger)  |  {CHANNEL_LABELS[channel]}  |  {time.strftime('%Y-%m-%d %H:%M')}")
        print(f"{'â' * 60}")
        print(f"\nð Topic: {topic}  (from scheduled task at {trigger.get('scheduled_at', '?')})")
    else:
        # Standard mode: pick topic and generate script via server
        if not args.channel:
            parser.error("--channel is required unless --trigger-file is provided")
        channel = args.channel
        topic   = None
        script  = None

    label = CHANNEL_LABELS[channel]
    voice = CHANNEL_VOICES[channel]

    # ââ Burst-publishing guard ââââââââââââââââââââââââââââââââââââââââââââââââ
    # Stop manual re-runs / workflow_dispatch from stacking >cap videos in a day.
    if not os.getenv("BURST_GUARD_OVERRIDE"):
        burst_guard_or_exit(channel)

    if not args.trigger_file:
        print(f"\n{'â' * 60}")
        print(f"  ð¬ Auto-Post  |  {label}  |  {time.strftime('%Y-%m-%d %H:%M')}")
        print(f"{'â' * 60}")
        topic = pick_topic(channel)
        print(f"\nð Topic: {topic}")

    # ââ Ensure dependencies installed âââââââââââââââââââââââââââââââââââââââââ
    print("\nð Checking dependencies...")
    deps_ok = ensure_dependencies()
    if not deps_ok:
        print("  â ï¸ Could not install all dependencies (likely running in restricted environment).")
        if script:
            # We have a pre-generated script â save trigger file for Mac watcher
            tf = write_trigger_file(channel, topic, script)
            print(f"\nð Trigger file saved for Mac watcher: {tf.name}")
            print("   The Mac watcher (auto_watcher.sh) will pick this up and complete the post.")
        else:
            print("   Run this script manually on your Mac to complete the post.")
        sys.exit(0)

    # ââ Start server if needed ââââââââââââââââââââââââââââââââââââââââââââââââ
    server_proc        = None
    server_was_running = server_running()

    if server_was_running:
        print("\nð Video server already running â using it.")
    else:
        print("\nð Starting video server...")
        server_log = open(BASE_DIR / "video_server.log", "w")
        server_proc = subprocess.Popen(
            [sys.executable, str(BASE_DIR / "video_app.py")],
            stdout=server_log,
            stderr=server_log,
        )
        if not wait_for_server(timeout=90):
            print("â Server failed to start within 90 seconds.")
            sys.exit(1)

    try:
        # ââ Generate or use pre-generated script ââââââââââââââââââââââââââââââ
        if script is None:
            # Generate script via Flask server
            print(f"\nâï¸  Generating 8-scene script  (voice: {voice})...")
            try:
                script_resp = api_post("/generate-script", {
                    "topic":      topic,
                    "channel":    channel,
                    "num_scenes": 8,
                })
                if "error" in script_resp:
                    raise ValueError(script_resp["error"])
                script = script_resp["script"]
            except ValueError as e:
                err = str(e)
                if err.startswith("TITLE_VALIDATION_SKIP"):
                    # Intentional skip â title validator rejected all 3 attempts.
                    # This is EXPECTED behavior, not a code error. Exit 0 (green in GH Actions).
                    print(f"\nâ­ï¸  SKIPPED (title validation): {err}")
                    print("   No video posted this run. This is intentional â a bad title is worse than no post.")
                    append_to_google_sheets(channel, f"[SKIPPED] {err[22:100]}", "", status="Skipped - Title Validation")
                    sys.exit(0)
                print(f"â Script generation failed: {e}")
                sys.exit(1)
            except Exception as e:
                print(f"â Script generation failed: {e}")
                sys.exit(1)

        title = script["title"]

        # ââ Run the pipeline ââââââââââââââââââââââââââââââââââââââââââââââââââ
        print(f"\nâï¸  Script ready: {title}")
        video_url = run_via_server(channel, topic, script)

        print(f"  â Posted! {video_url}")

        # ââ Log success âââââââââââââââââââââââââââââââââââââââââââââââââââââââ
        mark_posted(channel, topic, title, video_url)

        # Clean up trigger file if it was used
        if args.trigger_file:
            try:
                Path(args.trigger_file).unlink()
            except Exception:
                pass

        print(f"\n{'â' * 60}")
        print(f"  ð SUCCESS â {label}")
        print(f"  Topic : {topic}")
        print(f"  Title : {title}")
        print(f"  URL   : {video_url}")
        print(f"{'â' * 60}\n")

    finally:
        # Only stop the server if WE started it
        if server_proc and not server_was_running:
            print("  ð Stopping video server...")
            server_proc.terminate()
            server_proc.wait(timeout=10)


if __name__ == "__main__":
    main()
