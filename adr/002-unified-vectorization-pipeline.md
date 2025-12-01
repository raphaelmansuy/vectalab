# 002. Unified Vectorization Pipeline and Reporting

Date: 2025-12-01
Status: Proposed

## Context

The `vectalab` CLI currently implements multiple vectorization methods (`auto`, `hifi`, `standard`, `premium`) across different execution paths (`_run_auto_conversion`, `_run_hifi_conversion`, `_run_standard_conversion`). 

Each path handles its own execution logic, metric calculation, and result reporting. This has led to inconsistencies:
- **Reporting:** `auto` mode provides a detailed table with SOTA metrics (LPIPS, DISTS, etc.), while `hifi` and `standard` modes provide limited summaries (SSIM, file size).
- **Metrics:** Not all conversions calculate the full suite of quality metrics (SSIM, Topology, Edge Accuracy, Delta E, LPIPS, DISTS, GMSD).
- **Maintenance:** Adding a new metric or changing the reporting format requires updating multiple functions.
- **User Experience:** Users get different feedback depending on the method used, making it hard to compare results across methods.

The goal is to ensure every conversion command produces a detailed session summary with all quality metrics, including SOTA perceptual metrics, and to consolidate the underlying conversion logic.

## Decision

We will refactor the `vectalab` CLI to use a **Unified Vectorization Pipeline**.

### 1. Unified `VectorizationResult` Data Structure
We will define a standard data class (or dictionary structure) to hold the results of any vectorization process.
```python
@dataclass
class VectorizationResult:
    input_path: Path
    output_path: Path
    method: str
    duration: float
    file_size: int
    metrics: Dict[str, Any]  # SSIM, LPIPS, etc.
    stats: Dict[str, Any]    # Path counts, segments, etc.
    error: Optional[str] = None
```

### 2. Consolidated Execution Flow
We will create a single entry point for running conversions that handles the common lifecycle:
1.  **Preparation:** Validate inputs, setup paths.
2.  **Execution:** Delegate to the specific strategy (`hifi`, `premium`, `logo`, `sam`, etc.) to generate the SVG.
3.  **Analysis:** Run a standardized `calculate_metrics` function on the result.
4.  **Reporting:** Pass the `VectorizationResult` to a standardized `display_report` function.

### 3. Standardized Metric Calculation
The `_calculate_full_metrics` function (currently in `cli.py`) will be promoted to a core utility (e.g., in `vectalab.analysis`) and applied to **all** successful conversions by default.
- It will calculate: SSIM, Topology, Edge Accuracy, Delta E.
- It will optionally (or by default, if dependencies exist) calculate SOTA metrics: LPIPS, DISTS, GMSD.
- It will analyze SVG complexity (path counts, curve fractions).

### 4. Unified Reporting
A single `display_session_summary(result: VectorizationResult)` function will be responsible for rendering the Rich table.
- It will adapt to the available metrics (e.g., hide LPIPS if not available).
- It will provide context/meaning for each metric (as seen in the current `auto` report).
- It will consistently format values (colors for good/bad ranges).

### 5. Refactored CLI Commands
The `convert` command and its sub-handlers (`_run_*`) will be refactored to use this pipeline.
- `_run_auto_conversion` will become a strategy selector that delegates to the specific method but returns the common result structure.
- `_run_hifi_conversion` and others will be wrapped to return the common result structure.

## Consequences

### Positive
- **Consistency:** Every user interaction yields the same high-quality feedback.
- **Observability:** Users gain deep insights into the quality of every conversion, not just "auto" ones.
- **Maintainability:** Reporting logic is centralized. Adding a new metric happens in one place.
- **Extensibility:** New vectorization methods just need to produce an SVG; the pipeline handles the rest.

### Negative
- **Performance:** Calculating full SOTA metrics (especially LPIPS) involves loading ML models and rendering SVGs, which adds overhead (seconds) to every conversion.
    - *Mitigation:* We can add a `--fast` or `--no-metrics` flag to skip heavy analysis for users who want raw speed.
- **Dependencies:** Requires `cairosvg` and `torch`/`lpips` for full reporting, though the system should gracefully degrade if they are missing.

## Implementation Plan

1.  Extract `calculate_full_metrics` to `vectalab/analysis.py` (or `quality.py`).
2.  Create `VectorizationResult` class.
3.  Create `display_session_summary` in `vectalab/output.py` (or `cli.py`).
4.  Refactor `_run_hifi_conversion`, `_run_standard_conversion`, and `_run_auto_conversion` to return `VectorizationResult`.
5.  Update the main `convert` command to orchestrate the pipeline.
