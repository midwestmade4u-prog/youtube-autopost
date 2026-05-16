#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  auto_post_mz.py — Minute Zero auto-post orchestrator        ║
╚══════════════════════════════════════════════════════════════╝

Flow:
  1. Pick topic (based on weekday + time → Format A / B / C)
  2. Load v3 prompt from MZ_Channel/MZ_Script_Generator_Prompt_v3.md
  3. Call OpenAI (or Anthropic) API → get v3 JSON output
  4. video_mz.render_video() → produces master + platform variants + thumb
  5. Upload master to YouTube (via video_mz_upload helper)
  6. Log to auto_post_log.json + append to Google Sheets
  7. (Future) Push TikTok variant to Content Posting API

Usage:
  python3 auto_post_mz.py                   # pick topic automatically
  python3 auto_post_mz.py --format A        # force a specific format
  python3 auto_post_mz.py --topic "Knight Capital"
  python3 auto_post_mz.py --dry-run         # render only, no upload

Required env vars:
  OPENAI_API_KEY                — script generation (or ANTHROPIC_API_KEY, see MODEL_BACKEND below)
  PEXELS_API_KEY                — video clip sourcing
  (YouTube token is loaded from youtube_token_mz.json)

Required Python deps (installed in GH Action workflow):
  edge-tts, Pillow, requests, openai, google-api-python-client,
  google-auth, google-auth-httplib2, google-auth-oauthlib
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "auto_post_log.json"
MZ_CHANNEL_DIR = BASE_DIR / "MZ_Channel"
MZ_PROMPT_V3 = MZ_CHANNEL_DIR / "MZ_Script_Generator_Prompt_v3.md"
MZ_OUTPUT_DIR = BASE_DIR / "MZ_Output"
MZ_OUTPUT_DIR.mkdir(exist_ok=True)

# ── Model backend ──────────────────────────────────────────────────────────
MODEL_BACKEND = os.environ.get("MZ_MODEL_BACKEND", "openai").lower()   # openai|anthropic
OPENAI_MODEL    = os.environ.get("MZ_OPENAI_MODEL",    "gpt-4o")
ANTHROPIC_MODEL = os.environ.get("MZ_ANTHROPIC_MODEL", "claude-sonnet-4-6")


# ─── Topic banks (mirror of MZ_Topic_Bank_v1.md as of Apr 24 2026) ──────────

ONE_BAD_DAY_TOPICS = [
    "Knight Capital — 12 minutes of bad code → $440M evaporated, Aug 1, 2012, 9:30 AM",
    "Coca-Cola — Apr 23, 1985 — the day they announced 'New Coke'",
    "Yahoo — 1998 meeting — Yahoo passes on buying Google for $1M",
    "Blockbuster — 2000 — the phone call rejecting Netflix for $50M",
    "Quaker Oats — 1994 — the Snapple acquisition decision ($1.7B → $300M in 27 months)",
    "JCPenney (Ron Johnson) — Feb 1, 2012 — killing all coupons on day one",
    "AOL–Time Warner — Jan 10, 2000 — merger announcement press conference",
    "Enron — Aug 14, 2001 — Skilling's sudden resignation call",
    "Theranos — Oct 16, 2015 — WSJ story drops",
    "FTX — Nov 2, 2022 — CoinDesk leaks the Alameda balance sheet",
    "Long-Term Capital Management — Aug 17, 1998 — Russia defaults",
    "Arthur Andersen — Oct 23, 2001 — the shredding-party memo",
    "Borders — 2001 — signing the deal to hand their website to Amazon",
    "Wells Fargo — The 2011 sales mandate memo ('eight is great')",
    "Boeing — The MCAS single-sensor design call (737 MAX)",
    "MySpace — Jul 19, 2005 — News Corp pays $580M and hands it to people who saw it as a billboard, not a platform",
    "Bear Stearns — Mar 13, 2008 — the midnight call admitting insolvency",
    "Lehman Brothers — Sep 14, 2008 — the weekend Paulson refused to bail them out",
    "MF Global — Oct 2011 — Jon Corzine's Euro bond doubling-down call",
    "Sears — Mar 24, 2005 — Eddie Lampert merges Kmart and Sears, announces he'll run the combined company like a hedge fund",
    "Groupon — 2011 — the pre-IPO 'accounting correction' announcement",
    "WeWork — Aug 14, 2019 — the S-1 filing that killed the IPO",
    "RJR Nabisco — 1988 — the 'Premier' smokeless cigarette launch call",
    # Moved to end — same company as GM bailout (already posted Apr 28); space these out
    "General Motors — 2001 — the 57¢ ignition switch cost-cut decision",
]
# Removed from ONE_BAD_DAY (Apr 30 2026 cleanup):
# - Barings Bank (UK), Société Générale (France), Swissair (Switzerland),
#   Volkswagen (Germany) → moved to UNKNOWN_FAILURE pool (Format B only)
# - Friendster → cut entirely (too obscure, no emotional pull for US audience)
# - Polaroid → moved to NEAR_DEATH_TOPICS (better fit: invented digital, shelved it)
# - MySpace reframed: News Corp acquisition (Jul 19 2005) is the real minute zero
# - Sears reframed: Lampert merger announcement (Mar 24 2005) is the real minute zero

# ── FORMAT B: US FRAUD & SCANDAL (pivoted Apr 30 2026) ───────────────────────
# Old "Unknown Failure" foreign-company list replaced entirely.
# New premise: the FRAUD IS the story. US only. Hook rule: for lesser-known
# companies, the hook MUST lead with the most unbelievable fact — not the name.
# These are also long-form candidates: any Short that breaks out gets a
# 10-12 min deep-dive version later.

# Tier 1 — household names, fire first
UNKNOWN_FAILURE_TOPICS_TIER1 = [
    "Bernie Madoff — Dec 10, 2008 — confesses to sons Mark and Andrew; they call the FBI; $65B Ponzi scheme hidden 48 years unravels in one conversation",
    "WorldCom — Jun 25, 2002 — internal auditor Cynthia Cooper walks into the board meeting with proof of $3.8B in fake entries; Bernie Ebbers' empire gone in one afternoon",
    "Tyco International / Dennis Kozlowski — Jun 3, 2002 — resigns after DA reveals $1M art sales tax dodge; the $2M company-funded birthday party for his wife then surfaces",
    "HealthSouth / Richard Scrushy — Mar 19, 2003 — FBI raids at 5:30 AM; $2.7B fraud; Scrushy had sold $75M in stock two days prior",
    "ImClone / Martha Stewart — Dec 27, 2001 — sells 3,928 shares on an insider tip; $228K saved; ends with 5 months in federal prison",
    "Washington Mutual — Sep 25, 2008 — FDIC seizes the bank at 6 PM, sells it to JPMorgan for $1.9B by midnight; $307B in assets gone in one night",
    "Countrywide / Angelo Mozilo — 2008 — internal emails surface where Mozilo calls his own mortgage products 'toxic' and 'poison' while selling them to customers",
    "Adelphia / Rigas family — Jul 24, 2002 — John Rigas and son Timothy arrested at their Manhattan apartment; secretly borrowed $2.3B from their own public company",
]

# Tier 2 — lesser-known names, stories are insane; hook must lead with the unbelievable fact
UNKNOWN_FAILURE_TOPICS_TIER2 = [
    "ZZZZ Best / Barry Minkow — May 1987 — LA Times reporter finds no record of the $7M carpet cleaning job; a 16-year-old's $300M empire was entirely fictional",
    "Crazy Eddie — 1987 — SEC freezes assets; Eddie Antar had inflated inventory for a decade then fled to Israel; 'insane prices' was insane fraud",
    "Cendant — Apr 15, 1998 — accounting fraud discovered THREE WEEKS after the merger closed; stock drops 47% in a single day, $14B in market cap gone",
    "Global Crossing — Jan 28, 2002 — $12B bankruptcy; CEO Gary Winnick had already pocketed $700M while employees' pensions were wiped out",
    "Sunbeam / Chainsaw Al Dunlap — Jun 9, 1998 — board fires the CEO celebrated for saving companies; he'd been destroying them through accounting fraud the entire time",
    "MicroStrategy — Mar 20, 2000 — $66M restatement announced the same week as the IPO celebration; CEO Michael Saylor loses $6B in a single day",
    "Qwest / Joseph Nacchio — 2002 — CEO convicted of 19 counts of insider trading; sold $52M in stock while publicly hyping a company he knew was collapsing",
    "Symbol Technologies — 2004 — CEO Tomo Razmilovic flees to Sweden to avoid arrest for $230M fraud; FBI has to extradite him back",
    "Rite Aid — Jun 2003 — CEO Martin Grass sentenced to 8 years; $1.6B accounting fraud at the nation's third-largest drugstore chain",
]

NEAR_DEATH_TOPICS = [
    "Apple — Aug 6, 1997 — Steve Jobs announces Microsoft's $150M lifeline",
    "IBM — 1993 — Lou Gerstner's first board meeting, $8B loss",
    "Chrysler — 1979 — the $1.5B loan guarantee vote in Congress",
    "Disney — 1984 — Bass brothers rescue from Saul Steinberg's raid",
    "FedEx — 1973 — Fred Smith's $5K blackjack win to make Monday's payroll",
    "Starbucks — Jan 2008 — Schultz returns, closes 600 stores in one weekend",
    "Harley-Davidson — 1981 — the buyout from AMF, 13 executives' personal savings",
    "Ford — Nov 2006 — mortgaging the blue oval logo + all assets for $23.6B",
    "Converse — 2001 — Chapter 11, sold to Nike",
    "American Express — 1963 — Salad Oil Scandal, $150M exposure",
    "Delta Air Lines — Sep 14, 2005 — Chapter 11 filing at 5:30 AM",
    "Continental Airlines — 1983 & 1990 — double bankruptcy survival",
    "Best Buy — 2012 — CEO sex scandal, stock at $11, everyone wrote them off to Amazon; Hubert Joly's turnaround saves the company",
    "Netflix — Sep 18, 2011 — Qwikster split announced; 800K subscribers leave; stock drops 77%; Hastings reverses the decision",
    "Domino's — 2009 — viral 'gross ingredients' video destroys the brand; CEO goes on camera and admits the pizza was bad; radical honesty saves the company",
    "Airbnb — Mar 2020 — COVID cancels $1B in bookings overnight; company nearly collapses; pivots to Online Experiences and survives",
    # Moved from ONE_BAD_DAY Apr 30 2026 — better as near-death/missed opportunity
    "Polaroid — 1975 — engineers invent the digital camera, management shelves it; Polaroid files bankruptcy 26 years later having never shipped it",
    # Moved to end — GM bailout already posted Apr 28; space same-company stories out
    "GM — Jun 1, 2009 — Chapter 11, $82B federal bailout",
]
# Removed from NEAR_DEATH (Apr 30 2026 cleanup):
# - Marvel → already posted Apr 28, removed to prevent duplicate
# - LEGO (Danish), Nintendo (Japanese), Harrods (UK) → foreign companies cut
# - J.Crew → weak story, "COVID hit retail" has no compelling human element
# - GM moved to end (same company as Apr 28 bailout video — space them out)


# ─── Rotation logic ──────────────────────────────────────────────────────────

def pick_format_for_slot(weekday: int, hour_ct: int) -> str:
    """
    Rotation from MZ_Channel #3 plan:
      09:00 CT daily  → Format A (one_bad_day)
      19:00 CT Mon/Wed/Fri/Sun → Format B (unknown_failure)
      19:00 CT Tue/Thu/Sat     → Format C (near_death)

    weekday: Python datetime.weekday() (Monday=0 ... Sunday=6)
    hour_ct: hour in Central Time (24h)
    """
    if hour_ct < 12:
        return "A"
    # Evening slot
    # Mon=0, Wed=2, Fri=4, Sun=6  → Format B
    # Tue=1, Thu=3, Sat=5         → Format C
    if weekday in (0, 2, 4, 6):
        return "B"
    return "C"


def pick_topic(format_letter: str) -> tuple[str, str]:
    """Return (topic_string, format_tag_for_prompt)."""
    log = _load_log()
    used = set(log.get("mz_topics_used", []))

    if format_letter == "A":
        pool = ONE_BAD_DAY_TOPICS
        tag = "one_bad_day"
    elif format_letter == "B":
        # Exhaust Tier 1 before dipping into Tier 2
        tier1_available = [t for t in UNKNOWN_FAILURE_TOPICS_TIER1 if t not in used]
        tier2_available = [t for t in UNKNOWN_FAILURE_TOPICS_TIER2 if t not in used]
        pool = tier1_available if tier1_available else tier2_available
        if not pool:
            pool = UNKNOWN_FAILURE_TOPICS_TIER1 + UNKNOWN_FAILURE_TOPICS_TIER2
        tag = "unknown_failure"
    elif format_letter == "C":
        pool = NEAR_DEATH_TOPICS
        tag = "near_death"
    else:
        raise ValueError(f"Invalid format letter: {format_letter}")

    available = [t for t in pool if t not in used]
    if not available:
        print(f"  🔄 All MZ Format {format_letter} topics used — resetting cycle")
        # Clear only this format's used-set — preserve other formats' rotation
        for t in pool:
            used.discard(t)
        log["mz_topics_used"] = list(used)
        _save_log(log)
        available = pool[:]

    return random.choice(available), tag


# ─── Log helpers ─────────────────────────────────────────────────────────────

def _load_log() -> dict:
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_log(log: dict) -> None:
    LOG_FILE.write_text(json.dumps(log, indent=2))


def append_to_google_sheets(title: str, url: str, format_tag: str) -> None:
    """Append posted MZ video to Google Sheets Auto-Post Log (GitHub Actions only)."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from datetime import datetime
        from zoneinfo import ZoneInfo
    except ImportError:
        print("⚠️  Google API libraries not available for Sheets logging")
        return
    try:
        creds_json = os.environ.get("GOOGLE_SHEETS_KEY")
        if not creds_json:
            print("  ❌ GOOGLE_SHEETS_KEY not set — skipping Sheets log")
            return
        creds = service_account.Credentials.from_service_account_info(
            json.loads(creds_json),
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
        timestamp = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M:%S")
        row = [timestamp, "Minute Zero", title, "Success", url, ""]
        service.spreadsheets().values().append(
            spreadsheetId="1JKlBnYdv-_r3FcjozBtpRxLNRiAoA1ezLRz2W-7vVWI",
            range="Auto-Post Log!A:G",
            valueInputOption="USER_ENTERED",
            body={"values": [row]}
        ).execute()
        print(f"  📊 Logged to Google Sheets: Minute Zero — {title}")
    except Exception as e:
        print(f"  ⚠️  Sheets logging failed: {str(e)[:100]}")


def mark_mz_posted(topic: str, title: str, video_url: str, format_tag: str) -> None:
    log = _load_log()
    log.setdefault("mz_topics_used", []).append(topic)
    log.setdefault("posts", []).append({
        "channel":    "mz",
        "format":     format_tag,
        "topic":      topic,
        "title":      title,
        "url":        video_url,
        "posted_at":  time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save_log(log)


# ─── MZ Script validators ────────────────────────────────────────────────────

# edge-tts ChristopherNeural speaks at ~2.5 words/sec.
# Calibrated May 6 2026 from Washington Mutual video (106w → 54.5s = 1.95 wps observed,
# but script was underfilled; 2.5 wps is the correct target for a properly-filled script).
MZ_WORD_TARGETS = {
    "one_bad_day":     (140, 165),   # Format A: target 55–65s
    "unknown_failure": (180, 215),   # Format B: target 72–82s
    "near_death":      (165, 215),   # Format C: target 66–86s (GPT plateaus ~175w on survival arcs; 165 floor still clears Format A max)
}

def mz_script_word_count_ok(script: dict, format_tag: str) -> tuple[bool, int, tuple[int, int]]:
    """Check narration word count is in the edge-tts target band for this format.

    MZ uses a flat 'script' string field (not scenes like TMF).
    Returns (ok, actual_count, (min, max)).
    """
    narration = (script.get("script") or "").strip()
    total = len(narration.split())
    lo, hi = MZ_WORD_TARGETS.get(format_tag, (140, 215))
    return (lo <= total <= hi), total, (lo, hi)


def mz_title_ok(title: str) -> tuple[bool, str]:
    """MZ title guardrails — data-backed from analytics (May 2026).

    Winners: "How One Buyout Saved Harley-Davidson" (919 views), "How Marvel Survived" (all-time #1)
    Losers:  "The Night Washington Mutual Vanished" (83 views), "The Moment Bernie Madoff..." (314 views)
    Rule: titles MUST open with 'How' OR lead with a dollar/number figure in the first 5 words.
    """
    t = (title or "").strip()
    if len(t) < 10:
        return False, "title too short"
    if len(t) > 70:
        return False, f"title too long ({len(t)} chars — keep under 70)"

    t_lower = t.lower()
    words = t_lower.split()

    # Ban confirmed weak openers
    banned_openers = ("the night", "the day", "the moment", "the hour", "the week")
    for banned in banned_openers:
        if t_lower.startswith(banned):
            return False, (
                f"title starts with '{banned}' — confirmed underperformer. "
                f"Must start with 'How' or lead with a dollar/number figure. "
                f"Example: 'How [Company] Nearly Died' or '$440M Vanished in 12 Minutes'"
            )

    # Require "How" opener OR a number/dollar sign in the first 5 words
    starts_with_how = t_lower.startswith("how ")
    first_five = " ".join(words[:5])
    has_number_or_dollar = any(c.isdigit() or c == "$" for c in first_five)

    if not starts_with_how and not has_number_or_dollar:
        return False, (
            f"title must start with 'How' or contain a number/$dollar in the first 5 words. "
            f"Got: \"{t[:50]}\". "
            f"Good examples: 'How Harley-Davidson Survived', '$440M Gone in 12 Minutes'"
        )

    return True, ""


# Banned generic Pexels terms that recur across every video and produce
# visually identical dark-city / corporate-building footage.
_PEXELS_BANNED_TERMS = {
    "dark city", "city night", "night city", "office building",
    "corporate headquarters", "businessman", "businessmen",
    "business meeting", "financial stress", "money", "finance",
    "economy", "economic", "growth", "failure", "corporate",
    "city skyline", "skyscraper", "downtown", "urban night",
}

def mz_pexels_queries_ok(script: dict) -> tuple[bool, str]:
    """Check that every Pexels query is topic-specific, not a banned generic phrase.

    Each query must:
      1. Not consist entirely of banned generic terms.
      2. Contain at least one word that is 4+ chars and NOT in the banned set,
         so GPT can't sneak in "dark city skyline" and call it specific.
    Returns (ok, problem_description).
    """
    queries = script.get("pexels_search_queries") or []
    if not queries:
        return False, "pexels_search_queries is missing or empty"

    bad_queries = []
    for q in queries:
        q_lower = q.lower().strip()
        words = set(w.strip(".,;:\"'") for w in q_lower.split())
        # A query is "generic" if every meaningful word (4+ chars) is in the banned set
        meaningful = [w for w in words if len(w) >= 4]
        if meaningful and all(w in _PEXELS_BANNED_TERMS for w in meaningful):
            bad_queries.append(q)
            continue
        # Also flag if a banned multi-word phrase is the ENTIRE query (2–3 word queries)
        if any(q_lower == banned or q_lower.startswith(banned + " ") or q_lower.endswith(" " + banned)
               for banned in _PEXELS_BANNED_TERMS if " " in banned):
            bad_queries.append(q)

    if bad_queries:
        return False, (
            f"PEXELS QUERY FAIL: {len(bad_queries)} generic query/queries that will produce "
            f"repeated dark-city/corporate footage: {bad_queries}. "
            f"Every query MUST contain a company name, person, location, or specific year. "
            f"BAD: 'dark city night' — GOOD: 'WeWork coworking office 2019'"
        )
    return True, ""


# ─── Script generation (v3 prompt → JSON) ────────────────────────────────────

def load_system_prompt() -> str:
    """Read v3 prompt markdown and extract the code-block payload."""
    if not MZ_PROMPT_V3.exists():
        raise FileNotFoundError(f"Missing v3 prompt: {MZ_PROMPT_V3}")
    text = MZ_PROMPT_V3.read_text()
    # The prompt lives inside a ```...``` code fence
    in_block = False
    lines: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("```") and not in_block:
            in_block = True
            continue
        if line.strip().startswith("```") and in_block:
            break
        if in_block:
            lines.append(line)
    if not lines:
        raise RuntimeError("Could not extract code block from v3 prompt file")
    return "\n".join(lines)


def _call_openai(system: str, user: str) -> str:
    """Call OpenAI and return raw content string."""
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing or empty")
    client = OpenAI(api_key=api_key)
    r = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0.8,
    )
    return r.choices[0].message.content


def _call_anthropic(system: str, user: str) -> str:
    """Call Anthropic and return raw content string."""
    from anthropic import Anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is missing or empty")
    client = Anthropic(api_key=api_key)
    r = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return r.content[0].text


def _parse_llm_content(content: str) -> dict:
    """Parse JSON from LLM response, stripping any markdown code fences."""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].lstrip()
    data = json.loads(content)
    if "error" in data:
        raise RuntimeError(f"Script generator self-rejected: {data['error']}")
    return data


def generate_script(topic: str, format_tag: str) -> dict:
    """Call the LLM backend with v3 prompt + tagged topic, return validated JSON.

    Primary backend: OpenAI (proven, paid, reliable).
    Fallback backend: Anthropic (used if OpenAI fails for any reason).
    MZ_MODEL_BACKEND env var can force a specific backend, but fallback still applies.

    Validator: up to 3 attempts. Rejects scripts where narration word count falls
    outside the edge-tts target band for the given format.
    """
    system = load_system_prompt()
    user_base = f"[{format_tag.upper()}] {topic}"

    # Determine call order based on MODEL_BACKEND setting
    if MODEL_BACKEND == "anthropic":
        primary_fn,  primary_name  = _call_anthropic, "anthropic"
        fallback_fn, fallback_name = _call_openai,    "openai"
    else:
        primary_fn,  primary_name  = _call_openai,    "openai"
        fallback_fn, fallback_name = _call_anthropic,  "anthropic"

    def _call_with_fallback(system_prompt: str, user_msg: str) -> dict:
        """Try primary backend, fall back to secondary on any error."""
        try:
            print(f"  🤖 Using {primary_name} backend ...")
            content = primary_fn(system_prompt, user_msg)
            return _parse_llm_content(content)
        except Exception as e:
            print(f"  ⚠️  {primary_name} failed: {str(e)[:120]}")
            print(f"  🔄 Falling back to {fallback_name} ...")
        try:
            content = fallback_fn(system_prompt, user_msg)
            print(f"  ✅ {fallback_name} fallback succeeded")
            return _parse_llm_content(content)
        except Exception as e2:
            raise RuntimeError(
                f"Both LLM backends failed.\n"
                f"  {primary_name}: see above\n"
                f"  {fallback_name}: {str(e2)[:200]}"
            ) from e2

    extra = ""
    last_data: dict | None = None
    lo, hi = MZ_WORD_TARGETS.get(format_tag, (140, 215))

    for attempt in range(1, 4):   # up to 3 attempts
        data = _call_with_fallback(system + extra, user_base)
        last_data = data

        wc_ok, word_count, (lo, hi) = mz_script_word_count_ok(data, format_tag)
        title_ok, title_reason = mz_title_ok(data.get("title", ""))
        pexels_ok, pexels_reason = mz_pexels_queries_ok(data)

        problems = []
        if not wc_ok:
            est_sec = int(word_count / 2.5)
            problems.append(
                f"LENGTH FAIL: narration is {word_count} words (~{est_sec}s at edge-tts rate). "
                f"Must be {lo}–{hi} words (target {int(lo/2.5)}–{int(hi/2.5)}s). "
                f"Write MORE narration — do not summarise, expand each beat fully."
            )
        if not title_ok:
            problems.append(f"TITLE FAIL: {title_reason}")
        if not pexels_ok:
            problems.append(pexels_reason)

        if not problems:
            print(f"  ✅ Script passed validators ({word_count}w, title OK) on attempt {attempt}")
            return data

        print(f"  ⚠️  Validator failed attempt {attempt}/3: {' | '.join(problems)}")

        # Build an expansion hint for the LENGTH FAIL case — show the rejected script
        # and pinpoint exactly which beat needs more words, so GPT doesn't just reshuffle.
        length_hint = ""
        if not wc_ok:
            rejected_script = (data.get("script") or "").strip()
            need_more = (lo - word_count)
            length_hint = (
                f"\n\nYour rejected narration ({word_count} words) is shown below. "
                f"You must add at least {need_more} more words — NOT by repeating or padding, "
                f"but by expanding the minute_zero beat with:\n"
                f"  • The exact date/time the crisis peaked\n"
                f"  • Specific dollar figures or numeric thresholds\n"
                f"  • Who made the key decision and what they actually did\n"
                f"  • What would have happened if they had waited 24 more hours\n"
                f"  • The emotional/internal state inside the company at that moment\n"
                f"Keep all other beats as-is. Only expand minute_zero.\n\n"
                f"REJECTED SCRIPT:\n{rejected_script}"
            )

        extra = (
            "\n\nIMPORTANT — your previous draft was REJECTED:\n- "
            + "\n- ".join(problems)
            + f"\n\nFix ALL issues. The narration (script field) MUST be {lo}–{hi} words. "
              f"edge-tts speaks at ~2.5 words/sec — {lo}w = ~{int(lo/2.5)}s, {hi}w = ~{int(hi/2.5)}s. "
              f"Do NOT shorten or summarise."
            + length_hint
        )

    # All retries exhausted — skip this post rather than publish a bad title.
    # Caller catches TITLE_VALIDATION_SKIP, logs to Sheets, and exits 0 (green in GH Actions).
    last_title = (last_data or {}).get("title", "n/a") if last_data else "n/a"
    raise ValueError(
        f"TITLE_VALIDATION_SKIP: all 3 attempts failed — "
        f"last title: \"{last_title}\" | word count: {word_count}"
    )


# ─── YouTube upload ──────────────────────────────────────────────────────────

def upload_to_youtube(video_path: Path, title: str, description: str,
                      tags: list[str], thumbnail_path: Path | None = None,
                      privacy_status: str = "public") -> str:
    """Upload the MZ master to YouTube. Returns video URL.

    privacy_status: "public" (default, used by cron), "unlisted" (manual
    routing test — video uploads but doesn't appear in feed/search), or
    "private" (only owner can view).
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    token_path = BASE_DIR / "youtube_token_mz.json"
    if not token_path.exists():
        raise RuntimeError("youtube_token_mz.json missing — complete OAuth first")

    creds = Credentials.from_authorized_user_file(
        str(token_path),
        ["https://www.googleapis.com/auth/youtube.upload",
         "https://www.googleapis.com/auth/youtube"]
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())

    yt = build("youtube", "v3", credentials=creds)

    # Safety check: verify token's channel identity matches MZ
    me = yt.channels().list(mine=True, part="id,snippet").execute()
    if not me.get("items"):
        raise RuntimeError("YouTube token returned no channel — bad OAuth?")
    channel_id = me["items"][0]["id"]
    # Log — don't hard-fail if MZ channel id isn't yet configured
    print(f"  🔑 Uploading as channel: {channel_id} ({me['items'][0]['snippet']['title']})")

    body = {
        "snippet": {
            "title":       title[:100],
            "description": description,
            "tags":        tags[:15],
            "categoryId":  "22",   # People & Blogs — matches MZ_Channel_Setup.md
        },
        "status": {
            "privacyStatus":           privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video_path), resumable=True, chunksize=1024 * 1024 * 4)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = req.next_chunk()

    video_id = response["id"]
    video_url = f"https://youtu.be/{video_id}"

    # Optional: upload custom thumbnail
    if thumbnail_path and thumbnail_path.exists():
        try:
            yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))).execute()
            print(f"  🖼️  Custom thumbnail uploaded")
        except Exception as e:
            print(f"  ⚠️ Thumbnail upload failed (non-fatal): {e}")

    return video_url


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format",  choices=["A", "B", "C"],
                        help="Force a specific format (skip auto-rotation).")
    parser.add_argument("--topic",   help="Override topic string.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Render only, skip YouTube upload.")
    parser.add_argument("--unlisted", action="store_true",
                        help="Upload as unlisted (not public). Use for first routing test.")
    args = parser.parse_args()

    print(f"\n{'═' * 60}")
    print(f"  🎬 Minute Zero Auto-Post  |  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═' * 60}")

    # 1. Topic selection
    if args.topic:
        topic = args.topic
        format_tag = {"A": "one_bad_day", "B": "unknown_failure", "C": "near_death"}[args.format or "A"]
    else:
        if args.format:
            fmt = args.format
        else:
            now = dt.datetime.now(dt.timezone.utc)
            # Central Time is UTC-5 (CDT) or -6 (CST). Use -5 as conservative default for daylight savings.
            ct = now - dt.timedelta(hours=5)
            fmt = pick_format_for_slot(ct.weekday(), ct.hour)
        topic, format_tag = pick_topic(fmt)

    print(f"\n📖 Format: {format_tag}")
    print(f"📖 Topic : {topic}")

    # 2. Generate script
    print(f"\n✍️  Generating v3 script (backend: {MODEL_BACKEND}) ...")
    try:
        script_data = generate_script(topic, format_tag)
    except ValueError as e:
        err = str(e)
        if err.startswith("TITLE_VALIDATION_SKIP"):
            # Intentional skip — title validator rejected all 3 attempts.
            # Exit 0 (green in GH Actions) and log to Sheets so it's visible but not alarming.
            print(f"\n⏭️  SKIPPED (title validation): {err}")
            print("   No video posted. A bad title is worse than no post — this is expected behavior.")
            append_to_google_sheets(f"[SKIPPED] {err[22:100]}", "", format_tag)
            # Mark the topic as used so the same failing topic isn't re-picked on
            # the next run — prevents infinite retry loops on stubborn topics.
            log = _load_log()
            used = log.get("mz_topics_used", [])
            if topic not in used:
                used.append(topic)
                log["mz_topics_used"] = used
                _save_log(log)
                print(f"   📝 Marked skipped topic as used to prevent retry loop: {topic[:60]}")
            return 0
        raise
    print(f"  ✅ Title: {script_data['title']}")
    print(f"  ✅ Duration target: {script_data.get('target_duration_sec', '?')}s")
    # Hook rotation telemetry (v3 → v4): log each variant's style + validity.
    # A variant's `hook` may legitimately be null if the LLM couldn't generate
    # that style; we surface those so v4 weighting can trust the data.
    hooks = script_data.get("hooks", []) or []
    for i, h in enumerate(hooks):
        style = (h or {}).get("style", "?")
        text  = (h or {}).get("hook")
        status = "∅ null" if not text else f"{len(text)} chars"
        print(f"  ✅ Hook[{i}] {style}: {status}")
    if not any((h or {}).get("hook") for h in hooks):
        print("  ⚠️  All hook variants null — script body hook will still render, but v4 rotation data is empty")

    # 3. Render
    print(f"\n🎥 Rendering video (clean master + variants) ...")
    from video_mz import render_video
    out_dir = MZ_OUTPUT_DIR / dt.date.today().isoformat()
    result = render_video(script_data, out_dir)
    print(f"  ✅ Master:    {result['master_path']}")
    print(f"  ✅ YT:        {result['yt_path']}")
    print(f"  ✅ TikTok:    {result['tt_path']}")
    print(f"  ✅ Instagram: {result['ig_path']}")
    print(f"  ✅ Thumb:     {result['thumb_path']}")

    if args.dry_run:
        print(f"\n⏹️  Dry run — skipping YouTube upload.")
        return 0

    # 4. Upload to YouTube
    print(f"\n📤 Uploading to YouTube ...")
    hashtags = script_data.get("hashtags", "").strip()
    tags = [h.lstrip("#") for h in hashtags.split() if h.startswith("#")]
    description = (
        f"{script_data.get('description', '')}\n\n"
        f"{hashtags}"
    ).strip()
    video_url = upload_to_youtube(
        Path(result["yt_path"]),
        title=script_data["title"],
        description=description,
        tags=tags,
        thumbnail_path=Path(result["thumb_path"]),
        privacy_status="unlisted" if args.unlisted else "public",
    )
    print(f"  ✅ Posted ({'unlisted' if args.unlisted else 'public'}): {video_url}")

    # 5. Log
    mark_mz_posted(topic, script_data["title"], video_url, format_tag)
    append_to_google_sheets(script_data["title"], video_url, format_tag)

    # 6. Post TikTok variant (if TIKTOK_ACCESS_TOKEN is set)
    tt_path = Path(result["tt_path"])
    tiktok_publish_id = None
    if os.environ.get("TIKTOK_ACCESS_TOKEN") or (BASE_DIR / "tiktok_token.json").exists():
        print(f"\n📱 Posting TikTok variant ...")
        try:
            from tiktok_post import post_to_tiktok, load_access_token
            tt_token = load_access_token()
            tt_title = script_data["title"]
            tiktok_publish_id = post_to_tiktok(tt_path, tt_title, tt_token)
            print(f"  ✅ TikTok posted — Publish ID: {tiktok_publish_id}")
        except Exception as e:
            print(f"  ⚠️  TikTok post failed (non-fatal): {str(e)[:200]}")
    else:
        print(f"\n⏭️  Skipping TikTok post (TIKTOK_ACCESS_TOKEN not set)")

    # 7. Trigger file for traceability (matches TMF/BSG pattern)
    trigger_path = BASE_DIR / f"auto_trigger_mz_{time.strftime('%Y%m%d_%H%M')}.json"
    trigger_path.write_text(json.dumps({
        "channel":     "mz",
        "format_tag":  format_tag,
        "topic":       topic,
        "title":       script_data["title"],
        "video_url":   video_url,
        "master_path": result["master_path"],
        "tt_path":          result["tt_path"],
        "tiktok_publish_id": tiktok_publish_id,   # None if not posted
        "ig_path":     result["ig_path"],    # Instagram variant — future
        "thumb_path":  result["thumb_path"],
        "posted_at":   time.strftime("%Y-%m-%d %H:%M:%S"),
    }, indent=2))
    print(f"  📄 Trigger file: {trigger_path.name}")

    print(f"\n{'═' * 60}")
    print(f"  🎉 SUCCESS — Minute Zero")
    print(f"  Topic : {topic}")
    print(f"  Title : {script_data['title']}")
    print(f"  URL   : {video_url}")
    print(f"{'═' * 60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
