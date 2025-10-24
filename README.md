The code and data for the ICAIF paper "FAITH: A Framework for Assessing Intrinsic Tabular Hallucinations in Finance" [Link](https://www.arxiv.org/abs/2508.05201)

## Dataset Overview

FAITH is a dataset for evaluating tabular hallucinations in financial documents. It contains masked sentences from 10-K reports, paired with financial tables. The model is tasked to recover masked numerical span based on the context.

### Dataset Statistics

| Metric | Pilot Split | Main Split |
|--------|-------------|------------|
| Number of companies | 9 | 453 |
| Avg. context length (chars) | 14,148 | 12,843 |
| Avg. number of tables | 14.9 | 19.2 |
| Number of sentences | 164 | 1,122 |
| Number of answerable spans | 300 | 2,406 |

## Repository Structure

```
FAITH/
├── data/
│   ├── pilot.json              # Pilot dataset (9 reports)
│   └── main.json               # Full dataset (453 reports)
│
├── src/
│   ├── formulate_prompt.py     # Generate prompts from dataset
│   ├── eval.py                 # Evaluate model predictions
│   ├── prompt.yaml             # Prompt templates
│   └── unit_groups.yaml        # Financial unit definitions
│
├── LICENSE
└── README.md
```

## Dataset Format

The dataset is stored in JSON format with the following structure:

```json
{
  "metadata": {
    "cik": "1800",
    "filing_date": "2024-02-16",
    "item": "item7"
  },
  "tables": [
    {
      "table_index": 0,
      "pre_text": "The following table shows...",
      "cells": [
        ["Header1", "Header2", "Header3"],
        ["Value1", "Value2", "Value3"]
      ]
    },
    ...
  ],
  "instances": [
    {
      "uid": "c1b4a3d3-8410-4430-b328-038efb178ed3",
      "sentence": "The increase primarily consisted of revisions of previous estimates of 113.9 MMBOE...",
      "pre_sentence": "Total estimated net proved reserves as of December 31, 2023...",
      "post_sentence": "Our proved reserve life index increased to 10.9 years...",
      "mask_type": "A",
      "mask_span": [182, 192],
      "masked_sentence": "The increase primarily consisted of revisions of previous estimates of 113.9 MMBOE related to infill reserves in both our South Texas and Midland Basin programs, partially offset by [MASK] of production during 2023.",
      "ground_truth": "55.5 MMBOE",
      "gpt-4.1_label": "answerable",
      "gemini-2.5-pro-label": "answerable",
      "claude-sonnet-4-label": "answerable"
    },
    ...
  ]
}
```

### Field Descriptions

**Metadata Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `cik` | string | Company identifier (Central Index Key) |
| `filing_date` | string | Date of the 10-K filing |

**Table Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `table_index` | int | Sequential index of the table in the report |
| `pre_text` | string | Context text appearing before the table |
| `cells` | array | 2D array representing table rows and columns |

**Instance Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `uid` | string | Unique instance identifier (UUID format) |
| `sentence` | string | Original unmasked sentence containing the numerical value |
| `pre_sentence` | string | Sentence immediately before the masked sentence |
| `post_sentence` | string | Sentence immediately after the masked sentence |
| `mask_type` | string | Type of mask (e.g., "A", "B") |
| `mask_span` | [int, int] | Character indices `[start, end]` of the masked span in the original sentence |
| `masked_sentence` | string | Sentence with masked numerical value (shown as `[MASK]`) |
| `ground_truth` | string | The actual numerical value that should fill the mask |
| `gpt-4.1_label` | string | GPT-4.1 annotation: `"answerable"` or `"unanswerable"` |
| `gemini-2.5-pro-label` | string | Gemini 2.5 Pro annotation: `"answerable"` or `"unanswerable"` |
| `claude-sonnet-4-label` | string | Claude Sonnet 4 annotation: `"answerable"` or `"unanswerable"` |

## Installation

### Requirements

```bash
pip install pyyaml loguru tabulate
```


## Usage

### 1. Generate Prompts

Use `formulate_prompt.py` to generate prompts for model inference:

```bash
python src/formulate_prompt.py \
    --dataset_path data/main.json \
    --prompt_template_path src/prompt.yaml \
    --unit_group_path src/unit_groups.yaml \
    --table_format csv \
    --output_path data/main_prompt.jsonl
```

**Arguments:**
- `--dataset_path`: Path to the dataset JSON file (default: `data/main.json`)
- `--prompt_template_path`: Path to prompt templates (default: `src/prompt.yaml`)
- `--unit_group_path`: Path to unit definitions (default: `src/unit_groups.yaml`)
- `--table_format`: Table format in prompts, `csv` or `markdown` (default: `csv`)
- `--output_path`: Output JSONL file path (default: `data/main_prompt.jsonl`)

The output file will contain one JSON object per line with the following structure:

```json
{
  "uid": "c1b4a3d3-8410-4430-b328-038efb178ed3",
  "cik": "1800",
  "filing_date": "2024-02-16",
  "system_prompt": "You are a professional financial analyst.",
  "user_prompt": "Your task is to fill in the masked blank...",
  "ground_truth": "55.5 MMBOE"
}
```

### 3. Evaluate Predictions


After obtaining model predictions, evaluate them using `eval.py`:

```bash
python src/eval.py \
    --dataset_path data/main_prompt.jsonl \
    --prediction_path data/main_prediction.jsonl \
    --unit_group_path src/unit_groups.yaml
```


**Prediction File Format:**

Your prediction file should be a JSONL file with the following structure:

```json
{
  "uid": "c1b4a3d3-8410-4430-b328-038efb178ed3",
  "answer": "55.5 MMBOE"
}
```

**Evaluation Metrics:**

The evaluation script will output:
- Accuracy
- Total count
- Correct count
- Incorrect count

The evaluator uses sophisticated numeric comparison that:
- Handles different units (million, billion, thousand, etc.)
- Supports various formats (percentages, basis points, currencies)
- Accounts for numerical precision and rounding
- Allows for relative tolerance (2% by default)

## Configuration Files

### prompt.yaml

Contains three prompt templates:

1. **`system_prompt`**: System-level instructions for the model
2. **`user_prompt_answerability_annotation`**: For annotating whether spans are answerable or unanswerable
3. **`user_prompt_prediction`**: For generating predictions for masked values

These prompts are used by `formulate_prompt.py` to create the final prompts sent to language models.

### unit_groups.yaml

Defines financial and numerical units with their aliases and scaling factors:

**Scaling Units:**
- `million` (1e6), `billion` (1e9), `trillion` (1e12), `thousand` (1e3)
- `percent` (1e-2), `bps` (basis points, 1e-4)

**Special Units:**
- Financial: `eps` (earnings per share), `cps` (cents per share)
- Energy: `boe` (barrel of oil equivalent), `kwh`, `btu`
- Currency: `usd`, `eur`, `gbp`, `jpy`
- Postfix units: `per_share`, `per_annum`, `per_month`, `per_unit`

The evaluation script uses these definitions to correctly parse and compare numerical values with different units.

## Citation

If you use this dataset, please cite:

```bibtex
@inproceedings{faith2024,
  title={FAITH: A Framework for Assessing Intrinsic Tabular Hallucinations in Finance},
  author={[Authors]},
  booktitle={ACM International Conference on AI in Finance (ICAIF)},
  year={2025},
  url={https://www.arxiv.org/abs/2508.05201}
}
```

## License

See [LICENSE](LICENSE) file for details.
