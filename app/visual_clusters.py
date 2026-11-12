"""Deterministic 64-bit visual-hash clustering; no image or identity data exported."""
import csv,io,re
from collections import Counter

def hamming(a,b):
    if not re.fullmatch('[0-9a-fA-F]{16}',a or '') or not re.fullmatch('[0-9a-fA-F]{16}',b or ''):raise ValueError('Expected two 64-bit hexadecimal hashes.')
    return (int(a,16)^int(b,16)).bit_count()

def cluster_submissions(entries,threshold=6):
    if not isinstance(threshold,int) or not 0<=threshold<=64:raise ValueError('Threshold must be 0–64 bits.')
    items=[]
    for ei,e in enumerate(entries,1):
        for fi,f in enumerate(e['files'],1):
            valid=all(re.fullmatch('[0-9a-fA-F]{16}',f.get(k) or '') for k in ('phash','dhash')) and bool(f.get('hash_method'))
            items.append({'event_id':f'event-{ei:04d}','submission_id':f'submission-{len(items)+1:05d}','file_id':f['id'],'file':f,'valid':valid,'p':int(f['phash'],16) if valid else 0,'d':int(f['dhash'],16) if valid else 0})
    parent=list(range(len(items)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,a in enumerate(items):
        if not a['valid']:continue
        for j in range(i):
            b=items[j]
            if b['valid'] and a['file']['hash_method']==b['file']['hash_method'] and (a['p']^b['p']).bit_count()<=threshold and (a['d']^b['d']).bit_count()<=threshold:
                parent[find(i)]=find(j)
    groups={}
    for i,a in enumerate(items):
        if a['valid']:groups.setdefault(find(i),[]).append(i)
    key=lambda i:(items[i]['file']['hash_method'],items[i]['file']['phash'].lower(),items[i]['file']['dhash'].lower(),items[i]['file_id'])
    ordered=sorted(groups.values(),key=lambda indices:min(key(i) for i in indices))
    memberships={i:(f'cluster-{ci:04d}',indices) for ci,indices in enumerate(ordered,1) for i in indices}
    representatives={cid:items[min(indices,key=key)]['file'] for cid,indices in ((f'cluster-{ci:04d}',indices) for ci,indices in enumerate(ordered,1))}
    counts=Counter((a['file']['hash_method'],a['file']['phash'].lower(),a['file']['dhash'].lower()) for a in items if a['valid'])
    exact_duplicates=sum(n-1 for n in counts.values());hashable=sum(a['valid'] for a in items)
    sha=Counter(a['file'].get('sha256') for a in items if a['file'].get('sha256'))
    rows=[]
    for i,a in enumerate(items):
        row={k:a[k] for k in ('event_id','submission_id')}
        if a['valid']:
            cid,indices=memberships[i];representative=representatives[cid];f=a['file']
            row.update(cluster_id=cid,cluster_size=len(indices),hash_status='available',phash_distance_to_representative=hamming(f['phash'],representative['phash']),dhash_distance_to_representative=hamming(f['dhash'],representative['dhash']),exact_pattern_group_size=counts[(f['hash_method'],f['phash'].lower(),f['dhash'].lower())])
        else:row.update(cluster_id='',cluster_size=0,hash_status='missing_or_incompatible',phash_distance_to_representative='',dhash_distance_to_representative='',exact_pattern_group_size=0)
        rows.append(row)
    summary={'total_entries':len(entries),'total_submissions':len(items),'hashable_submissions':hashable,'unclustered_submissions':len(items)-hashable,'unique_visual_clusters':len(ordered),'exact_pattern_duplicate_submissions':exact_duplicates,'exact_pattern_match_rate':exact_duplicates/hashable if hashable else None,'exact_byte_duplicate_submissions':sum(n-1 for n in sha.values()),'hamming_threshold_each_hash':threshold,'matching_rule':'Both pHash and dHash distance <= threshold, identical hash method; connected components (transitive).','exact_pattern_definition':'Repeated identical pHash AND dHash pairs beyond the first, divided by hashable submissions. Hash equality does not prove identical pixels or bytes.','cluster_id_scope':'Deterministic within this dataset; IDs may change when dataset membership changes. One submission means one current attachment; retired attachments excluded.'}
    return rows,summary,{a['file_id']:rows[i] for i,a in enumerate(items)}

def csv_text(rows,fields=None):
    out=io.StringIO(newline='');writer=csv.DictWriter(out,fieldnames=fields or list(rows[0] if rows else ['event_id','submission_id','cluster_id','cluster_size','hash_status','phash_distance_to_representative','dhash_distance_to_representative','exact_pattern_group_size']))
    writer.writeheader();writer.writerows(rows);return out.getvalue()
