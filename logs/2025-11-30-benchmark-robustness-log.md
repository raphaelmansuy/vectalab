# Task Log: Benchmark Robustness

- **Actions**:
    - Investigated the "stuck at 99%" issue reported by the user.
    - Identified that `subprocess.run` calling `vectalab` was missing a timeout, causing indefinite hangs on complex SVGs.
    - Modified `vectalab/benchmark.py` to:
        - Add a **120-second timeout** to the vectorization process.
        - Implement **incremental saving** to `results.jsonl` so data isn't lost on crash/interrupt.
        - Handle `KeyboardInterrupt` (Ctrl+C) gracefully to generate a partial report.

- **Decisions**:
    - Set timeout to 120s. This is generous enough for even complex SVGs on a modern machine, but prevents infinite hangs.
    - Used JSONL for incremental storage as it's append-only and corruption-resistant.

- **Next Steps**:
    - User should restart the benchmark. It will now skip/fail the problematic image instead of hanging, and finish successfully.

- **Lessons**:
    - Always put timeouts on subprocess calls in batch processing pipelines.
    - Incremental result saving is crucial for long-running benchmarks.
