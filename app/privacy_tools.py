"""Private metadata inspection and allowlisted public exports for BanShield."""
import json, hashlib, os, tempfile, zipfile
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageOps, ExifTags
from video_evidence import is_video
from visual_clusters import cluster_submissions, csv_text

def inspect_metadata(saved_path, source_path=None):
    result={'inspected_at':datetime.now().astimezone().isoformat(timespec='seconds'),'creation_timestamp':None,'creation_source':None,'timezone_status':'unknown','sensitive_fields':[],'metadata_fields':[]}
    with Image.open(saved_path) as im:
        exif=im.getexif()
        tags=dict(exif)
        try:tags.update(exif.get_ifd(34665))
        except (KeyError,TypeError,ValueError):pass
        names=[ExifTags.TAGS.get(k,str(k)) for k in tags]
        info_names=list(im.info)
        result['metadata_fields']=sorted(set(names+info_names))
        sensitive=('gps','serial','owner','artist','author','copyright','comment','description','make','model','software','host','document','xp','xmp','iptc','photoshop')
        result['sensitive_fields']=sorted(n for n in result['metadata_fields'] if any(t in n.lower() for t in sensitive))
        # Preserve raw clock text: an EXIF clock without an offset is not UTC.
        for tag,label,offset_tag in ((36867,'EXIF DateTimeOriginal',36881),(36868,'EXIF DateTimeDigitized',36882),(306,'EXIF DateTime',36880)):
            value=tags.get(tag)
            if value:
                raw=str(value).strip('\x00 ');offset=str(tags.get(offset_tag,'')).strip('\x00 ')
                result.update(creation_timestamp=raw,creation_source=label,timezone_status=('offset '+offset if offset else 'unknown'),embedded_offset=offset or None)
                break
        if not result['creation_timestamp']:
            for key in ('Creation Time','creation_time','date:create'):
                if key in im.info:
                    result.update(creation_timestamp=str(im.info[key]),creation_source='Image metadata '+key);break
    if source_path:
        stat=Path(source_path).stat();birth=getattr(stat,'st_birthtime',None)
        if birth is not None:result['source_filesystem_created_at']=datetime.fromtimestamp(birth).astimezone().isoformat(timespec='seconds')
        result['source_filesystem_modified_at']=datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec='seconds')
    result['timestamp_note']='Embedded clocks are unverified. Filesystem times may reflect copying or downloading, not capture.'
    return result

def encode_clean_png(source,destination):
    with Image.open(source) as im:
        im.seek(0);oriented=ImageOps.exif_transpose(im).convert('RGB')
        # A new pixel buffer carries no EXIF, XMP, text, ICC, or original filename.
        clean=Image.new('RGB',oriented.size);clean.paste(oriented);clean.save(destination,format='PNG')

def public_manifest(entries):
    # Deliberate allowlist: no free text, source filenames, IDs, hashes of private
    # files, revisions, AI notes, metadata values, account names, or local paths.
    rows,summary,_=cluster_submissions(entries)
    return {'submissions':rows,'summary':summary,'format':'banshield-public-dataset','version':1,'entries':[
        {'id':f'event-{i:04d}','event_at':e['event_at'],'event_timezone':e.get('event_timezone'),'time_certainty':e['certainty'],'attachment_count':len(e['files']),'video_count':sum(is_video(f) for f in e['files']),'image_count':sum(not is_video(f) for f in e['files'])}
        for i,e in enumerate(entries,1)],'privacy_note':'Free text and original attachments omitted. Event times may be identifying; review before sharing.'}

def export_public(destination, manifest, reviewed_images):
    dest=Path(destination);fd,stage=tempfile.mkstemp(prefix='.public-export-',suffix='.zip',dir=dest.parent);os.close(fd)
    try:
        with tempfile.TemporaryDirectory() as td:
            public=json.loads(json.dumps(manifest));public['reviewed_images']=[]
            with zipfile.ZipFile(stage,'w',zipfile.ZIP_DEFLATED) as z:
                for i,path in enumerate(reviewed_images,1):
                    name=f'images/reviewed-{i:04d}.png';clean=Path(td)/f'{i}.png';encode_clean_png(path,clean)
                    z.write(clean,name);public['reviewed_images'].append({'path':name,'sha256':hashlib.sha256(clean.read_bytes()).hexdigest()})
                z.writestr('submissions.csv',csv_text(public.get('submissions',[])))
                summary=public.get('summary',{})
                z.writestr('summary.json',json.dumps(summary,indent=2))
                z.writestr('summary.csv',csv_text([summary]) if summary else 'total_submissions,unique_visual_clusters,exact_pattern_match_rate\r\n')
                z.writestr('dataset.json',json.dumps(public,ensure_ascii=False,indent=2))
                z.writestr('README.txt','BanShield public derivative export. Original evidence is not included. Images were decoded and re-encoded as metadata-free PNGs. Visible text, faces, usernames, QR codes and other identifiers require manual redaction before selection. Event times may identify people. This export is not an evidence backup.')
        os.replace(stage,dest)
    finally:Path(stage).unlink(missing_ok=True)
