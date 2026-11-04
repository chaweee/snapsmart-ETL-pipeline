"""Run demo extraction and transformation using the same batch ID."""

import json

from export_supabase import PROJECT_ROOT, export
from run_log import logged_run
from transform import transform


def main():
    batch = {}

    def extraction(run):
        batch['id'] = run.pipeline_run_id
        return export([], run)

    result = logged_run(extraction)
    if result:
        return result
    batch_dir = PROJECT_ROOT / 'output' / 'batches' / batch['id']
    with (batch_dir / 'extracted.json').open(encoding='utf-8') as file:
        snapshot = json.load(file)
    report = transform(snapshot, batch_dir / 'transformed')
    print(f"Batch {batch['id']}: {report['status']}; results: {batch_dir / 'transformed'}")
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
