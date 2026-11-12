"""Deterministic rubric scores; not calibrated probabilities or legal conclusions."""
import re,json
BANDS={'direct_contradiction':90,'procedural_failure':70,'discretionary_gray_area':40,'weak_or_unsupported':0}
def normalized(text):return ' '.join(str(text).split())
def values(obj):
    if isinstance(obj,dict):return ' '.join(values(v) for v in obj.values())
    if isinstance(obj,list):return ' '.join(values(v) for v in obj)
    return str(obj)
def apply_rubric(findings,policy,manifest):
    sources={m[1]:m[2] for m in re.finditer(r'^## \[([^\]]+)\][^\n]*\n(.*?)(?=^## \[|\Z)',policy,re.M|re.S)}
    evidence={}
    for e in manifest['entries']:
        evidence[e['id']]=values({k:v for k,v in e.items() if k not in ('screenshots','network_evidence')})
        for item in e['screenshots']+e['network_evidence']:evidence[item['evidence_id']]=values(item)
        for a in e['addenda']:evidence[a['id']]=values(a)
    for f in findings['findings']:
        requested=f['rubric_band'];band=requested;reasons=[]
        excerpt=normalized(f['evidence_excerpt'])
        evidence_supported=len(excerpt)>=20 and any(excerpt in normalized(evidence.get(eid,'')) for eid in f['evidence_ids'])
        quote=normalized(f['policy_excerpt'])
        policy_supported=len(quote)>=20 and any(quote in normalized(sources.get(sid,'')) for sid in f['policy_source_ids'])
        if band!='weak_or_unsupported' and not evidence_supported:band='weak_or_unsupported';reasons.append('Evidence excerpt missing or not found in cited evidence.')
        if band in ('direct_contradiction','procedural_failure','discretionary_gray_area') and not policy_supported:band='weak_or_unsupported';reasons.append('Policy excerpt missing or not found in cited policy section.')
        f['requested_rubric_band']=requested;f['rubric_band']=band;f['rubric_score']=BANDS[band];f['score_adjustments']=reasons;f['included_in_report']=f['rubric_score']>=40
    return {'version':1,'score_type':'deterministic evidence-review rubric, not probability','band_scores':BANDS,'report_minimum_score':40,'filtered_out_count':sum(not f['included_in_report'] for f in findings['findings']),'limitations':'Model-selected bands require human review. Literal citation checks do not verify authenticity, applicability, completeness, or whether a true contradiction exists.'}
