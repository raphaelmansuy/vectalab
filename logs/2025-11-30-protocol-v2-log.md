# Task Log: Protocol v2 & Golden Dataset

- **Actions**:
    - Created `docs/protocol_v2.md` defining the new benchmarking standard.
    - Created `scripts/download_golden_dataset.py` to fetch diverse SVGs (Icons, Logos, Illustrations).
    - Downloaded ~112 SVGs into `golden_data/`.
    - Modified `vectalab/benchmark.py` to support `--sets golden`.
    - Implemented automatic rasterization of Golden SVGs to PNGs for benchmarking.
    - Updated `README.md` with new benchmark commands and documentation link.

- **Decisions**:
    - Used `cairosvg` to rasterize Golden SVGs to ensure high-quality ground truth inputs.
    - Structured `golden_data` into `icons`, `logos`, and `illustrations` for categorized testing.
    - Kept `golden_data` separate from `test_data` to distinguish between legacy and v2 datasets.

- **Next Steps**:
    - Run a full benchmark on the Golden Dataset and analyze per-category performance.
    - Tune `vectalab` parameters based on Golden Dataset results.

- **Lessons**:
    - `cairosvg` is essential for creating reliable raster inputs from SVGs.
    - The W3C test suite has some broken links; need to maintain a local copy or reliable mirror.
