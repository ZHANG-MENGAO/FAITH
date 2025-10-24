from argparse import ArgumentParser

import yaml
from typing import List, Dict, Any
from pathlib import Path
import json

def _load_yaml_file(file_path: str) -> dict:
    with open(file_path, "r") as f:
        return yaml.safe_load(f)

def _load_json(file_path: str) -> dict:
    with open(file_path, "r") as f:
        return json.load(f)

def _write_jsonl(file_path: str, data: list):
    with open(file_path, "w") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")

def _formulate_table(table: dict, table_format: str) -> str:
    if not table or not table.get('cells'):
        return ""
    
    table_str = f"### Table {table['table_index']}:\n"
    if table.get('pre_text'):
        table_str += table['pre_text'] + "\n"
    
    cells = table['cells']
    
    if table_format == "csv":
        # Render as CSV (comma separated, quoting as needed)
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        for row in cells:
            writer.writerow(row)
        table_str += output.getvalue().strip()
    elif table_format == "markdown":
        from tabulate import tabulate
        table_str += tabulate(cells[1:], headers=cells[0], tablefmt="github")
    else:
        raise ValueError(f"Invalid table format: {table_format}")
    
    return table_str

def formulate_prompt_prediction(dataset:List[Dict[str, Any]], prompt_template: dict, unit_groups: dict, table_format: str):
    samples = []
    # Prepare custom units
    unit_groups = unit_groups['units']
    percentage_symbols = unit_groups.get('percent', {}).get('aliases', [])
    bps_symbols = unit_groups.get('bps', {}).get('aliases', [])
    
    # Build final prompt with custom unit description
    for report in dataset:
        report_id = report['metadata']['cik']
        filing_date = report['metadata']['filing_date']

        # table string are reused for all instances in the report
        tables = {}
        for table in report['tables']:
            formated_table = _formulate_table(table, table_format)
            tables[table['table_index']] = formated_table
        tables = sorted(tables.items(), key=lambda x: int(x[0]))
        table_str = "\n\n".join([table_content for _, table_content in tables])

        for instance in report['instances']:
            if any(symbol in instance['ground_truth'] for symbol in percentage_symbols):
                unit_description = "in percentage format."
            elif any(symbol in instance['ground_truth'] for symbol in bps_symbols):
                unit_description = "in basis points (bps) format."
            else:
                unit_description = "which is neither a percentage nor a basis points (bps)."

            input_params = {
                'unit_description': unit_description,
                'pre_sentence': instance['pre_sentence'],
                'masked_sentence': instance['masked_sentence'],
                'post_sentence': instance['post_sentence'],
                'tables_with_pretext': table_str,
            }
            prompt = prompt_template['user_prompt_prediction'].format(**input_params)
            sample = {
                'uid': instance['uid'],
                'cik': report_id,
                'filing_date': filing_date,
                'system_prompt': prompt_template['system_prompt'],
                'user_prompt': prompt,
                'ground_truth': instance['ground_truth']
            }
            samples.append(sample)
    
    return samples

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--dataset_path", default="data/main.json", type=str)
    parser.add_argument("--prompt_template_path", default="src/prompt.yaml", type=str)
    parser.add_argument("--unit_group_path", default="src/unit_groups.yaml", type=str)
    parser.add_argument("--table_format", default="csv", type=str, choices=["csv", "markdown"])
    parser.add_argument("--output_path", default="data/main_prompt.jsonl", type=str)
    args = parser.parse_args()

    prompt_template = _load_yaml_file(Path(args.prompt_template_path))
    unit_groups = _load_yaml_file(Path(args.unit_group_path))
    dataset = _load_json(Path(args.dataset_path))
    prompt_samples = formulate_prompt_prediction(dataset, prompt_template, unit_groups, args.table_format)
    _write_jsonl(Path(args.output_path), prompt_samples)