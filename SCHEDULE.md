# Posting Schedule -- Source of Truth

Last updated: Jul 5 2026. This file is the canonical reference for cadence across
all 3 channels. If you change a cron schedule, a DAILY_POST_CAPS value, or a
channel_monitor.py schedule_days entry, update this file in the same commit.

## Shorts (auto_post.py / auto_post_mz.py)

| Channel | Workflow file          | Cron            | Cadence | Cap/day |
|---------|-------------------------|------------------|---------|---------|
| TMF     | tmf-autopost.yml         | 0 13 * * *       | 7/wk (1x/day, every day) | 1 |
| BSG     | bsg-autopost.yml         | 0 17 * * *       | 7/wk (1x/day, every day) | 1 |
| MZ      | mz-autopost.yml          | 0 14 * * *       | 7/wk (1x/day, every day) | 1 |

- Times are UTC in cron; comments in each workflow file show the CT equivalent.
- `youtube-autopost.yml` is DISABLED (schedule trigger removed, BSG job set to
  `if: false`). It used to duplicate-post BSG content alongside bsg-autopost.yml
  (~21/wk combined vs 7/wk expected) -- fixed Jul 5 2026. Do not re-enable its
  schedule without also removing bsg-autopost.yml's, or BSG will double-post again.
- `DAILY_POST_CAPS` in `auto_post.py`: `{"tmf": 1, "bsg": 1, "mz": 1}`. This is a
  safety ceiling, not the schedule itself -- it exists so a manual workflow_dispatch
  or a retry can't stack a 2nd post on top of the scheduled one.

## Longform (auto_post_*_longform.py)

All three channels share the same longform cadence, 3x/week:

| Day       | Time (CT) | Cron (UTC)      |
|-----------|-----------|------------------|
| Sunday    | 10 AM     | 0 15 * * 0       |
| Tuesday   | 9 AM      | 0 14 * * 2       |
| Friday    | 12 PM     | 0 17 * * 5       |

Workflow files: `tmf-longform.yml`, `bsg-longform.yml`, `mz-longform.yml`.
This cadence has NOT changed as part of the Jul 5 2026 Shorts cadence work.

## Monitoring

- `channel-monitor.yml` runs nightly at 2 AM CT (`0 7 * * *`), calling
  `channel_monitor.py`. It checks the last ~26h of YouTube uploads per channel
  against `CHANNELS[channel]["expected_posts"]`, gated by `schedule_days`.
- `schedule_days` (Python `datetime.weekday()`: Mon=0 ... Sun=6) currently reads
  `(0,1,2,3,4,5,6)` for all 3 channels -- every day is a posting day, so
  `expected_posts` (all set to 1) applies every night. If cadence is ever cut
  below 7/wk again, `schedule_days` MUST be narrowed to the actual posting days,
  or the monitor will false-alarm "missed_posts" on the off days and may
  auto-dispatch an unwanted extra run.
- Alert emails only fire for CRITICAL_ISSUE_TYPES (missed_posts, yt_api_error,
  no_workflow_runs, silent_upload_failure). As of Jul 5 2026 these read as
  "Expected 1 / Published N" so the shortfall is unambiguous at a glance.
- `weekly-digest.yml` runs Sunday 3 AM CT (`0 8 * * 0`) -- separate from the
  nightly monitor, produces the weekly analytics digest Matt reviews by hand.

## Change log

- **Jul 5 2026**: BSG duplicate-workflow bug fixed (youtube-autopost.yml disabled).
  All 3 channels briefly cut to 5-6/wk (TMF) and 3-4/wk (MZ) per weekly analytics
  review, then reverted same day to 7/wk (1x/day, every day) per Matt's explicit
  daily-minimum requirement. Net change from before: same weekly volume, but
  consolidated from 2 posting slots/day down to 1, and BSG's duplicate bug fixed.
