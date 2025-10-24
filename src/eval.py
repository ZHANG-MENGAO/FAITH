import re
from typing import Tuple
from pathlib import Path
from loguru import logger
import yaml
from argparse import ArgumentParser
import json
import sys

logger.remove()  # Remove default handler
logger.add(sys.stderr, level="ERROR")  # Only show ERROR and CRITICAL

def _load_yaml(file_path: str) -> dict:
    with open(file_path, "r") as f:
        return yaml.safe_load(f)

def _load_jsonl(file_path: str) -> list:
    with open(file_path, "r") as f:
        return [json.loads(line) for line in f]

def _get_unit_scale_map(unit_group_path: Path) -> dict:
    """
    Returns a dict mapping all aliases (including main unit name) to their numeric scale.
    Only units with a "scale" field are included.
    """
    config = _load_yaml(unit_group_path)
    scale_map = {}
    for unit_key, unit_block in config["units"].items():
        scale = unit_block.get("scale")
        if scale is not None:
            all_aliases = [unit_key] + unit_block.get("aliases", [])
            for alias in all_aliases:
                scale_map[alias] = float(scale)
    return scale_map

def _get_unscaled_aliases_by_type(unit_group_path: Path) -> list:
    """
    Returns a dict with two keys: 'postfix' and 'special_unit'.
    Each contains a list of aliases of units that don't have a 'scale' field,
    categorized by whether their description contains 'postfix'.
    """
    config = _load_yaml(unit_group_path)
    # postfix_aliases = set()
    special_unit_aliases = set()
    for unit_key, unit_block in config["units"].items():
        if "scale" not in unit_block:
            desc = unit_block.get("description", "").lower()
            aliases = [unit_key] + unit_block.get("aliases", [])

            if 'currency' in desc:
                continue

            # if "postfix" in desc:
            #     postfix_aliases.update(a for a in aliases)
            # else:
            special_unit_aliases.update(a for a in aliases)
    return  sorted(special_unit_aliases)


def word_to_number(match: re.Match) -> str:
    word = match.group(1)
    logger.info(f"Match word num: {word}")
    return str(WORD_NUM_MAP[word])

def detect_scale(unit_part, scale_map, postfix_list):
    key = unit_part.lower().strip()
    # No Unit, very precise
    if len(key) == 0:
        return 1, None, None
    
    scale = scale_map.get(key)
    if scale is not None:
        return scale, key, None

    for pf in sorted(postfix_list, key=len, reverse=True):
        pf = pf.lower().strip()
        if key == pf:
            return 1, None, pf
        elif key.endswith(" " + pf):
            trimmed = key[:-(len(pf) + 1)].rstrip()
            scale = scale_map.get(trimmed)
            if scale is not None:
                return scale, trimmed, pf

    if key in postfix_list:
        return 1, None, key

    return None, None, None

def parse_val_and_resolution(text: str) -> Tuple[float, float]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty input")

    # 0. Remove ',' 
    s = text.replace(",", "").strip()
    neg = False
    # 0. Remove Symbol
    s = re.sub(_currency, "", s)

    # 1. Recognize negative number with (num) or -num
    paren_pat = re.compile(r"\(\s*([-+]?\d*\.?\d+(?:e[-+]?\d+)?)\s*\)")
    paren_match = paren_pat.search(s)
    if paren_match:
        neg = True
        s = s[:paren_match.start()] + paren_match.group(1) + s[paren_match.end():]
    if s.startswith("-"):
        neg, s = True, s[1:]

    # 2. extract number
    s_no_words = WORD_NUM_RE.sub(word_to_number, s)

    m = re.search(r"[-+]?\d*\.?\d+(?:e[-+]?\d+)?", s_no_words)
    if not m:
        logger.error(f"No numeric part in {text}")
        return None, None

    num_str = m.group()
    number = float(num_str)
    # decimal zero
    decimals = len((num_str.split(".", 1)[1]).rstrip("0")) if "." in num_str else 0
    # non-decimal zero
    trailing_zeros = 0 if "." in num_str else len(num_str) - len(num_str.rstrip("0") or "0")

    # detect unit
    unit_part = s_no_words[m.end():].strip()
    # scale = SCALE_MAP.get(unit_part, None)
    scale, scale_map_key, postfix = detect_scale(unit_part, SCALE_MAP, POSTFIX_UNIT_SET)
    if scale is None:
        logger.error(f"Parse Unit Failed!! Unit is '{unit_part}'")
        return None, None

    val = number * scale
    res = scale * (10 ** trailing_zeros) * (10 ** -decimals)

    if neg:
        val = -val
    # TODO: if needed conpare 'postfix' in GT, return here postfix
    return val, res

# compare number
def compare_numbers(pred_text: str, gt_text: str,
                    resolution_factor: float = 0.5,
                    rel_tol: float = 0.02) -> bool:
    # 0. Try Exact Match
    if pred_text is None or gt_text is None:
        logger.error(f"INVALID INPUT FOR compare_numbers")
        return False

    if not isinstance(pred_text, str):
        pred_text = str(pred_text)
    if not isinstance(gt_text, str):
        gt_text = str(gt_text)

    if pred_text.strip().lower() == gt_text.strip().lower():
        return True
    
    # 1. If not EM, go for resolution parse
    pred_val, pred_res   = parse_val_and_resolution(pred_text)
    gt_val,  gt_res      = parse_val_and_resolution(gt_text)

    # If Parse failed, means LLM response distract from instruction, should be considered as False
    if pred_val is None or gt_val is None:
        logger.error(f"Value Parse Failed!! Prediction {pred_text}, gt {gt_text}")
        return False
    
    if pred_val < 0:
        logger.warning(f"Skip Negative Predictions!! Prediction {pred_text}, gt {gt_text}")
        return None

    res = pred_res if pred_res > gt_res else gt_res
    logger.info(f"chosen resolution {res} is used")

    if gt_val < 0:
        abs_diff = abs(abs(pred_val) - abs(gt_val))
        rel_diff = abs_diff / (abs(gt_val) if gt_val else 1)
    else:
        abs_diff = abs(pred_val - gt_val)
        rel_diff = abs_diff / (abs(gt_val) if gt_val else 1)

    return (abs_diff <= resolution_factor * res) or (rel_diff <= rel_tol)

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--dataset_path", default="data/pilot_prompt.jsonl", type=str)
    parser.add_argument("--prediction_path", default="data/pilot_prediction_gemini.jsonl", type=str)
    parser.add_argument("--unit_group_path", default="src/unit_groups.yaml", type=str)
    args = parser.parse_args()

    SCALE_MAP = _get_unit_scale_map(Path(args.unit_group_path))
    POSTFIX_UNIT_SET = _get_unscaled_aliases_by_type(Path(args.unit_group_path))
    WORD_NUM_MAP = {
        "zero": 0, "one": 1, "two": 2, "three": 3,  "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
        "ten": 10, "eleven": 11, "twelve": 12,  "thirteen": 13,
        "fourteen": 14, "fifteen": 15, "sixteen": 16,
        "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    }
    WORD_NUM_RE = re.compile(r"\b(" + "|".join(WORD_NUM_MAP.keys()) + r")\b")

    _currency = r"[$€£¥]"
    dataset = _load_jsonl(Path(args.dataset_path))
    predictions = _load_jsonl(Path(args.prediction_path))
    # print(predictions[0])
    if len(predictions) != len(dataset):
        logger.error(f"Number of predictions {len(predictions)} does not match number of dataset samples {len(dataset)}")
        exit(1)
    
    predictions_dict = {prediction['uid']: prediction['answer'] for prediction in predictions}
    correct_count = 0
    total_count = 0

    for sample in dataset:
        prompt = sample['user_prompt']
        ground_truth = sample['ground_truth']
        prediction = predictions_dict[sample['uid']]
        is_correct = compare_numbers(prediction, ground_truth)
        if is_correct:
            correct_count += 1
        total_count += 1

    print(f"Accuracy: {correct_count / total_count}")
    print(f"Total count: {total_count}")
    print(f"Correct count: {correct_count}")
    print(f"Incorrect count: {total_count - correct_count}")