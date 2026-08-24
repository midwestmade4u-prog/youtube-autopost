# Metric definitions - read before quoting any retention number

Three different numbers are all called "retention". They are not interchangeable.

| Name | Definition | Typical TMF value |
|---|---|---|
| Export-derived | watch-time / **all views** / duration | 34% |
| Studio "average view duration %" | watch-time / **engaged views** / duration | **47%** |
| Studio "stayed to watch" | share who did not swipe away early | 74% |

Verified Aug 24 2026 on two TMF videos, same window: export arithmetic gave 33.6%
and 33.5%; Studio reported 47.4% for both. Ratio 1.40 and 1.39 - identical, so a
definition gap, not noise. **Export-derived retention reads about 1.4x LOW.**

## Rules

1. Name which of the three you mean before quoting a retention figure.
2. Never compare against a baseline unless both were measured the same way.
3. Always state the absolute count under a percentage. TMF's "47% subscriber drop"
   was 36 -> 19 subscribers: a swing of 17 people.
4. Use medians for per-video typicality, sums only for totals. TMF looked like it
   was collapsing (1612 -> 666 -> 332 weekly sums) because one 744-view video sat
   in the middle week; medians (13 -> 29.5 -> 104 -> 62 -> 52) show it improving.
5. Ratios over tiny denominators are noise.
6. Before attributing a metric change to content, check whether the code changed.
   A caption bug shipped ~100 days of broken Shorts and every weekly report
   explained it as a topic-selection problem.
