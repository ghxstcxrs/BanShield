"""Read-only cross-check cards from locally indexed, hash-verified API reports."""
import json,hashlib
from pathlib import Path
from analysis_models import ScoredFindings

def load_cross_checks(data_dir,connection,entries):
    data=Path(data_dir).resolve();result={e['id']:[] for e in entries}
    if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='analysis_runs'").fetchone():return result
    owners={}
    for e in entries:
        owners[e['id']]=e['id']
        for value in e['files']+e['network_captures']+e['addenda']:owners[value['id']]=e['id']
    for row in connection.execute('SELECT record_json FROM analysis_runs ORDER BY rowid DESC'):
        try:
            record=json.loads(row[0]);path=(data/record['report_file']).resolve()
            if not path.is_relative_to(data) or not path.is_file():continue
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=record['report_sha256']:continue
            report=json.loads(raw);provider=report.get('provider')
            if provider not in ('gemini','openai'):continue
            parsed=ScoredFindings.model_validate(report['findings']).model_dump()
            for finding in parsed['findings']:
                if not finding['included_in_report']:continue
                for eid in {owners[x] for x in finding['evidence_ids'] if x in owners}:
                    result[eid].append({'provider':provider,'model':report['model'],'generated_at':report['generated_at'],'report_id':record['report_id'],'finding':finding})
        except (OSError,ValueError,KeyError,TypeError):continue
    return result
