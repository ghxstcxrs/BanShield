"""Offline import of private HAR captures and raw JSON response bodies."""
import json,base64

def parse_capture(raw):
    if len(raw)>100*1024*1024:raise ValueError('Capture exceeds 100 MB. Export a narrower request selection.')
    data=json.loads(raw.decode('utf-8-sig'))
    if isinstance(data,dict) and 'log' in data:
        log=data['log']
        if not isinstance(log,dict) or not isinstance(log.get('entries'),list):raise ValueError('Invalid HAR log.entries.')
        entries=log['entries']
        if len(entries)>50000:raise ValueError('Capture has more than 50,000 requests. Narrow the capture.')
        requests=[]
        for e in entries:
            if not isinstance(e,dict):raise ValueError('Invalid HAR request entry.')
            req=e.get('request') or {};response=e.get('response') or {};content=response.get('content') or {}
            headers=response.get('headers') or []
            body=content.get('text');state='not included in HAR'
            if body is not None:
                if content.get('encoding')=='base64':
                    try:body=base64.b64decode(body,validate=True).decode('utf-8',errors='replace');state='decoded base64 as UTF-8 (replacement for invalid bytes)'
                    except Exception:body='[Could not decode base64; original bytes retained in capture]';state='decode failed'
                else:body=str(body);state='included'
            requests.append({'started_at':e.get('startedDateTime'),'method':req.get('method'),'url':req.get('url'),'status':response.get('status'),'status_text':response.get('statusText'),'server_date':next((h.get('value') for h in headers if str(h.get('name','')).lower()=='date'),None),'response_headers':headers,'body':body,'body_state':state,'mime_type':content.get('mimeType'),'duration_ms':e.get('time')})
        return {'kind':'HAR','requests':requests,'note':'Request start times come from the capturing client. Server Date headers are separate, unverified server-provided times. Status 0 is not an HTTP success code. Bodies may be absent or sanitized by the browser.'}
    return {'kind':'JSON','requests':[{'status':None,'server_date':None,'started_at':None,'method':None,'url':None,'body':json.dumps(data,ensure_ascii=False,indent=2),'body_state':'raw JSON payload; transport context unavailable'}],'note':'Raw JSON alone does not contain verified HTTP status, response headers or capture time. These are recorded as unknown rather than inferred from body fields.'}
