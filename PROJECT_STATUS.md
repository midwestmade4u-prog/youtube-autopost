# YouTube Automation Project Status

**Date:** April 19, 2026  
**Current Status:** Partially working - TMF automated, BSG paused for manual testing

---

## What's Working ✅

### TMF (The Mind Files) - FULLY AUTOMATED
- **Posting Schedule:** 7 AM CST, 12 PM CST, 9 PM CST (three times daily)
- **Status:** Workflow runs, videos generate and post to YouTube
- **Workflow File:** `.github/workflows/tmf-autopost.yml`
- **YouTube Channel ID:** `UC0O6KbbHKW4_a7d9epNo93A`
- **Latest Test:** Video "Why You're Hooked on Your Phone" posted successfully on Apr 19

### Video Generation Pipeline
- ✅ Flask web app (`video_app.py`) generates videos locally
- ✅ OpenAI API generates scripts
- ✅ ElevenLabs TTS generates voice
- ✅ FAL AI generates images
- ✅ FFmpeg creates final MP4
- ✅ Manual upload to YouTube works via web app

### GitHub Actions Setup
- ✅ Workflows trigger on schedule
- ✅ Environment variables working (OPENAI_API_KEY, ELEVENLABS_API_KEY, FAL_API_KEY)
- ✅ YouTube OAuth tokens properly generated and stored

---

## What's Paused ⏸️

### BSG (Bible Story Garden) - MANUAL TESTING MODE
- **Status:** Automation disabled (workflow file deleted on Apr 19)
- **Reason:** Channel routing issue - videos posted to TMF instead of BSG
- **Current Plan:** Manually test BSG for 1-2 weeks to gauge traction before investing in proper automation
- **YouTube Channel ID:** `UCcyBiF84Mc-evMSYZlqh3zVA`

---

## Critical Issues Identified ❌

### 1. YouTube Channel Routing (BLOCKER FOR MULTI-CHANNEL AUTOMATION)
**Problem:** Both channels are under one Google account (Midwest Made4U). When posting, videos go to TMF regardless of channel selection.

**Root Cause:** YouTube Data API's `onBehalfOfContentOwnerChannel` parameter requires `onBehalfOfContentOwner` (content owner ID), which only works for YouTube Partners/enterprise accounts. Personal accounts don't have this.

**Attempted Fixes:**
- Added Channel IDs to code: `YT_CHANNEL_IDS = {"bsg": "UCcyBf84Mc-evMSYZlqh3zVA", "tmf": "UC0O6KbbHKW4_a7d9epNo93A"}`
- Added `onBehalfOfContentOwnerChannel` parameter to upload request
- **Result:** YouTube API error: "Missing content owner id"

**Status:** Needs architectural redesign for long-term multi-channel automation

### 2. Google Sheets Logging (NOT CRITICAL - PAUSED)
**Problem:** Auto-post logs aren't appearing in Google Sheets tracker
**Root Cause:** Unknown - possibly empty `GOOGLE_SHEETS_KEY` secret or issue with Google Sheets API integration
**Status:** Deprioritized while focusing on channel routing

---

## Key Files & Locations

**GitHub Repo:** `youtube-autopost` (main branch)

**Workflows:**
- `.github/workflows/tmf-autopost.yml` - ✅ ACTIVE
- `.github/workflows/bsg-autopost.yml` - ❌ DELETED (paused)

**Python Scripts:**
- `auto_post.py` - Main automation script (runs in GitHub Actions)
- `video_app.py` - Flask web server (local manual generation)

**Tokens & Credentials:**
- `youtube_token_bsg.json` - OAuth token for BSG channel
- `youtube_token_tmf.json` - OAuth token for TMF channel
- `video-studio-493020-05e03c3a1b8c.json` - Google Service Account (for Sheets, not yet working)
- `youtube_client_secrets.json` - OAuth app credentials

**Configuration:**
- GitHub Secrets needed:
  - `OPENAI_API_KEY` ✅ Set
  - `ELEVENLABS_API_KEY` ✅ Set
  - `FAL_API_KEY` ✅ Set
  - `YT_TOKEN_BSG` ✅ Set
  - `YT_TOKEN_TMF` ✅ Set
  - `GOOGLE_SHEETS_KEY` ✅ Set (but logging not working)

**Google Sheets:**
- URL: https://docs.google.com/spreadsheets/d/1JKlBnYdv-_r3FcjozBtpRxLNRiAoA1ezLRz2W-7vVWI/edit
- Sheet name: "Auto-Post Log"
- Shared with service account: `youtube-autopost-bot@video-studio-493020.iam.gserviceaccount.com`

---

## Next Steps

### Immediate (Next 1-2 weeks)
1. **Test BSG manually** - Generate videos using Flask web app, schedule directly on YouTube Studio
2. **Monitor TMF** - Verify it keeps posting on schedule (7 AM, 12 PM, 9 PM CST)
3. **Assess BSG traction** - See if channel gains viewers/engagement

### Long-term (When Ready to Automate BSG)
1. **Solve multi-channel routing** - Options:
   - Use separate Google accounts for each channel (complex OAuth setup)
   - Use YouTube Data API differently (research required)
   - Rearchitect to handle channel selection differently
   
2. **Fix Google Sheets logging** - Debug why videos aren't logging

3. **Scale to additional channels** - Once multi-channel architecture is solid

---

## Technical Debt

- `onBehalfOfContentOwnerChannel` parameter added but doesn't work (needs removal/redesign)
- Debug logging added to `youtube_upload()` function - can be cleaned up later
- GitHub Actions error handling could be improved (`continue-on-error: true` suppresses actual failures)

---

## Commands to Remember

**Start Flask web app locally:**
```bash
cd /path/to/Youtube\ Channels\ Project
python3 video_app.py
```
Then open: http://localhost:5002

**Push code changes:**
```bash
git add <files>
git commit -m "message"
git push
```

**Manually trigger TMF workflow:**
- GitHub → Actions → YouTube Auto-Post - The Mind Files → Run workflow

---

## Contact Info
- Email: wisseinc@gmail.com
- Project Folder: `/Youtube Channels\ Project` (Mac)
