# Minute Zero — Development Plan v2 (Apr 24, 2026)

**v2 changes from v1:** Adds paired TikTok launch, cross-post architecture, Phase 4 long-form graduation, and the 6 v3-prompt deltas from the Apr 24 viral research.

---

## The strategic reframe (read first)

**Old goal:** Reach YouTube Shorts monetization (1K subs + 10M Shorts views in 90 days).
**New goal:** Land **one breakout video at 500K+ views** on MZ within 60 days of launch, on any platform.

**Why the reframe:** Shorts ad revenue is $0.01–$0.15 per 1K views. Even 10M views ≈ $100–$1,500. The real money is:
1. Long-form graduation (Phase 4 — 10–12 min deep-dives, CPM $15–$40)
2. Brand deals (unlocked at ~50K subs)
3. Affiliate links (books about each company we cover)

Cross-platform posting to YouTube + TikTok + Instagram gives 3× distribution for the same production cost. MZ is our cross-post test bed; if it works, we retrofit TMF and BSG.

---

## Phase 0 — Pre-launch (now through Monday 2026-04-27)

**Already done:**
- Niche locked (Business Failures, three-format umbrella)
- Channel name "Minute Zero" + dedicated Gmail
- Branding v3 (profile, banner, watermark)
- Channel setup doc (description, keywords, upload defaults)
- Topic bank v1 (70 topics, Format B reordered to Tier 1/2)
- Script generator v3 prompt (6 deltas from viral research)
- `video_mz.py` render pipeline with clean-master + per-platform variants
- Viral research findings written up
- TikTok setup walkthrough pre-written

**Still to do before launch:**
- [ ] Pexels API key — sign up at pexels.com/api, save as env var + GH secret `PEXELS_API_KEY`
- [ ] OpenAI API key confirmed in env (or switch to Anthropic Claude API via `ANTHROPIC_API_KEY`)
- [ ] First local render dry-run (pick 1 Format A topic → run `video_mz.py` end-to-end → inspect MP4s)
- [ ] MZ YouTube OAuth → save token, sync to GH secret `YT_TOKEN_MZ`
- [ ] Grab MZ YouTube channel ID → fill into `YT_CHANNEL_IDS["mz"]` in video_app.py
- [ ] Write `auto_post_mz.py` (topic pick → script gen → video_mz.render → YT upload)
- [ ] Write `mz-autopost.yml` GH Actions workflow (copy of tmf-autopost.yml)
- [ ] First manual test upload (unlisted) → verify routing hits MZ channel, not TMF

**Parallel track (start now, runs async):**
- [ ] TikTok account creation (see MZ_TikTok_Setup_Walkthrough.md)
- [ ] TikTok Developer app
- [ ] Apply for Direct Post API (2–4 week clock)
- [ ] While waiting: Upload-to-Drafts API works immediately

---

## Monday 2026-04-27 — Stack Day

Big day, three channels progressed in one sitting:

1. **Morning: BSG brand transfer** — Gmail-to-Gmail transfer from midwestmade4u → bsgchannel99. Per-channel Gmail scaling pattern locked.
2. **Mid-day: MZ OAuth + first test upload (unlisted)** — confirm pipeline works end-to-end on YouTube.
3. **Afternoon: TikTok account creation + dev app submission** — starts the Direct Post API clock.

---

## Phase 1 — Cold-start + data gathering (launch Day 1 through Day 14)

- **Output:** 1 Format A Short / day at 9 AM CT, YouTube only (for the first 7 days)
- **Cross-post:** Once TikTok Upload API is working, also post to TikTok (Upload-to-Drafts mode; manual Post tap on phone)
- **Hook rotation:** Rotate all 3 hook styles (bold_claim, curiosity_gap, time_anchor) evenly → ~4–5 videos per style
- **No Format B or C yet** — keep topic variable controlled
- **No Instagram yet** — adds dev scope without proven value

**Success criteria for Phase 1:**
- Pipeline stable (no failed runs in 7 consecutive days)
- No platform routing errors (no MZ videos land on TMF, etc.)
- At least 1 video hits 10K+ views
- At least one hook style shows measurable lead in retention

---

## Phase 2 — Three-format rotation + cross-post stabilization (Day 15 through Day 30)

- **Output:** 2 Shorts / day
  - 9 AM CT = Format A (one_bad_day) — daily
  - 7 PM CT = alternates Format B (unknown_failure) and Format C (near_death)
- **Cross-post:** YouTube + TikTok live. Direct Post API should be approved by ~Day 21.
- **v4 prompt update:** Based on Phase 1 hook data, update v3 → v4 weighting winning hook style 60–70% of output.

**Decision point Day 25 (Format B kill criterion):**
- After 10 Format B videos published → compare average views vs Format A
- If Format B avg < 60% of Format A → pull Format B, redistribute those slots to A + C

---

## Phase 3 — Add Instagram + first viral moment (Day 31 through Day 60)

- **Output:** 2 Shorts / day across YouTube + TikTok + Instagram Reels (all 3)
- **Goal:** One video to 500K+ views on any platform. This is the north-star metric.
- **Iteration cadence:** Weekly prompt tweaks based on retention + VVSA data
- **Thumbnail A/B:** Test 2 thumbnail variants per video for first 2 weeks

---

## Phase 4 — Long-form graduation (Day 60 onward)

**Trigger:** MZ hits ~1K subs on YouTube (projected around Day 45–60 given validation).

**Launch:** 10–12 minute long-form versions of our best-performing Shorts topics. Same story, full depth.

- CPM jumps from $0.01–$0.15 (Shorts) to $15–$40 (long-form business/finance)
- Single long-form at 100K views = $1,500–$4,000 revenue
- Shorts become the top-of-funnel; long-form is the revenue engine
- Production: Remotion + Claude (already noted in your tooling stack for future long-form)

**Format:** Each long-form covers ONE company, uses the same 4-beat story structure, plus:
- Expanded "before the fall" context (5–6 min)
- Deeper "minute zero" reconstruction (3–4 min)
- "Where are they now" epilogue (1–2 min)

---

## Phase 5 — Steady state + scale the pattern (Day 90 onward)

- Full analytics review at Day 90
- If monetizing: consider Channel #4 using the same stack. The full pattern (per-channel Gmail → branding → topic bank → script gen → video pipeline → cross-post → long-form graduation) is now a **playbook**, not a one-off. Spinning up channel 4 should take 1–2 weeks, not 2 months.
- If not monetizing: examine retention data, possibly pivot Format or kill cross-post cost if one platform isn't pulling weight.

---

## Error-prevention rules (baked in from past channel learnings)

1. **Sheets logging env vars** — when writing `mz-autopost.yml`, explicitly expose `GOOGLE_SHEET_ID` + `SHEETS_SA_JSON` as `env:` in the workflow YAML, not just as GH secrets. (Ref: `project_sheets_logging_fixed` memory — this bit BSG.)
2. **Channel routing** — never rely on `onBehalfOfContentOwnerChannel` — it's CMS-only. Token identity drives routing. Verify with `channels().list(mine=True)` before upload. (Ref: `project_bsg_routing_fix` memory.)
3. **Token drift protocol** — after any local re-OAuth, immediately re-paste the local token file contents into the matching GH secret (`YT_TOKEN_MZ`, `TIKTOK_TOKEN_MZ`). Drift = 401 outage. (Ref: `project_tmf_token_drift` memory.)
4. **Don't modify BSG or TMF code paths while building MZ.** All MZ code lives in:
   - `video_mz.py` (new)
   - `auto_post_mz.py` (new, to build)
   - `mz-autopost.yml` (new, to build)
   - `MZ_Channel/` doc folder
   
   Shared touchpoints: `video_app.py` `YT_TOKEN_FILES` + `YT_CHANNEL_IDS` dicts — already updated with MZ stubs. Nothing else in BSG/TMF should change during MZ build.
5. **Watermark rule for cross-post** — master MP4 has MZ watermark only. Never embed "from YouTube" or any platform-specific branding in the master. Variants add platform-specific end cards.
6. **Test upload must be unlisted first** — before cron fires, one manual upload to verify the whole chain (script → render → upload → correct channel → correct metadata). Never debug channel routing on a live, indexable video.

---

## What makes this plan resilient to session resets

Every file it references lives in the workspace folder and is pointed to from `MEMORY.md`. If we lose session context:
- Read `project_channel3_plan` memory → points here
- Read `project_mz_viral_research_apr24` memory (to be created) → points to the viral research findings
- Read this doc → re-grounds on full plan
- Read `MZ_Script_Generator_Prompt_v3.md`, `MZ_Topic_Bank_v1.md`, `MZ_TikTok_Setup_Walkthrough.md` for reference material
- Read `video_mz.py` for the actual render pipeline

No critical planning state lives only in conversation context. If a session dies mid-work, the next session can be productive in 5 minutes.
