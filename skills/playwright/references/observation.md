# Temporal Observation

`pw observe` samples a viewport or element and builds labeled contact sheets for video, animation, transient UI, and dashboards.

```bash
pw observe
pw observe e12 --duration 20s --every 1s
pw observe 'video' --duration 8s --fps 4
pw observe --duration 30s --frames-per-sheet 24 --columns 4
```

`--every` and `--fps` are mutually exclusive requested rates. Actual throughput is measured; missed deadlines are skipped rather than captured in a burst.

Defaults:

- Duration: 10 seconds
- Interval: 1 second
- Maximum: 120 frames
- Contact sheet: 24 frames in 4 columns

Use `--output <new-or-empty-directory>` to choose the artifact directory. Output contains raw frames, numbered contact sheets, and `manifest.json`. The manifest records requested and achieved rates, timing, skipped frames, target bounds, warnings, and sheet-cell mappings.

The command fails before capture when the requested schedule exceeds `--max-frames`. A missing or ambiguous target produces a partial manifest and nonzero exit. Nearly black or unchanged captures are reported as warnings, not diagnosed as DRM.
