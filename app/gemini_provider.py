"""Gemini REST adapter; text-only, explicit provider selection, no retries."""
import re,json,urllib.request,urllib.error

def request_payload(common):
    return {'systemInstruction':{'parts':[{'text':common['instructions']}]},'contents':[{'role':'user','parts':[{'text':common['input'][0]['content'][0]['text']}]}],'generationConfig':{'responseMimeType':'application/json','responseJsonSchema':common['text']['format']['schema'],'maxOutputTokens':common['max_output_tokens']}}
def normalize_response(response):
    if response.get('promptFeedback',{}).get('blockReason'):raise ValueError('Gemini blocked the prompt; no findings accepted.')
    candidates=response.get('candidates',[])
    if len(candidates)!=1:raise ValueError('Gemini returned no single completed candidate; no findings accepted.')
    candidate=candidates[0]
    if candidate.get('finishReason')!='STOP':raise ValueError('Gemini response was blocked or incomplete; no findings accepted.')
    texts=[]
    for part in candidate.get('content',{}).get('parts',[]):
        if part.get('thought'):continue
        if 'text' in part:texts.append(part['text'])
        elif part:raise ValueError('Unexpected non-text Gemini output; no findings accepted.')
    if not texts:raise ValueError('Gemini returned no findings text.')
    return {'status':'completed','id':response.get('responseId'),'output':[{'content':[{'type':'output_text','text':''.join(texts)}]}],'resolved_model':response.get('modelVersion')}
def generate(common,model,key,transport=None):
    model=model.removeprefix('models/')
    if not re.fullmatch(r'[A-Za-z0-9._-]+',model):raise ValueError('Enter a Gemini model ID, not a URL or path.')
    payload=request_payload(common)
    def send(body):
        req=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models/'+model+':generateContent',data=json.dumps(body).encode(),headers={'x-goog-api-key':key,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=180) as response:return json.load(response)
        except urllib.error.HTTPError as exc:raise RuntimeError(f'Gemini request failed (HTTP {exc.code}); check model access, key, quota and schema support. No retry or fallback was made.') from None
    return normalize_response((transport or send)(payload))
