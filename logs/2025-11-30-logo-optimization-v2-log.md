# Logo Optimization Log (v2)

## Changes
- Added `LogoQuality` presets to `vectalab/quality.py`:
  - `clean`: Original settings (best for simple flat logos)
  - `balanced`: Default, slightly better detail
  - `high`: More detail, better colors (48 max), sharper corners
  - `ultra`: Maximum fidelity, up to 64 colors, very precise paths
- Updated `vectorize_logo_clean` to accept `quality_preset`.
- Updated `vectorize_logo_clean` to boost palette size for `high` (48) and `ultra` (64) presets when image is complex.
- Updated `vectalab/cli.py` to add `--quality` / `-q` option to `logo` command.

## Verification
- Tested with `google.png` (simple logo):
  - Balanced: 96.26% SSIM
  - High: 96.42% SSIM
  - Ultra: 96.52% SSIM
- Verified help text displays new options.

## Usage
To improve vectorization of complex logos:
```bash
vectalab logo input.png --quality high
# or
vectalab logo input.png --quality ultra
```
