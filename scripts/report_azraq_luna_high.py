"""Build the FS-03 comparative report from completed per-condition artifacts."""

import json
from pathlib import Path

from triage_sql.experiment_inputs import pair_luna_low_baseline, verify_frozen_inputs
from triage_sql.failure_experiment import ARTIFACT_NAMES, CONDITIONS, OUTPUT_DIR
from triage_sql.failure_report import build_failure_report


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    verify_frozen_inputs(ROOT)
    output_dir = ROOT / OUTPUT_DIR
    checkpoint = json.loads((output_dir / "checkpoint.json").read_text(encoding="utf-8"))
    if checkpoint.get("status") != "completed":
        raise SystemExit("FS-03 report requires a completed experiment checkpoint")
    evaluation_dir = ROOT / "data/evaluation"
    cohort = [json.loads(line) for line in (evaluation_dir / "azraq-retrieval-failure-labels.jsonl").read_text().splitlines() if line.strip()]
    baseline = json.loads((evaluation_dir / "azraq-sql-prompt-results.json").read_text())
    paired = pair_luna_low_baseline(cohort, baseline)
    artifacts = {
        condition: json.loads((output_dir / ARTIFACT_NAMES[condition]).read_text(encoding="utf-8"))
        for condition in CONDITIONS
    }
    report = build_failure_report(cohort, paired, artifacts)
    report_path = output_dir / "comparison-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(report_path.relative_to(ROOT)), "conditions": report["conditions"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
