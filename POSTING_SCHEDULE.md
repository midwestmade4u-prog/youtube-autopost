# Channel Posting Schedule
*Last updated: May 4, 2026*

---

## The Mind Files (TMF)
**Workflow:** `tmf-autopost.yml`
**Posts per day:** 3 (burst guard enforced)

| Slot | UTC Cron | Approx CDT |
|------|----------|------------|
| Morning | `0 13 * * *` | ~8 AM |
| Afternoon | `0 18 * * *` | ~1 PM |
| Night | `0 3 * * *` | ~10 PM |

> GH Actions fires 30 min–3 hrs late on free tier — times are approximate.

---

## Minute Zero (MZ)
**Workflow:** `mz-autopost.yml`
**Posts per day:** 2 (Phase 2 — graduated May 4 2026)

| Slot | UTC Cron | Approx CDT | Status |
|------|----------|------------|--------|
| Morning | `0 14 * * *` | ~9 AM | ✅ Active — Format A (One Bad Day) |
| Evening | `0 0 * * *` | ~7 PM | ✅ Active — Format B/C rotation |

> Phase 2 graduated May 4 after Day 7 deep dive: 5/7 post-v3.1 videos hit ≥40% stayed-to-watch.
> Morning = Format A always. Evening = time-based B/C rotation.
> If evening slot avg stayed-to-watch falls below 40% after 7 days, revert to 1/day.

---

## Bible Story Garden (BSG)
**Workflow:** `youtube-autopost.yml` (BSG step)
**Posts per day:** 2 (target post-migration)

| Slot | Target CDT | Status |
|------|------------|--------|
| Midday | Noon | ⏸ Manual YouTube Studio videos through May 6 |
| Evening | 7 PM | ⏸ Manual YouTube Studio videos through May 6 |

> BSG automation re-enables after May 4 Gmail ownership transfer.
> Steps to re-enable: transfer → re-OAuth → paste token → remove `if: false` from BSG step.

---

## Legacy / Disabled
| Workflow | Notes |
|----------|-------|
| `youtube-autopost.yml` TMF step | ❌ Disabled Apr 30 — was double-posting alongside `tmf-autopost.yml` |
| `youtube-autopost.yml` BSG step | ❌ Disabled pending May 4 migration |

---

## Quick Reference — What fires today
| Time (CDT, approx) | Channel | Action |
|--------------------|---------|--------|
| ~8 AM | TMF | Auto-generate + post |
| ~9 AM | MZ | Auto-generate + post (Format A) |
| ~1 PM | TMF | Auto-generate + post |
| ~10 PM | TMF | Auto-generate + post |
