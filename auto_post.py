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

TMF_TOPICS = [
    "Why One Bad Thing Erases Ten Good Things You've Done",
    "The Framing Effect — How Words CHANGE Your Decisions",
    "Why You Feel Guilty for Things That Aren't Your Fault",
    "The False Consensus Effect — Why You Think EVERYONE Agrees With You",
    "Why Good People Lie (And How They Justify It)",
    "Why You Care What Strangers Think (Even Though You Shouldn't)",
    "The Sunk Cost Fallacy — Why You Can't Let Go of Bad Decisions",
    "Why You Overestimate How Much Others Notice Your Mistakes",
    "The Backfire Effect — Why Facts Make People BELIEVE HARDER in False Beliefs",
    "Why You Feel Obligated to People Who Are Mean to You",
    "Impostor Syndrome — Why High Achievers Think They're Frauds",
    "Why You Make Worse Decisions When You're Tired (The Science)",
    "The Spotlight Effect — Why You Think Everyone's Watching You",
    "Why You're Nicer to Strangers Than People You Love",
    "The Planning Fallacy — Why You Always Underestimate How Long Things Take",
    "Why You Feel Annoyed by People Who Are Similar to You",
    "Dunning-Kruger Effect — Why Incompetent People Think They're Experts",
    "Why You Can't Stop Checking Your Phone (The Science Behind Addiction)",
    "The Mere Exposure Effect — Why Familiarity Makes You Like Things More",
    "Why You Regret Things You DIDN'T Do More Than Things You Did",
    "The Bystander Effect — Why You Don't Help (Even Though You Want To)",
    "Why You Act Differently Around Different People (The Real Reason)",
    "Authority Bias — Why You Obey People in Positions of Power",
    "Why You're More Likely to Help Someone Who Looks Like You",
    "The Decoy Effect — How Stores TRICK You Into Buying More",
    "Why You're Attracted to People (The Psychology Behind It)",
    "The Halo Effect — How One Good Thing Makes You OVERLOOK Bad Things",
    "Why You Procrastinate (And Why Understanding It Doesn't Help)",
    "Confirmation Bias — Why You Only See Evidence That Proves You Right",
    "Why People WHO KNOW BETTER Still Make Bad Choices",
    "The Anchoring Effect — Why The First Number You Hear CHANGES Everything",
    "Why You Feel Compelled to Return Favors (Even Unwanted Ones)",
    "The Recency Bias — Why You Remember Recent Events Better",
    "Why You Feel Obligated to Finish Things You Started (Even Bad Things)",
    "The Availability Heuristic — Why You Overestimate Dangerous Things",
    "Why You Judge Others Harsher Than You Judge Yourself",
    "The Cocktail Party Effect — Why You Hear Your Name Across a Crowded Room",
    "Why You're Kinder to Yourself When You're Sad (The Comfort Trap)",
    "The Illusion of Transparency — Why You Think Others Know What You're Thinking",
    "Why You're More Likely to Succeed When You DON'T Think Too Hard",
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
            return

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
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
        # Silently fail — don't break the workflow
        print(f"  ⚠️  Could not log to Sheets: {e}")


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
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


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

    # Detect CI environment (GitHub Actions sets GITHUB_ACTIONS to "true")
    github_actions_var = os.getenv("GITHUB_ACTIONS")
    in_ci_environment  = bool(github_actions_var)  # More robust check

    if server_was_running:
        print("\n🔌 Video server already running — using it.")
    elif in_ci_environment:
        print(f"\n🌐 Running in CI environment (GITHUB_ACTIONS={github_actions_var}) — using headless mode.")
    else:
        print("\n🚀 Starting video server...")
        server_proc = subprocess.Popen(
            [sys.executable, str(BASE_DIR / "video_app.py")],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not wait_for_server(timeout=90):
            print("⚠️ Server failed to start within 90 seconds. Attempting headless mode...")
            in_ci_environment = True  # Fall back to headless mode

    try:
        # ── Generate or use pre-generated script ──────────────────────────────
        if script is None:
            # Standard mode: generate script via server
            print(f"\n✍️  Generating 8-scene script  (voice: {voice})...")
            try:
                script_resp = api_post("/generate-script", {
                    "topic":      topic,
                    "channel":    channel,
                    "num_scenes": 8,
                })
            except Exception as e:
                print(f"❌ Script generation request failed: {e}")
                sys.exit(1)

            if "error" in script_resp:
                print(f"❌ Script error: {script_resp['error']}")
                sys.exit(1)

            script = script_resp["script"]

        title = script["title"]

        # ── Run the pipeline ──────────────────────────────────────────────────
        print(f"\n✍️  Script ready: {title}")
        if in_ci_environment:
            video_url = run_headless(channel, topic, script)
        else:
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
