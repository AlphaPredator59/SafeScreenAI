# SafeScreen AI — Benchmark Error Analysis

**Total Evaluated Samples**: 3
**Total Decision Errors**: 0

---
## Error Diagnostics: Zero Decision Errors

All evaluated available samples matched their ground-truth moderation decisions and policy classifications.

### Evaluated Sample Ground Truth Validations:
- **`scenario_01_cooking` (Benign cooking with knife)**: Predicted `APPROVED` (Risk: `LOW` / `0.0000`) exactly matched Ground Truth (`APPROVED`).
- **`scenario_02_shooting_range` (Controlled shooting-range practice)**: Predicted `APPROVED` (Risk: `LOW` / `0.0000`) exactly matched Ground Truth (`APPROVED`).
- **`scenario_03_slap` (Physical assault / slap)**: Predicted `REVIEW_REQUIRED` (Risk: `HIGH` / `0.7650`) exactly matched Ground Truth (`REVIEW_REQUIRED`).