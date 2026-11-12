"""Saved-byte hashes and non-recursive report provenance records."""
import json,hashlib,os,sqlite3
from pathlib import Path
from datetime import datetime,timezone

def atomic_bytes(path,content):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.tmp')
    with temp.open('wb') as out:out.write(content);out.flush();os.fsync(out.fileno())
    os.replace(temp,path)
def finalize_report(folder,result,policy=None,manifest=None,data_dir=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    policy_bytes=policy.encode('utf-8') if policy is not None else None
    input_bytes=json.dumps(manifest,ensure_ascii=False).encode('utf-8') if manifest is not None else None
    if policy_bytes is not None and hashlib.sha256(policy_bytes).hexdigest()!=result['policy_sha256']:raise ValueError('Policy text no longer matches the analysis input. Report provenance was not recorded.')
    if input_bytes is not None and hashlib.sha256(input_bytes).hexdigest()!=result['manifest_sha256']:raise ValueError('Manifest no longer matches the analysis input. Report provenance was not recorded.')
    report=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')
    atomic_bytes(folder/'audit_report.json',report)
    atomic_bytes(folder/'findings.json',report) # Compatibility alias, identical saved bytes.
    if policy_bytes is not None:atomic_bytes(folder/'roblox_tos_and_policies.txt',policy_bytes)
    if input_bytes is not None:atomic_bytes(folder/'input_evidence_manifest.json',input_bytes)
    record={'report_id':hashlib.sha256(report).hexdigest(),'report_file':'audit_report.json','report_sha256':hashlib.sha256((folder/'audit_report.json').read_bytes()).hexdigest(),'generated_at':result['generated_at'],'recorded_at':datetime.now(timezone.utc).isoformat(),'provider':result.get('provider','openai'),'model':result['model'],'resolved_model':result.get('resolved_model'),'response_id':result.get('response_id'),'policy_file':'roblox_tos_and_policies.txt','policy_sha256':result['policy_sha256'],'input_manifest_file':'input_evidence_manifest.json','input_manifest_sha256':result['manifest_sha256'],'hash_algorithm':'SHA-256','input_manifest_serialization':'UTF-8 json.dumps(ensure_ascii=False), no indentation or newline; frozen pre-analysis input','timestamp_source':'Local system clock; not a trusted timestamp authority'}
    records=[record]
    if data_dir is not None:
        data=Path(data_dir);report_path=(folder/'audit_report.json').resolve()
        if not report_path.is_relative_to(data.resolve()):raise ValueError('Indexed report must be stored inside the selected log data folder.')
        stored=dict(record);stored['report_file']=report_path.relative_to(data.resolve()).as_posix()
        conn=sqlite3.connect(data/'audit-log.sqlite3')
        try:
            conn.execute('CREATE TABLE IF NOT EXISTS analysis_runs(report_id TEXT PRIMARY KEY,record_json TEXT NOT NULL)')
            with conn:conn.execute('INSERT OR IGNORE INTO analysis_runs VALUES(?,?)',(record['report_id'],json.dumps(stored,ensure_ascii=False)))
            records=[json.loads(r[0]) for r in conn.execute('SELECT record_json FROM analysis_runs ORDER BY rowid')]
        finally:conn.close()
    if manifest is not None:
        linked=json.loads(json.dumps(manifest));linked['analysis_records']=records
        encoded=json.dumps(linked,ensure_ascii=False,indent=2).encode('utf-8')
        atomic_bytes(folder/'evidence_manifest.json',encoded)
        if data_dir is not None:atomic_bytes(Path(data_dir)/'evidence_manifest.json',encoded)
    atomic_bytes(folder/'report_integrity.json',json.dumps(record,ensure_ascii=False,indent=2).encode('utf-8'))
    return record
