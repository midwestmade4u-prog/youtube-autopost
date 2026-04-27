# Minute Zero — TikTok Setup Walkthrough

**When to use this:** After you finish MZ YouTube setup, run this start-to-finish to get a TikTok account + automated posting online.

**Expected total time:** 30 minutes of your time + a 2–4 week approval window (async, happens in background).

**What you'll have at the end:**
1. `@minutezero` TikTok account (or closest handle available)
2. TikTok Business account tier (free, unlocks analytics + API)
3. Developer app registered and awaiting Content Posting API approval
4. Two working modes:
   - **Immediately:** Upload-to-Drafts API (you tap "Post" on your phone once/day)
   - **Once approved:** Direct Post API (fully automated, zero touch)

---

## Phase 1 — Account Creation (10 minutes)

### Step 1: Sign out of any existing TikTok

- Open tiktok.com in an **incognito window** (prevents account-picker confusion)
- If you have a personal TikTok, stay signed out for this whole flow

### Step 2: Create the TikTok account

- Go to tiktok.com → **Sign up**
- Choose **Use phone or email** → **Email**
- Email: your **Minute Zero Gmail** (the dedicated one we created — not wisseinc@gmail.com)
- Birthday: your real birthday (required, no workaround)
- Password: use a password manager; save it
- Verify the email code from inbox

### Step 3: Claim the @minutezero handle

- Go to Profile → **Edit profile**
- Username: try in order of preference:
  1. `@minutezero`
  2. `@minutezerochannel`
  3. `@minutezero.yt`
  4. `@theminutezero`
- **Match whatever YouTube handle you ended up with** so cross-platform search finds you
- Display name: `Minute Zero`
- Bio: `The moment it all broke. Business empire failures in 60 seconds. New vids daily.`
- Profile picture: upload `MinuteZero_ProfilePicture.png` from the workspace folder
- Save

### Step 4: Switch to Business Account (free, required for API)

- Profile → hamburger menu → **Settings and privacy**
- **Account** → **Switch to Business Account**
- Category: **Media & Entertainment** (closest fit)
- Confirm
- This unlocks: analytics, TikTok Developer API access, custom website link in bio

---

## Phase 2 — Developer App Registration (10 minutes)

### Step 5: TikTok Developers account

- Go to https://developers.tiktok.com/ in the same browser (already logged in)
- Click **Manage apps** → **Log in with TikTok**
- Select the Minute Zero TikTok account
- Grant developer permissions

### Step 6: Create the app

- Click **Create an app**
- App name: `Minute Zero Autopost`
- Description: `Automated posting for Minute Zero, a short-form business-failure history channel. Publishes 1–2 Shorts per day generated from in-house pipeline.`
- Category: **Content / Media**
- Platform: **Web** (not iOS/Android — this is server-to-server)
- Submit

### Step 7: Enable Content Posting API

- In your app dashboard, find the **Products** or **Add Products** section
- Enable **Content Posting API**
- Two tiers will appear:
  - **Inbox (Upload to Drafts)** — instant / minimal review → use this NOW
  - **Direct Post** — requires audit → **APPLY TODAY**, clock starts ticking
- For Direct Post application, you'll need:
  - App name ✅
  - Description (provided above) ✅
  - Demo video of the app in action — **skip if you can**; if required, submit this document as the use-case description
  - Privacy policy URL — use https://www.youtube.com/@minutezero if they'll accept; else use Notion or GitHub Pages placeholder
- Submit both applications

### Step 8: Get OAuth credentials

After app is created (not after approval — you can get these immediately):
- Copy **Client Key** → save as GH secret `TIKTOK_CLIENT_KEY`
- Copy **Client Secret** → save as GH secret `TIKTOK_CLIENT_SECRET`
- Add redirect URI: `http://localhost:5002/tiktok-callback` (matches our Flask OAuth pattern)

---

## Phase 3 — Local OAuth + Token Sync (10 minutes)

*This phase gets run after the Upload tier is available, even before Direct Post is approved.*

### Step 9: Add TikTok OAuth endpoints to video_app.py

I'll build these endpoints ahead of time — they'll mirror the YouTube OAuth flow pattern we already have. Endpoints:
- `/tiktok-connect?channel=mz` → starts OAuth, returns auth URL
- `/tiktok-callback?channel=mz` → receives code, saves `tiktok_token_mz.json`

### Step 10: Run the OAuth flow

- Start Flask: `python3 video_app.py` (or visit http://localhost:5002)
- Visit http://localhost:5002/tiktok-connect?channel=mz
- Copy the returned URL into a browser (TikTok account logged in)
- Approve scopes
- You'll be redirected to /tiktok-callback, which writes `tiktok_token_mz.json`

### Step 11: Sync token to GH Secret

Same protocol as `YT_TOKEN_TMF` (ref: `project_tmf_token_drift` memory):

```bash
cat "/sessions/nifty-nice-volta/mnt/Youtube Channels Project/tiktok_token_mz.json"
```

Copy the output → GitHub → repo Settings → Secrets → paste into `TIKTOK_TOKEN_MZ`.

---

## Phase 4 — Integrate into render + post pipeline

Once OAuth token is live:

- `auto_post_mz.py` (we'll build this) runs `video_mz.py.render_video()` → gets `{id}_tt.mp4`
- Calls TikTok Content Posting API upload endpoint:
  - **Upload tier:** `POST https://open.tiktokapis.com/v2/post/publish/inbox/video/init/` → uploads to drafts → you tap Post on your phone
  - **Direct Post tier (after approval):** `POST https://open.tiktokapis.com/v2/post/publish/video/init/` → fully auto
- GitHub Action `mz-autopost.yml` runs this at 9 AM CT daily alongside YT upload

---

## What to do WHILE waiting for Direct Post approval

**Option A (easiest):** Accept the daily 30-second tap. Morning routine:
- GH Action fires 9 AM CT
- MZ Short hits YT live + lands in TikTok drafts
- Phone buzz: "You have a TikTok draft ready"
- Open app, tap Post, done. ~30 seconds.

**Option B (fully auto, scrappy):** Use **Make.com** ($9/mo) or **iOS Shortcuts** to auto-trigger the Post tap when a new draft arrives. Works but fragile.

**Option C (skip TikTok until approved):** Post YT only for 2–4 weeks, then cut TikTok in when Direct Post goes live. Cleanest but loses 2–4 weeks of cross-platform growth.

**My recommendation: Option A.** It's the lowest total friction and preserves the cross-platform distribution while you wait.

---

## Common gotchas

1. **Birthday — TikTok rejects accounts under 13.** Use your real DOB.
2. **Region restriction — some TikTok API features are geo-gated.** US account should have full access; verify under Settings → Region.
3. **Handle conflict — if @minutezero is taken**, check if it's squatter-ish or an active account. If squatter, report via TikTok's username-takeover process with your YouTube URL as evidence of legitimate use. (Takes 3–5 business days.)
4. **Don't verify email from a VPN** — TikTok flags new business accounts on VPN IPs and can require phone verification before API access unlocks.
5. **The Business tier is reversible** — if you ever want to switch back to Personal, Settings → Account → Switch Account Type. But keep it Business for our use case.

---

## Post-setup checklist

- [ ] `@minutezero` (or chosen handle) created
- [ ] Profile picture + bio match YouTube channel
- [ ] Business account activated
- [ ] Developer app created, name "Minute Zero Autopost"
- [ ] Content Posting API enabled (Upload tier active; Direct Post applied)
- [ ] Client Key + Secret stored as GH secrets (`TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`)
- [ ] Redirect URI set to `http://localhost:5002/tiktok-callback`
- [ ] Local OAuth complete, `tiktok_token_mz.json` written
- [ ] Token synced to GH secret `TIKTOK_TOKEN_MZ`
- [ ] First draft uploaded and published manually as smoke test

Once all of these are ticked, MZ is cross-post ready.
