"""Manually supplied policy snapshots only. No policy network fetching."""
import re,os
from pathlib import Path
from datetime import date
from urllib.parse import urlparse
REQUIRED=('terms','standards','appeals','moderation','support')
def validate_policy(text):
    sections={m.group(1):m.group(2) for m in re.finditer(r'^## \[([^\]]+)\][^\n]*\n(.*?)(?=^## \[|\Z)',text,re.M|re.S)}
    if any(len(re.findall(r'^## \['+sid+r'\]',text,re.M))!=1 for sid in REQUIRED):raise ValueError('Include each section once: ## [terms], ## [standards], ## [appeals], ## [moderation], ## [support].')
    for sid in REQUIRED:
        section=sections[sid]
        def field(name):
            m=re.search(r'^'+name+r':\s*(.+)$',section,re.M)
            if not m:raise ValueError(f'[{sid}] requires {name}: on its own line.')
            return m.group(1).strip()
        source=field('Source');url=urlparse(source)
        if url.scheme!='https' or url.hostname not in ('en.help.roblox.com','about.roblox.com','www.roblox.com','roblox.com') or url.username or url.password:raise ValueError(f'[{sid}] Source must be an official Roblox HTTPS URL.')
        try:date.fromisoformat(field('Retrieved'))
        except ValueError:raise ValueError(f'[{sid}] Retrieved must be YYYY-MM-DD.')
        effective=field('Effective')
        if effective.lower()!='unknown':
            try:date.fromisoformat(effective)
            except ValueError:raise ValueError(f'[{sid}] Effective must be YYYY-MM-DD or unknown.')
        body=re.split(r'^Content:\s*$',section,maxsplit=1,flags=re.M)
        if len(body)!=2 or len(body[1].strip())<80 or '[PASTE' in body[1].upper():raise ValueError(f'[{sid}] Paste the official policy text after Content:; template placeholders are not a policy.')
    return text

def policy_path(root):return Path(root)/'policies'/'roblox_tos_and_policies.txt'
def read_policy(root):
    path=policy_path(root)
    if not path.is_file():raise ValueError('Manually save your sourced policy as '+str(path)+'. Copy the provided template, fill all five sections, then reload. PDF, HTML and DOCX are not accepted here.')
    if path.stat().st_size>4*1024*1024:raise ValueError('Policy file exceeds 4 MB.')
    return validate_policy(path.read_text(encoding='utf-8-sig'))
def import_policy(root,source):
    source=Path(source)
    if source.suffix.lower()!='.txt':raise ValueError('Use a UTF-8 .txt policy file based on the provided template.')
    if source.stat().st_size>4*1024*1024:raise ValueError('Policy file exceeds 4 MB.')
    text=validate_policy(source.read_text(encoding='utf-8-sig'));dest=policy_path(root);dest.parent.mkdir(exist_ok=True);tmp=dest.with_suffix('.tmp');tmp.write_text(text,encoding='utf-8');os.replace(tmp,dest);return text
