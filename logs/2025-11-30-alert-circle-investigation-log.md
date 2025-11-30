# Task Log: Alert Circle Investigation

- **Actions**:
    - Located `alert-circle` artifacts.
    - Added `--filter` argument to `vectalab/benchmark.py` for targeted debugging.
    - Added **Path Complexity** metric (segment count) to `vectalab/benchmark.py`.
    - Ran benchmark on `alert-circle` with `ultra` (default) and `clean` quality.

- **Findings**:
    - **Metrics**: SSIM (100%) and Topology (100%) are insensitive to "wobbliness" because the shape is structurally correct and the wobble is within the pixel grid tolerance.
    - **Visuals**: The SVG contains hundreds of path segments (198 for `ultra`, 135 for `clean`) instead of a simple circle. This is due to VTracer's spline fitting on raster data.
    - **Improvement**: Switching to `quality=clean` reduces complexity by ~32% (198 -> 135 segments), resulting in smoother curves.

- **Decisions**:
    - Added `Path Complexity` to the standard benchmark report to track "smoothness" in the future.
    - Recommend using `--quality clean` for the Golden Dataset icons/logos to prioritize smoothness.

- **Next Steps**:
    - User can run the full benchmark with `--quality clean` if they prefer smoother results.
