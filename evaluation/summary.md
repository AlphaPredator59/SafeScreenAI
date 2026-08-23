# SafeScreen AI — Benchmark Evaluation Report

## Executive Summary

- **Dataset Total Samples**: 12
- **Available Samples Evaluated**: 3
- **Unavailable Placeholder Samples**: 9
- **Inference Device**: CPU

> [!NOTE]
> Headline metrics are computed exclusively over available media with verified ground truth. Results from small sample counts are preliminary diagnostics and not statistically representative.

---

## 1. Headline Decision Metrics (Safe vs Unsafe)

| Metric | Score | Note |
| :--- | :--- | :--- |
| **Accuracy** | `100.0%` | (TP + TN) / Total |
| **Precision** | `100.0%` | TP / (TP + FP) |
| **Recall** | `100.0%` | TP / (TP + FN) |
| **F1 Score** | `1.0000` | Harmonic mean of Precision & Recall |
| **Review Rate** | `33.3%` | Proportion resulting in REVIEW_REQUIRED |
| **False Positive Rate (FPR)** | `0.0%` | Safe misclassified as Unsafe |
| **False Negative Rate (FNR)** | `0.0%` | Unsafe misclassified as Safe |

---

## 2. Confusion Matrices

### Binary Confusion Matrix

| Expected \ Predicted | Pred SAFE | Pred UNSAFE |
| :--- | :--- | :--- |
| **Exp SAFE** | `2` (TN) | `0` (FP) |
| **Exp UNSAFE** | `0` (FN) | `1` (TP) |

### Multiclass Confusion Matrix

| Expected \ Predicted | Pred APPROVED | Pred REVIEW_REQUIRED | Pred REJECTED |
| :--- | :--- | :--- | :--- |
| **Exp APPROVED** | `2` | `0` | `0` |
| **Exp REVIEW_REQUIRED** | `0` | `1` | `0` |
| **Exp REJECTED** | `0` | `0` | `0` |

---

## 3. Dataset Sample Status Breakdown

| Sample ID | Scenario | Local File | Status | Expected Decision | Predicted Decision | Match |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `scenario_01_cooking` | Benign cooking with knife | `Cooking.mp4` | **EVALUATED** | `APPROVED` | `APPROVED` | `PASS` |
| `scenario_02_shooting_range` | Controlled shooting-range practice | `Shooting Range.mp4` | **EVALUATED** | `APPROVED` | `APPROVED` | `PASS` |
| `scenario_03_slap` | Physical assault / slap | `Slap.mp4` | **EVALUATED** | `REVIEW_REQUIRED` | `REVIEW_REQUIRED` | `PASS` |
| `scenario_04_threatening_weapon` | Threatening weapon interaction | `threatening_weapon.mp4` | *UNAVAILABLE* | `REJECTED` | `—` | `N/A` |
| `scenario_05_weapon_ambiguous` | Weapon with ambiguous context | `weapon_ambiguous.mp4` | *UNAVAILABLE* | `REVIEW_REQUIRED` | `—` | `N/A` |
| `scenario_06_sports_activity` | Benign sports activity | `sports_activity.mp4` | *UNAVAILABLE* | `APPROVED` | `—` | `N/A` |
| `scenario_07_educational_demo` | Educational demonstration involving potentially dangerous object | `educational_demo.mp4` | *UNAVAILABLE* | `APPROVED` | `—` | `N/A` |
| `scenario_08_toxic_speech` | Toxic/harassing speech without physical violence | `toxic_speech.mp4` | *UNAVAILABLE* | `REVIEW_REQUIRED` | `—` | `N/A` |
| `scenario_09_audio_free_violence` | Audio-free violent scene | `silent_violence.mp4` | *UNAVAILABLE* | `REVIEW_REQUIRED` | `—` | `N/A` |
| `scenario_10_audio_only_threat` | Audio-only threatening speech where visual evidence is weak | `audio_threat.mp4` | *UNAVAILABLE* | `REVIEW_REQUIRED` | `—` | `N/A` |
| `scenario_11_conflicting_signals` | Conflicting visual and contextual evidence | `conflicting_signals.mp4` | *UNAVAILABLE* | `REVIEW_REQUIRED` | `—` | `N/A` |
| `scenario_12_ordinary_scene` | Ordinary scene with no policy risk | `ordinary_scene.mp4` | *UNAVAILABLE* | `APPROVED` | `—` | `N/A` |

---

## 4. Contextual Analysis & Disagreements

- **Context Categorization Accuracy**: `100.0%` (3/3)
- **Cross-Modal Disagreements Detected**: `1`

| Sample | Scenario | YOLO Objects | Qwen Context | Resolved by Context |
| :--- | :--- | :--- | :--- | :--- |
| `scenario_01_cooking` | Benign cooking with knife | `bowl, broccoli, dining table, fork, knife, oven, person, spoon` | `Cooking` | YES (Mitigated) |

---

## 5. Policy Category Classification Metrics

| Category | Precision | Recall | F1 Score | Support (True Positives in Eval) |
| :--- | :--- | :--- | :--- | :--- |
| **threats** | `100.0%` | `100.0%` | `1.0000` | 1 |

---

## 6. Pipeline Latency Breakdown

- **Total Pipeline Mean Latency**: `27.82s` (Median: `28.01s`, Min: `18.05s`, Max: `37.40s`)

| Stage | Mean Latency | Median Latency | Min Latency | Max Latency |
| :--- | :--- | :--- | :--- | :--- |
| **metadata** | `0.13s` | `0.11s` | `0.10s` | `0.20s` |
| **frame_processing** | `2.56s` | `3.30s` | `0.39s` | `3.99s` |
| **vision_yolo** | `1.97s` | `1.78s` | `0.51s` | `3.63s` |
| **audio_extraction** | `0.11s` | `0.13s` | `0.06s` | `0.14s` |
| **transcription_whisper** | `0.94s` | `1.11s` | `0.00s` | `1.69s` |
| **text_moderation** | `1.95s` | `0.00s` | `0.00s` | `5.86s` |
| **context_qwen** | `20.15s` | `15.71s` | `15.22s` | `29.51s` |
| **moderation_engine** | `0.00s` | `0.00s` | `0.00s` | `0.00s` |

---

## 7. Modality Ablation Analysis

| Ablation Mode | Modalities Included | Accuracy | Precision | Recall | F1 Score | Mean Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **full** | Visual + Audio + Text + Qwen | `100.0%` | `100.0%` | `100.0%` | `1.0000` | `27.82s` |
| **visual_qwen** | Visual + Qwen Context | `100.0%` | `100.0%` | `100.0%` | `1.0000` | `14.14s` |
| **visual_audio** | Visual + Whisper + Text Moderator | `33.3%` | `0.0%` | `0.0%` | `0.0000` | `5.40s` |
| **visual_only** | Visual Only | `33.3%` | `0.0%` | `0.0%` | `0.0000` | `3.89s` |