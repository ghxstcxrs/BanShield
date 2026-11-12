"""Parse reported email headers offline; no DKIM or identity verification."""
from email.parser import BytesParser
from email import policy
from email.utils import parsedate_to_datetime
from datetime import timezone

def parsed_clock(raw):
    try:
        dt=parsedate_to_datetime(raw)
        return {'raw':raw,'utc':dt.astimezone(timezone.utc).isoformat() if dt and dt.tzinfo else None,'status':'reported, unverified' if dt and dt.tzinfo else 'missing time zone; not comparable'}
    except Exception:return {'raw':raw,'utc':None,'status':'unparseable'}

def parse_email(raw,headers_only=False):
    if len(raw)>100*1024*1024:raise ValueError('Email exceeds 100 MB.')
    msg=BytesParser(policy=policy.default).parsebytes(raw,headersonly=True)
    if not msg.keys():raise ValueError('No recognizable email headers found.')
    clocks=[]
    for i,value in enumerate(msg.get_all('Date',[]),1):clocks.append({'source':f'Date header {i}',**parsed_clock(str(value))})
    received=[]
    for i,value in enumerate(msg.get_all('Received',[]),1):
        text=str(value);clock=parsed_clock(text.rsplit(';',1)[-1].strip()) if ';' in text else {'raw':text,'utc':None,'status':'no timestamp delimiter'}
        received.append({'hop_in_file_order':i,'header':text,'timestamp':clock})
        clocks.append({'source':f'Received hop {i} (file order)',**clock})
    return {'kind':'SMTP headers' if headers_only else 'EML','requests':[],'headers_only':headers_only,'headers':[{'name':k,'value':str(v)} for k,v in msg.raw_items()], 'timestamps':clocks,'received_chain':received,'dkim_signature_present':bool(msg.get_all('DKIM-Signature')),'dkim_verification':'NOT PERFORMED','authentication_results_reported':[str(v) for v in msg.get_all('Authentication-Results',[])],'note':'Date is an author-reported origination time, not proof of transport time. Received headers report individual hops and can be forged outside a trusted boundary. DKIM presence or reported Authentication-Results is not verification. No timestamp or short interval proves automation or absence of human review. Original bytes preserved; headers-only text is a user-supplied derivative.'}
