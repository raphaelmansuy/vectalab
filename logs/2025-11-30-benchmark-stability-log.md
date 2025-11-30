# Task Log: Benchmark Stability Fix

- **Actions**:
    - Analyzed the "stuck at 38%" issue.
    - Identified **Resource Exhaustion** as the root cause: Running 10 concurrent instances of `vectalab premium` (which loads the heavy SAM model) overwhelms system RAM/VRAM, leading to thrashing or deadlocks.
    - Updated `vectalab/benchmark.py` to:
        - Automatically set a safe default for `workers` (max 4) if not specified.
        - Display a **Warning** if the user manually sets `workers > 4`.
    
- **Decisions**:
    - Capped default workers at 4. Even on high-end machines, 4 concurrent SAM models is a heavy load. Stability > Speed for benchmarks.
    - Kept the timeout logic added previously as a secondary safety net.

- **Next Steps**:
    - User should re-run the benchmark with the default worker count (or explicitly `--workers 4`).

- **Lessons**:
    - ML workloads are not CPU-bound in the traditional sense; they are Memory/VRAM bound. Parallelism must be conservative.
