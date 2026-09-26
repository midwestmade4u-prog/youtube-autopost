# Minute Zero on Facebook — views and money (Sep 26 2026)

## Where things stood before today
- `mz-autopost.yml` has been uploading every MZ video to the FB Page via `/me/videos` = a **feed video post**, not a Reel. Feed videos are shown mostly to existing followers; Reels are the only FB surface with recommendation reach for a small page.
- Description was the title repeated. No hashtags. Step ran `continue-on-error`, so nothing reports whether uploads even succeed.
- Fixed today: `fb_reels_post.py` publishes through `/{page}/video_reels`, writes a real caption (hook + <=5 hashtags), time-compresses videos over 89 s (cap 1.12x), falls back to a feed post on failure, and honors the workflow's `dry_run` input.

## How Facebook pays in 2026 (what is actually verifiable)
- **Facebook Content Monetization** (the unified program: Reels, photos, text, stories) is **invite-only** per Meta's own page, with "express interest" in Professional Dashboard > Monetization. Meta says open enrollment is "planned". Third-party guides quote thresholds (5k–10k followers, 60k–600k minutes viewed / 60 days, 5 active videos) — treat these as the *signals Meta looks at*, not a published rule.
- **Qualified views** drive earnings, and a scroll-by does not count; holding past ~15 s is what registers. The retention work on the scripts pays here twice.
- Reported RPMs vary wildly by source ($0.02–$0.15 per 1k plays at the low end; $1–$10 per 1k qualified views at the high end; US business/finance audiences at the top). Plan on the low end until the dashboard shows real numbers.
- **Stars** unlock after monetization approval. **Branded content** tools open ~1k followers. **Subscriptions** ~10k followers. None of these are near-term for MZ.
- **Original-content rules** (Meta, Jul 2025 → 2026): penalties for reposts, other-platform watermarks, low-effort edits, >5 hashtags, caption stuffing. MZ scripts are original and the footage is licensed stock, so the risk is presentation: never post the TT/IG variants (end cards say "MORE ON YOUTUBE"), keep the caption clean, and don't spam-post.

## Plan
**Week 0 (now)**
1. Push today's changes. Run the workflow once with `dry_run=true` and read the "Post Facebook Reel" step log. Then a real run.
2. Open the Page in Professional Dashboard → Monetization → Content Monetization → **express interest**. Confirm the Page is in a monetization-eligible country, has a payout method on file, and passes Monetization Policies (no strikes).
3. Note today's follower count and 60-day minutes viewed (Professional Dashboard → Insights) as the baseline.

**Weeks 1–4: prove Reels reach**
4. One Reel per day is enough; do not double-post. Check after 7 days: Reels plays vs. the old feed videos, and the % of viewers who are non-followers (Insights → Reels → audience). If non-follower share is <50%, the recommendation engine isn't picking them up — revisit hook/caption before anything else.
5. Retention rubric applies identically on FB: 3-second hold and 15-second hold are the numbers to watch in Reels insights.
6. Reply to every comment in the first hour (Reels distribution weights early engagement). If that's not sustainable by hand, it's a small addition to `comment_curator.py`.

**Months 2–3: build the signals Meta invites on**
7. Target 5k followers and ~60k minutes viewed / 60 days as the first checkpoint (≈ 800 minutes/day ≈ 700 Reels views/day at MZ's current ~68 s avg watch). Follow-up: at 10k / 600k the invite odds reportedly jump.
8. Add a Facebook-native CTA. The spoken CTA says "Subscribe" (YouTube language); on FB the verb is "Follow". Cheapest fix: render an FB variant with a different spoken CTA in `video_mz.py`; until then leave it — it is not a policy problem, just a weaker ask.
9. Meanwhile the money is indirect: FB Reels → YouTube channel growth (YPP: 1,000 subs + 10M Shorts views / 90 days) and the affiliate plan already in `Affiliate_Marketing_Plan.md`. Put the affiliate/YouTube link in the Page bio and pinned post, not in Reel captions.

**Do not**
- Post the same Reel to the Page and a personal profile in Professional Mode — Meta's duplicate detection treats one as a repost.
- Buy followers or engagement (instant Content Monetization ineligibility).
- Cover tragedy/crime angles for FB — those formats are explicitly ad-restricted; the one_bad_day topics are fine, but keep Merrill/First Republic-style stories about decisions, not victims.

## Sources
- Meta, Facebook Content Monetization: https://creators.facebook.com/tools/facebook-content-monetization
- Meta, Reels Publishing API: https://developers.facebook.com/docs/video-api/guides/reels-publishing/
- Creators Agency, requirements 2026: https://creatorsagency.co/blog/facebook-content-monetization-requirements-2026
- ShortSync, CMP guide Aug 2026: https://www.shortsync.app/resources/facebook-content-monetization-program-2026
- FluxNote, Reels monetization 2026: https://fluxnote.io/guides/facebook-reels-monetization-requirements-2026
- ALM Corp, Meta original-content rules 2026: https://almcorp.com/blog/meta-original-content-rules-2026-facebook-instagram-creators/
- TechCrunch, Meta unoriginal-content crackdown (Jul 2025): https://techcrunch.com/2025/07/14/following-youtube-meta-announces-crackdown-on-unoriginal-facebook-content
