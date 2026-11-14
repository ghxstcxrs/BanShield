from __future__ import annotations
import sys, os, json, sqlite3, hashlib, shutil, uuid, zipfile, tempfile
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageOps
import imagehash
from network_evidence import parse_capture
from email_evidence import parse_email
from screenshot_input import ScreenshotDropList,local_paths
from event_timezones import parse_wall,resolve_wall,zone,fixed_zone,available_timezones,detect_local_zone
from visual_clusters import cluster_submissions
from privacy_tools import inspect_metadata, public_manifest, export_public
from PySide6.QtCore import Qt, QDateTime, QDate, QTime, QUrl, QTimeZone
from PySide6.QtGui import QPixmap, QDesktopServices, QFontDatabase, QFont, QShortcut, QKeySequence
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QScrollArea, QFrame, QDialog, QFormLayout, QTextEdit, QDateTimeEdit, QFileDialog, QMessageBox, QListWidget, QDialogButtonBox, QSizePolicy, QTabWidget, QInputDialog, QCheckBox, QProgressDialog)

ROOT = Path(__file__).resolve().parent.parent

def now(): return datetime.now().astimezone().isoformat(timespec='seconds')
def display_time(value):
    if not value: return 'Unknown'
    try: return datetime.fromisoformat(value).astimezone().strftime('%b %d, %Y | %I:%M:%S %p %Z')
    except ValueError: return value

def perceptual_hashes(path):
    # Hash the saved viewing image, without rewriting the original bytes.
    with Image.open(path) as source:
        source.seek(0)
        image=ImageOps.exif_transpose(source).convert('RGB')
        return (str(imagehash.phash(image,hash_size=8,highfreq_factor=4)),
                str(imagehash.dhash(image,hash_size=8)),
                'ImageHash '+imagehash.__version__+'; Pillow '+Image.__version__+'; pHash 64-bit highfreq_factor=4; dHash horizontal 64-bit; EXIF transpose; RGB; first frame',now())

def plain(text='', style=''):
    w = QLabel(text); w.setTextFormat(Qt.TextFormat.PlainText)
    w.setWordWrap(True); w.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    if style: w.setStyleSheet(style)
    return w

def button(text, callback, secondary=False):
    w=QPushButton(text); w.setCursor(Qt.CursorShape.PointingHandCursor)
    if secondary: w.setProperty('secondary', True)
    w.clicked.connect(callback); return w

class Store:
    def __init__(self, root):
        self.root=Path(root); self.data=self.root/'data'; self.attachments=self.data/'attachments'
        self.attachments.mkdir(parents=True, exist_ok=True)
        self.db=sqlite3.connect(self.data/'audit-log.sqlite3')
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS entries(id TEXT PRIMARY KEY,title TEXT NOT NULL,event_at TEXT,certainty TEXT NOT NULL,recorded_at TEXT NOT NULL,source TEXT NOT NULL,facts TEXT NOT NULL,notes TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY,entry_id TEXT NOT NULL REFERENCES entries(id),name TEXT NOT NULL,path TEXT NOT NULL,sha256 TEXT NOT NULL,added_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS network_captures(id TEXT PRIMARY KEY,entry_id TEXT NOT NULL REFERENCES entries(id),name TEXT NOT NULL,path TEXT NOT NULL,sha256 TEXT NOT NULL,imported_at TEXT NOT NULL,summary_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS attachment_processing(id TEXT PRIMARY KEY,file_id TEXT NOT NULL REFERENCES files(id),processed_at TEXT NOT NULL,status TEXT NOT NULL,details TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY,entry_id TEXT NOT NULL REFERENCES entries(id),edited_at TEXT NOT NULL,before_json TEXT NOT NULL,after_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS addenda(id TEXT PRIMARY KEY,entry_id TEXT NOT NULL REFERENCES entries(id),text TEXT NOT NULL,recorded_at TEXT NOT NULL);
        ''');
        if 'active' not in {r[1] for r in self.db.execute('PRAGMA table_info(files)')}:
            self.db.execute('ALTER TABLE files ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
        if 'ai_notes' not in {r[1] for r in self.db.execute('PRAGMA table_info(entries)')}:
            self.db.execute("ALTER TABLE entries ADD COLUMN ai_notes TEXT NOT NULL DEFAULT '{}'")
        for column in ('phash','dhash','hash_method','hash_computed_at','metadata_json'):
            if column not in {r[1] for r in self.db.execute('PRAGMA table_info(files)')}:
                self.db.execute(f'ALTER TABLE files ADD COLUMN {column} TEXT')
        if 'event_timezone' not in {r[1] for r in self.db.execute('PRAGMA table_info(entries)')}:
            self.db.execute('ALTER TABLE entries ADD COLUMN event_timezone TEXT')
        self.db.commit()
    def add(self, title, event_at, certainty, source, facts, notes, paths, ai_notes=None, event_timezone=None):
        eid='ENT-'+uuid.uuid4().hex[:12].upper(); timestamp=now(); copied=[]
        try:
            records=[]
            for path in paths:
                original=Path(path)
                if not original.is_file(): raise ValueError(f'Attachment not found: {original.name}')
                fid=uuid.uuid4().hex; filename=fid+original.suffix.lower()
                dest=self.attachments/filename
                with original.open('rb') as src, dest.open('xb') as target:
                    copied.append(dest); digest=hashlib.sha256()
                    while block:=src.read(1024*1024): target.write(block); digest.update(block)
                records.append((fid,eid,original.name,'attachments/'+filename,digest.hexdigest(),timestamp,*perceptual_hashes(dest),json.dumps(inspect_metadata(dest,original),ensure_ascii=False)))
            with self.db:
                self.db.execute('INSERT INTO entries(id,title,event_at,certainty,recorded_at,source,facts,notes) VALUES(?,?,?,?,?,?,?,?)',(eid,title,event_at,certainty,timestamp,source,facts,notes))
                self.db.execute('UPDATE entries SET ai_notes=?,event_timezone=? WHERE id=?',(json.dumps(ai_notes or {},ensure_ascii=False),event_timezone,eid))
                self.db.executemany('INSERT INTO files(id,entry_id,name,path,sha256,added_at,phash,dhash,hash_method,hash_computed_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)',records)
            return eid
        except Exception:
            for dest in copied: dest.unlink(missing_ok=True)
            raise
    def list(self, query='', descending=True):
        order='DESC' if descending else 'ASC'
        rows=self.db.execute(f'''SELECT * FROM entries ORDER BY COALESCE(event_at,recorded_at) {order}''').fetchall()
        result=[]
        for row in rows:
            e=dict(row); e['network_captures']=[dict(r) for r in self.db.execute('SELECT * FROM network_captures WHERE entry_id=? ORDER BY imported_at,rowid',(e['id'],))]; e['ai_notes']=json.loads(e['ai_notes']); e['files']=[dict(r) for r in self.db.execute('SELECT * FROM files WHERE entry_id=? AND active=1 ORDER BY added_at,id',(e['id'],))]
            e['addenda']=[dict(r) for r in self.db.execute('SELECT * FROM addenda WHERE entry_id=? ORDER BY recorded_at,rowid',(e['id'],))]
            e['revisions']=[dict(r) for r in self.db.execute('SELECT * FROM revisions WHERE entry_id=? ORDER BY edited_at,rowid',(e['id'],))]
            searchable=' '.join(str(v) for v in row)+' '+ ' '.join(f['name'] for f in e['files'])+' '+ ' '.join(a['text'] for a in e['addenda'])+' '+ ' '.join(r['before_json']+' '+r['after_json'] for r in e['revisions'])
            if query.casefold() in searchable.casefold(): result.append(e)
        return result
    @staticmethod
    def snapshot(entry):
        result={k:entry[k] for k in ('title','event_at','certainty','source','facts','notes')}
        result['event_timezone']=entry.get('event_timezone')
        result['ai_notes']=entry.get('ai_notes',{})
        result['screenshots']=[{k:f[k] for k in ('id','name','path','sha256')} for f in entry['files']]
        return result
    def edit(self, eid, title, event_at, certainty, source, facts, notes, paths, keep_ids, expected=None, ai_notes=None, event_timezone=None):
        if not title.strip() or not facts.strip(): raise ValueError('A title and factual description are required.')
        copied=[]
        try:
            # Lock before reading so the snapshot and update form one transaction.
            self.db.execute('BEGIN IMMEDIATE')
            current=next((e for e in self.list() if e['id']==eid),None)
            if current is None: raise ValueError('Entry no longer exists.')
            before=self.snapshot(current)
            if expected is not None and before!=expected: raise ValueError('This entry changed while you were editing. Close and reopen the editor to use the latest version.')
            active={f['id'] for f in current['files']}
            if not set(keep_ids)<=active: raise ValueError('An attachment is no longer current. Reopen the editor.')
            timestamp=now(); records=[]
            for path in paths:
                original=Path(path);fid=uuid.uuid4().hex;rel='attachments/'+fid+original.suffix.lower();dest=self.data/rel
                with original.open('rb') as src,dest.open('xb') as target:
                    copied.append(dest);digest=hashlib.sha256()
                    while block:=src.read(1024*1024):target.write(block);digest.update(block)
                records.append((fid,eid,original.name,rel,digest.hexdigest(),timestamp,*perceptual_hashes(dest),json.dumps(inspect_metadata(dest,original),ensure_ascii=False)))
            after={'title':title,'event_at':event_at,'certainty':certainty,'source':source,'facts':facts,'notes':notes,
                   'screenshots':[{k:f[k] for k in ('id','name','path','sha256')} for f in current['files'] if f['id'] in keep_ids]}
            after['event_timezone']=current.get('event_timezone') if event_timezone is None else event_timezone
            after['ai_notes']=current['ai_notes'] if ai_notes is None else ai_notes
            after['screenshots'] += [dict(zip(('id','name','path','sha256'),(r[0],r[2],r[3],r[4]))) for r in records]
            if before==after:
                self.db.rollback();return False
            self.db.execute('UPDATE entries SET title=?,event_at=?,certainty=?,source=?,facts=?,notes=? WHERE id=?',(title,event_at,certainty,source,facts,notes,eid))
            self.db.execute('UPDATE entries SET ai_notes=?,event_timezone=? WHERE id=?',(json.dumps(after['ai_notes'],ensure_ascii=False),after['event_timezone'],eid))
            for fid in active-set(keep_ids):self.db.execute('UPDATE files SET active=0 WHERE id=?',(fid,))
            self.db.executemany('INSERT INTO files(id,entry_id,name,path,sha256,added_at,phash,dhash,hash_method,hash_computed_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)',records)
            self.db.execute('INSERT INTO revisions VALUES(?,?,?,?,?)',(uuid.uuid4().hex,eid,timestamp,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False)))
            self.db.commit();return True
        except Exception:
            self.db.rollback()
            for path in copied:path.unlink(missing_ok=True)
            raise
    def amend(self, eid, text):
        with self.db: self.db.execute('INSERT INTO addenda VALUES(?,?,?,?)',(uuid.uuid4().hex,eid,text,now()))
    def attach_network(self,eid,filename):
        original=Path(filename)
        if original.stat().st_size>100*1024*1024:raise ValueError('Capture exceeds 100 MB.')
        raw=original.read_bytes();summary=parse_capture(raw)
        folder=self.data/'network';folder.mkdir(exist_ok=True)
        cid=uuid.uuid4().hex;rel='network/'+cid+('.har' if summary['kind']=='HAR' else '.json');dest=self.data/rel
        try:
            dest.write_bytes(raw)
            with self.db:
                self.db.execute('INSERT INTO network_captures VALUES(?,?,?,?,?,?,?)',(cid,eid,original.name,rel,hashlib.sha256(raw).hexdigest(),now(),json.dumps(summary,ensure_ascii=False)))
            return summary
        except Exception:dest.unlink(missing_ok=True);raise
    def attach_email(self,eid,raw,name,headers_only=False):
        summary=parse_email(raw,headers_only)
        folder=self.data/'network';folder.mkdir(exist_ok=True)
        cid=uuid.uuid4().hex;rel='network/'+cid+('.headers.txt' if headers_only else '.eml');dest=self.data/rel
        try:
            dest.write_bytes(raw)
            with self.db:self.db.execute('INSERT INTO network_captures VALUES(?,?,?,?,?,?,?)',(cid,eid,name,rel,hashlib.sha256(raw).hexdigest(),now(),json.dumps(summary,ensure_ascii=False)))
            return summary
        except Exception:dest.unlink(missing_ok=True);raise
    def process_existing(self, progress=None):
        files=[dict(r) for r in self.db.execute('SELECT * FROM files WHERE active=1 ORDER BY added_at,id')]
        result={'processed':0,'already_complete':0,'failed':0,'cancelled':False,'issues':[]}
        for i,f in enumerate(files):
            if progress and not progress(i,len(files),f['name']):result['cancelled']=True;break
            missing=[k for k in ('phash','dhash','hash_method','hash_computed_at','metadata_json') if not f.get(k)]
            if not missing:result['already_complete']+=1;continue
            try:
                path=(self.data/f['path']).resolve()
                if not path.is_relative_to(self.attachments.resolve()):raise ValueError('Attachment path is outside the evidence folder.')
                with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
                if actual!=f['sha256']:raise ValueError('SHA-256 mismatch; file may have changed. Original record left intact.')
                updates={}
                if any(k in missing for k in ('phash','dhash','hash_method','hash_computed_at')):
                    values=dict(zip(('phash','dhash','hash_method','hash_computed_at'),perceptual_hashes(path)))
                    # Never silently combine fingerprints generated by different methods.
                    for key in ('phash','dhash','hash_method'):
                        if f.get(key) and f[key]!=values[key]:raise ValueError('Existing hash or method differs; manual review required.')
                    updates.update({k:values[k] for k in missing if k in values})
                if 'metadata_json' in missing:
                    metadata=inspect_metadata(path)
                    metadata['inspection_context']='Existing saved evidence copy; original source filesystem times unavailable.'
                    updates['metadata_json']=json.dumps(metadata,ensure_ascii=False)
                with self.db:
                    assignments=','.join(k+'=?' for k in updates)
                    self.db.execute('UPDATE files SET '+assignments+' WHERE id=?',(*updates.values(),f['id']))
                    self.db.execute('INSERT INTO attachment_processing VALUES(?,?,?,?,?)',(uuid.uuid4().hex,f['id'],now(),'processed',json.dumps({'fields_added':list(updates),'sha256_verified':True})))
                result['processed']+=1
            except Exception as exc:
                result['failed']+=1;result['issues'].append(f['name']+': '+str(exc))
                with self.db:self.db.execute('INSERT INTO attachment_processing VALUES(?,?,?,?,?)',(uuid.uuid4().hex,f['id'],now(),'failed',str(exc)))
        return result
    def backup(self, destination):
        destination=Path(destination)
        # Stage next to the destination, then replace only after a complete archive exists.
        fd, staging=tempfile.mkstemp(prefix='.audit-backup-',suffix='.zip',dir=destination.parent); os.close(fd)
        try:
            with tempfile.TemporaryDirectory() as td:
                snapshot=Path(td)/'audit-log.sqlite3'; conn=sqlite3.connect(snapshot)
                try: self.db.backup(conn)
                finally: conn.close()
                entries=self.list()
                with zipfile.ZipFile(staging,'w',zipfile.ZIP_DEFLATED) as z:
                    z.write(snapshot,'data/audit-log.sqlite3')
                    z.writestr('audit-log.json',json.dumps({'version':1,'exported_at':now(),'entries':entries,'attachment_processing':[dict(r) for r in self.db.execute('SELECT * FROM attachment_processing ORDER BY processed_at,rowid')]},ensure_ascii=False,indent=2))
                    # Include retired attachments referenced by revision history, too.
                    for f in self.db.execute('SELECT * FROM files'):
                        source=self.data/f['path']
                        if not source.is_file(): raise ValueError('Missing attachment: '+f['name'])
                        if hashlib.sha256(source.read_bytes()).hexdigest()!=f['sha256']: raise ValueError('Attachment has changed: '+f['name'])
                        z.write(source,'data/'+f['path'])
                    for capture in self.db.execute('SELECT * FROM network_captures'):
                        source=self.data/capture['path']
                        with source.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
                        if digest!=capture['sha256']:raise ValueError('Network capture changed: '+capture['name'])
                        z.write(source,'data/'+capture['path'])

            os.replace(staging,destination)
        finally: Path(staging).unlink(missing_ok=True)
    def import_web(self, filename):
        import base64, re
        b=json.loads(Path(filename).read_text(encoding='utf-8-sig'))
        if b.get('format')!='document-audit-log' or b.get('version')!=1 or not isinstance(b.get('entries'),list): raise ValueError('Choose a JSON backup exported from the browser audit app.')
        count=0
        # Import the whole backup as one transaction; preserve original timestamps and IDs.
        copied=[]
        try:
            with self.db:
                for e in b['entries']:
                    if self.db.execute('SELECT 1 FROM entries WHERE id=?',(e['id'],)).fetchone(): continue
                    for k in ('id','title','certainty','recorded','source','facts','notes'):
                        if not isinstance(e.get(k),str): raise ValueError('Invalid entry in backup.')
                    datetime.fromisoformat(e['recorded'].replace('Z','+00:00'))
                    event=None if e['certainty']=='Unknown' else e['event']
                    if event: datetime.fromisoformat(event.replace('Z','+00:00'))
                    self.db.execute('INSERT INTO entries(id,title,event_at,certainty,recorded_at,source,facts,notes) VALUES(?,?,?,?,?,?,?,?)',(e['id'],e['title'],event,e['certainty'],e['recorded'],e['source'],e['facts'],e['notes']))
                    for f in e.get('files',[]):
                        match=re.fullmatch(r'data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)',f['data'])
                        if not match: raise ValueError('Unsupported image in backup.')
                        content=base64.b64decode(match[2],validate=True)
                        if len(content)>30*1024*1024: raise ValueError('An imported image is too large.')
                        fid=uuid.uuid4().hex; rel='attachments/'+fid+'.'+match[1]; path=self.data/rel
                        path.write_bytes(content);copied.append(path)
                        self.db.execute('INSERT INTO files(id,entry_id,name,path,sha256,added_at,phash,dhash,hash_method,hash_computed_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(fid,e['id'],f['name'],rel,hashlib.sha256(content).hexdigest(),e['recorded'],*perceptual_hashes(path),json.dumps(inspect_metadata(path),ensure_ascii=False)))
                    for a in e.get('addenda',[]):
                        datetime.fromisoformat(a['at'].replace('Z','+00:00'))
                        self.db.execute('INSERT INTO addenda VALUES(?,?,?,?)',(uuid.uuid4().hex,e['id'],a['text'],a['at']))
                    count+=1
            return count
        except Exception:
            for path in copied: path.unlink(missing_ok=True)
            raise

class LogLibrary:
    def __init__(self, root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.root/'log-library.sqlite3')
        self.db.row_factory=sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS logs(id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE COLLATE NOCASE,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        """)
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO logs VALUES(?,?,?)',('default','Original audit log',now()))
    def logs(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM logs ORDER BY CASE WHEN id='default' THEN 0 ELSE 1 END,created_at,rowid")]
    def location(self, lid):
        if not self.db.execute('SELECT 1 FROM logs WHERE id=?',(lid,)).fetchone():raise ValueError('Audit log not found.')
        return self.root if lid=='default' else self.root/'account-logs'/lid
    def selected(self):
        row=self.db.execute("SELECT value FROM settings WHERE key='selected_log'").fetchone()
        return row['value'] if row and self.db.execute('SELECT 1 FROM logs WHERE id=?',(row['value'],)).fetchone() else 'default'
    def select(self,lid):
        self.location(lid)
        with self.db:self.db.execute("INSERT OR REPLACE INTO settings VALUES('selected_log',?)",(lid,))
    def create(self,name):
        name=name.strip()
        if not name:raise ValueError('Enter an account or log name.')
        if len(name)>120:raise ValueError('Use a name up to 120 characters.')
        if self.db.execute('SELECT 1 FROM logs WHERE name=? COLLATE NOCASE',(name,)).fetchone():raise ValueError('That name is already in use. Choose another name.')
        lid=uuid.uuid4().hex
        store=Store(self.root/'account-logs'/lid);store.db.close()
        with self.db:self.db.execute('INSERT INTO logs VALUES(?,?,?)',(lid,name,now()))
        return lid
    def rename(self,lid,name):
        name=name.strip()
        if not name or len(name)>120:raise ValueError('Enter a name between 1 and 120 characters.')
        with self.db:self.db.execute('UPDATE logs SET name=? WHERE id=?',(name,lid))

class LocalDateTimeInput(QLineEdit):
    """Plain editable clock text: no segmented spinbox or auto-correction."""
    def __init__(self,value=None):
        super().__init__();self.setPlaceholderText('YYYY-MM-DD HH:MM:SS (24-hour)')
        self.setToolTip('Type or paste the whole local date and time. Accepts 2026-11-10 13:18:00 or 2026-11-10 01:18:00 PM. Nothing is changed until you save.')
        self.setDateTime(value or QDateTime.currentDateTime())
    def setDateTime(self,value):self.setText(value.toString('yyyy-MM-dd HH:mm:ss'))
    def dateTime(self):
        text=self.text().strip()
        for fmt in ('%Y-%m-%d %H:%M:%S','%Y-%m-%d %I:%M:%S %p','%Y-%m-%d %H:%M','%Y-%m-%dT%H:%M:%S'):
            try:dt=datetime.strptime(text.upper(),fmt)
            except ValueError:continue
            return QDateTime(QDate(dt.year,dt.month,dt.day),QTime(dt.hour,dt.minute,dt.second))
        return QDateTime()

class EntryDialog(QDialog):
    def __init__(self, parent, entry=None):
        self.entry=entry;self.existing_files=[]
        super().__init__(parent); self.setWindowTitle('New audit entry'); self.resize(660,740); self.paths=[]
        outer=QVBoxLayout(self); scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        body=QWidget(); layout=QVBoxLayout(body)
        layout.addWidget(plain('EDIT TIMELINE ENTRY' if entry else 'NEW TIMELINE ENTRY','font-size:20px;font-weight:700;'))
        layout.addWidget(plain('Describe the event and attach its supporting screenshots.','color:#a4aaaf;'))
        form=QFormLayout(); form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.title=QLineEdit();self.title.setPlaceholderText('A brief factual title');form.addRow('Title',self.title)
        self.event=LocalDateTimeInput();form.addRow('Event date and time · in the timezone below',self.event)
        self.timezone=QComboBox();self.timezone.setEditable(True);self.timezone.addItems(sorted(available_timezones()))
        self.detected_timezone,self.timezone_detection=detect_local_zone()
        system_id=self.detected_timezone
        self.timezone.setCurrentText(system_id)
        self.timezone_override=QCheckBox('Override timezone for this entry')
        form.addRow('Automatic timezone',plain(system_id+' · '+self.timezone_detection,'font-size:11px;color:#a4aaaf;'))
        form.addRow('',self.timezone_override);form.addRow('Entry timezone · IANA name or UTC±HH:MM',self.timezone)
        self.timezone_override.toggled.connect(self.timezone_mode_changed)
        self.timezone.currentTextChanged.connect(self.timezone_selected)
        form.addRow('',plain('New entries default to your computer’s timezone. An override affects this entry only. Changing the zone keeps the typed clock.','font-size:10px;color:#a4aaaf;'))
        self.fold=QComboBox();self.fold.addItems(['Select only if this time occurs twice','First occurrence (before clocks move back)','Second occurrence (after clocks move back)']);form.addRow('Daylight saving overlap',self.fold)
        self.event.setText(datetime.now(zone(system_id)).strftime('%Y-%m-%d %H:%M:%S'))

        self.certainty=QComboBox();self.certainty.addItems(['Exact as reported','Estimated','Unknown']);self.certainty.currentTextChanged.connect(self.update_timezone_controls);form.addRow('Time certainty',self.certainty)
        self.source=QLineEdit();self.source.setPlaceholderText('Document, URL, person, device, or timestamp context');form.addRow('Source and context',self.source)
        self.facts=QTextEdit();self.facts.setAcceptRichText(False);self.facts.setPlaceholderText('What you directly saw, heard, or received');self.facts.setMinimumHeight(110);form.addRow('Factual description',self.facts)
        self.notes=QTextEdit();self.notes.setAcceptRichText(False);self.notes.setPlaceholderText('Explanation, uncertainties, and follow-up');self.notes.setMinimumHeight(90);form.addRow('Notes and explanation  ·  optional',self.notes)
        layout.addLayout(form)
        row=QHBoxLayout();row.addWidget(button('+ Attach screenshots',self.attach,True));row.addWidget(button('Paste screenshot',self.paste_screenshot,True));row.addWidget(button('Remove selected',self.remove,True));layout.addLayout(row)
        layout.addWidget(plain('Drag image files into the area below · Ctrl+V here or Ctrl+Shift+V anywhere to paste a screenshot','font-size:10px;color:#a4aaaf;'))
        self.files=ScreenshotDropList();self.files.setMaximumHeight(120);self.files.filesDropped.connect(self.add_screenshot_paths);self.files.pasteRequested.connect(self.paste_screenshot);layout.addWidget(self.files)
        self._clipboard_temp=None
        self.paste_shortcut=QShortcut(QKeySequence('Ctrl+Shift+V'),self);self.paste_shortcut.activated.connect(self.paste_screenshot)
        layout.addWidget(plain('Screenshot copies are saved locally. Edits retain previous values and removed screenshots in the history.','color:#a4aaaf;font-size:11px;'))
        scroll.setWidget(body);outer.addWidget(scroll)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);outer.addWidget(buttons)
        if entry:
            self.setWindowTitle('Edit audit entry')
            self.title.setText(entry['title']);self.source.setText(entry['source'])
            self.facts.setPlainText(entry['facts']);self.notes.setPlainText(entry['notes'])
            self.timezone_override.setChecked(True)
            if entry['event_at']:
                saved=datetime.fromisoformat(entry['event_at']);selected=entry.get('event_timezone') or fixed_zone(saved)
                self.timezone.setCurrentText(selected);local=saved.astimezone(zone(selected));self.event.setText(local.strftime('%Y-%m-%d %H:%M:%S'));self.fold.setCurrentIndex(local.fold+1)
            self.certainty.setCurrentText(entry['certainty'])
            self.existing_files=list(entry['files'])
            for f in self.existing_files:self.files.addItem(f['name']+'  (saved)')

        self.update_timezone_controls()

    def update_timezone_controls(self,*args):
        known=self.certainty.currentText()!='Unknown'
        self.event.setEnabled(known);self.fold.setEnabled(known);self.timezone_override.setEnabled(known)
        self.timezone.setEnabled(known and self.timezone_override.isChecked())
    def timezone_mode_changed(self,override):
        if not override:
            self.timezone.blockSignals(True);self.timezone.setCurrentText(self.detected_timezone);self.timezone.blockSignals(False)
            self.fold.setCurrentIndex(0)
        if hasattr(self,'certainty'):self.update_timezone_controls()
    def timezone_selected(self,name):
        # A programmatic selection also represents an explicit override.
        if name!=self.detected_timezone and not self.timezone_override.isChecked():self.timezone_override.setChecked(True)

    def attach(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Attach screenshots','','Images (*.png *.jpg *.jpeg *.webp *.bmp)')
        self.add_screenshot_paths(paths)
    def add_screenshot_paths(self,paths,clipboard=False):
        errors=[]
        allowed={'PNG','JPEG'} if clipboard else {'PNG','JPEG','WEBP','BMP'}
        for raw in paths:
            path=Path(raw)
            try:
                if not path.is_file():raise ValueError('not a file')
                if path.stat().st_size>50*1024*1024:raise ValueError('image exceeds 50 MB')
                if clipboard and path.suffix.lower() not in ('.png','.jpg','.jpeg'):raise ValueError('clipboard files must be PNG or JPEG')
                with Image.open(path) as image:
                    if image.format not in allowed:raise ValueError('unsupported image content; PNG or JPEG required for clipboard files' if clipboard else 'unsupported image format')
                    image.verify()
                if QPixmap(str(path)).isNull():raise ValueError('image cannot be displayed')
                resolved=str(path.resolve())
                if os.path.normcase(resolved) not in {os.path.normcase(str(Path(p).resolve())) for p in self.paths}:
                    self.paths.append(resolved);self.files.addItem(path.name)
            except (OSError,ValueError,Image.DecompressionBombError) as e:errors.append(path.name+': '+str(e))
        if errors:QMessageBox.warning(self,'Some images were not attached','\n'.join(errors[:12]))
    def paste_screenshot(self):
        clipboard=QApplication.clipboard();mime=clipboard.mimeData()
        paths=local_paths(mime)
        if mime.hasUrls():
            if not paths:QMessageBox.warning(self,'No local image','Clipboard links are not downloaded. Copy a local PNG/JPEG file or an image.');return
            self.add_screenshot_paths(paths,clipboard=True);return
        image=clipboard.image()
        if image.isNull():QMessageBox.information(self,'No screenshot to paste','Copy an image or a PNG/JPEG file first. Text and web links are not uploaded.');return
        if image.width()*image.height()>80_000_000:QMessageBox.warning(self,'Image too large','Clipboard images must be under 80 megapixels.');return
        if self._clipboard_temp is None:
            self._clipboard_temp=tempfile.TemporaryDirectory(prefix='banshield-clipboard-')
            cleanup=self._clipboard_temp.cleanup;self.destroyed.connect(lambda *args:cleanup())
        path=Path(self._clipboard_temp.name)/('clipboard-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]+'.png')
        if not image.save(str(path),'PNG'):QMessageBox.warning(self,'Paste failed','Could not save the clipboard image as PNG.');return
        self.add_screenshot_paths([str(path)],clipboard=True)
    def remove(self):
        i=self.files.currentRow()
        if i>=0:
            if i<len(self.existing_files):self.existing_files.pop(i)
            else:self.paths.pop(i-len(self.existing_files))
            self.files.takeItem(i)
    def selected_event(self):
        if self.certainty.currentText()=='Unknown':return None
        fold=self.fold.currentIndex()-1 if self.fold.currentIndex()>0 else None
        return resolve_wall(self.event.text(),self.timezone.currentText().strip(),fold)
    def validate(self):
        try:self.selected_event()
        except ValueError as e:
            QMessageBox.warning(self,'Check event time',str(e));self.event.setFocus();return
        if not self.title.text().strip() or not self.facts.toPlainText().strip():
            QMessageBox.warning(self,'Missing information','Enter a title and factual description.');return
        self.accept()
    def values(self):
        selected=self.selected_event();event=selected.isoformat(timespec='seconds') if selected else None
        if self.entry and self.entry['event_at'] and event and self.timezone.currentText().strip()==(self.entry.get('event_timezone') or fixed_zone(datetime.fromisoformat(self.entry['event_at']))) and datetime.fromisoformat(event)==datetime.fromisoformat(self.entry['event_at']):event=self.entry['event_at']
        return (self.title.text().strip(),event,self.certainty.currentText(),self.source.text().strip(),self.facts.toPlainText().strip(),self.notes.toPlainText().strip(),self.paths)

class ImageDialog(QDialog):
    def __init__(self, path, name, parent):
        super().__init__(parent);self.setWindowTitle(name);self.resize(1000,760)
        l=QVBoxLayout(self);l.addWidget(plain(name,'font-weight:700;'))
        scroll=QScrollArea();image=QLabel();image.setPixmap(QPixmap(str(path)));scroll.setWidget(image);l.addWidget(scroll)
        l.addWidget(button('Open original size in image viewer',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))),True))

class Window(QMainWindow):
    def __init__(self, store, library=None, log_id=None):
        super().__init__();self.library=library;self.log_id=log_id;self.store=store;self.setWindowTitle('BanShield');self.resize(1120,840)
        root=QWidget();self.setCentralWidget(root);outer=QVBoxLayout(root);outer.setContentsMargins(35,22,35,20);outer.setSpacing(18)
        brand=QHBoxLayout();brand.addWidget(plain('◇   RECORD   /   Personal workspace','font-size:12px;color:#c0c6ca;'));brand.addStretch(1);brand.addWidget(plain('●  Saved on this computer','color:#b7c6b3;font-size:12px;'));outer.addLayout(brand)
        heading=QHBoxLayout();col=QVBoxLayout();col.addWidget(plain('DOCUMENTATION WORKSPACE','font-size:10px;color:#a4aaaf;letter-spacing:2px;'));col.addWidget(plain('BanShield','font-size:30px;font-weight:700;'));col.addWidget(plain('A clear record of what happened, and when.','color:#a4aaaf;'));heading.addLayout(col,1);heading.addWidget(button('+ New entry',self.new_entry));outer.addLayout(heading)
        if self.library:
            logrow=QHBoxLayout();logrow.addWidget(plain('ACCOUNT / AUDIT LOG','font-size:10px;color:#a4aaaf;font-weight:700;'))
            self.log_selector=QComboBox();self.log_selector.setMinimumWidth(240);self.log_selector.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
            self.load_log_choices();self.log_selector.currentIndexChanged.connect(self.switch_log);logrow.addWidget(self.log_selector,1)
            logrow.addWidget(button('+ New audit log',self.create_log));logrow.addWidget(button('Rename',self.rename_log,True));outer.addLayout(logrow)
        processing_row=QHBoxLayout();processing_row.addWidget(button('Process existing attachments',self.process_existing,True));processing_row.addWidget(plain('Fill missing hashes and metadata in the selected log','font-size:11px;color:#a4aaaf;'));processing_row.addWidget(button('API cross-checks · Gemini / ChatGPT',self.text_analysis,True));processing_row.addWidget(button('HAR / API capture guide',self.capture_guide,True));processing_row.addStretch();outer.addLayout(processing_row)

        tools=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Search notes, titles, sources, and evidence…');self.search.textChanged.connect(self.refresh);tools.addWidget(self.search,1)
        self.sort=QComboBox();self.sort.addItems(['Newest event first','Oldest event first']);self.sort.currentIndexChanged.connect(self.refresh);tools.addWidget(self.sort)
        tools.addWidget(button('Export backup',self.backup,True));tools.addWidget(button('Public export',self.public_export,True));tools.addWidget(button('More',self.more,True));outer.addLayout(tools)
        self.count=plain('');outer.addWidget(self.count)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setFrameShape(QFrame.Shape.NoFrame);outer.addWidget(self.scroll,1)
        self.status=plain('','color:#a4aaaf;font-size:11px;');outer.addWidget(self.status)
        self.path_label=plain('Local storage: '+str(self.store.data),'color:#8f989f;font-size:10px;');outer.addWidget(self.path_label)
        self.refresh()
    def load_log_choices(self):
        self.log_selector.blockSignals(True);self.log_selector.clear()
        for item in self.library.logs():self.log_selector.addItem(item['name'],item['id'])
        self.log_selector.setCurrentIndex(self.log_selector.findData(self.log_id));self.log_selector.blockSignals(False)
        label=next((r['name'] for r in self.library.logs() if r['id']==self.log_id),'Audit log')
        self.setWindowTitle(label+' — BanShield')
    def switch_log(self,*args):
        lid=self.log_selector.currentData()
        if not lid or lid==self.log_id:return
        new_store=None
        try:
            new_store=Store(self.library.location(lid));self.library.select(lid)
        except Exception as e:
            if new_store:new_store.db.close()
            self.load_log_choices();QMessageBox.critical(self,'Cannot open log',str(e));return
        old=self.store;self.store=new_store;self.log_id=lid;old.db.close()
        self.search.blockSignals(True);self.search.clear();self.search.blockSignals(False)
        self.path_label.setText('Local storage: '+str(self.store.data));self.refresh();self.load_log_choices()
        self.status.setText('Opened '+self.log_selector.currentText()+' · changes save in this log only.')
    def create_log(self):
        name,ok=QInputDialog.getText(self,'New audit log','Account or audit log name:')
        if not ok:return
        try:
            lid=self.library.create(name);self.load_log_choices()
            self.log_selector.setCurrentIndex(self.log_selector.findData(lid))
        except Exception as e:QMessageBox.warning(self,'Cannot create log',str(e))
    def rename_log(self):
        name,ok=QInputDialog.getText(self,'Rename audit log','Account or audit log name:',text=self.log_selector.currentText())
        if not ok:return
        try:self.library.rename(self.log_id,name);self.load_log_choices()
        except Exception as e:QMessageBox.warning(self,'Cannot rename log',str(e))
    def refresh(self,*args):
        if args or not hasattr(self,'_visible_limit'):self._visible_limit=50
        rows=self.store.list(self.search.text(),self.sort.currentIndex()==0)
        all_entries=self.store.list()
        _,cluster_summary,cluster_lookup=cluster_submissions(all_entries)
        from api_cross_checks import load_cross_checks
        self.api_checks=load_cross_checks(self.store.data,self.store.db,all_entries)
        for entry in rows:
            for file in entry['files']:file['visual_cluster']=cluster_lookup.get(file['id'],{})
        total=self.store.db.execute('SELECT count(*) FROM entries').fetchone()[0]
        rate=cluster_summary['exact_pattern_match_rate'];rate_text=f'{rate:.1%}' if rate is not None else 'N/A'
        self.count.setText(f"{total} entries · {cluster_summary['total_submissions']} submissions · {cluster_summary['unique_visual_clusters']} visual clusters · {rate_text} exact pattern repeat rate")
        self.count.setToolTip(cluster_summary['exact_pattern_definition']+' '+cluster_summary['matching_rule'])
        body=QWidget();layout=QVBoxLayout(body);layout.setContentsMargins(0,5,5,5);layout.setSpacing(0)
        if not rows:
            layout.addSpacing(70);layout.addWidget(plain('◇','font-size:40px;color:#a4b19f;'),0,Qt.AlignmentFlag.AlignHCenter)
            layout.addWidget(plain('Your record starts here' if total==0 else 'No matching entries','font-size:21px;font-weight:700;'),0,Qt.AlignmentFlag.AlignHCenter)
            layout.addWidget(plain('Add an event, write what happened, and attach its screenshots.','color:#a4aaaf;'),0,Qt.AlignmentFlag.AlignHCenter)
            if not total: layout.addWidget(button('+ Create your first entry',self.new_entry),0,Qt.AlignmentFlag.AlignHCenter)
        for e in rows[:self._visible_limit]:layout.addWidget(self.card(e))
        if len(rows)>self._visible_limit:
            layout.addWidget(plain(f'Showing {self._visible_limit} of {len(rows)} matching entries. Search covers the entire log.','color:#a4aaaf;font-size:11px;'))
            layout.addWidget(button('Load next 50 entries',self.load_more,True))
        layout.addStretch();self.scroll.setWidget(body)
    def load_more(self):
        position=self.scroll.verticalScrollBar().value();self._visible_limit+=50;self.refresh();self.scroll.verticalScrollBar().setValue(position)
    def card(self,e):
        container=QWidget();row=QHBoxLayout(container);row.setContentsMargins(0,0,0,0);row.setSpacing(15)
        rail=QWidget();rail.setFixedWidth(24);rl=QVBoxLayout(rail);rl.setContentsMargins(0,4,0,0);rl.setSpacing(6);rl.addWidget(plain('◇','font-family:Segoe UI Symbol;font-size:20px;color:#e3e7e9;'),0,Qt.AlignmentFlag.AlignHCenter);line=QFrame();line.setFrameShape(QFrame.Shape.VLine);line.setStyleSheet('color:#485057;');rl.addWidget(line,1,Qt.AlignmentFlag.AlignHCenter);row.addWidget(rail)
        content=QWidget();l=QVBoxLayout(content);l.setContentsMargins(0,0,0,28);l.setSpacing(8)
        l.addWidget(plain(e['title'],'font-weight:700;font-size:14px;'))
        when='Event time unknown'
        if e['event_at']:
            dt=datetime.fromisoformat(e['event_at']);when=dt.strftime('%b %d, %Y | %I:%M:%S %p UTC%z')+' · '+(e.get('event_timezone') or 'original recorded offset')
        if e['certainty']=='Estimated':when+='  ·  Estimated'
        l.addWidget(plain(when,'font-size:12px;color:#dde1e3;'))
        l.addWidget(plain(e['id']+('  ·  '+e['source'] if e['source'] else ''),'font-size:10px;color:#929da5;'))
        l.addSpacing(4);l.addWidget(plain(e['facts'],'font-size:13px;'))
        if e['notes']:
            l.addWidget(plain('Notes and explanation','font-size:12px;font-weight:700;'))
            note=plain(e['notes']);note.setStyleSheet('background:#2d3134;border:1px solid #41474c;border-radius:7px;padding:13px;font-size:13px;');l.addWidget(note)
        generated=self.api_checks.get(e['id'],[]) if hasattr(self,'api_checks') else []
        if generated:
            l.addWidget(plain('API cross-checks · read only','font-size:12px;font-weight:700;'))
            for check in generated[:6]:
                provider='Gemini' if check['provider']=='gemini' else 'ChatGPT / OpenAI'
                color,bg,border=('#c9b9f3','#302b3b','#514364') if check['provider']=='gemini' else ('#a1ddbf','#263830','#3f6350')
                card=QFrame();card.setObjectName('apiCheck');card.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Maximum)
                card.setStyleSheet(f'QFrame#apiCheck{{background:{bg};border:1px solid {border};border-radius:7px;}}')
                note_layout=QVBoxLayout(card);note_layout.setContentsMargins(12,8,12,9);note_layout.setSpacing(4)
                note_layout.addWidget(plain(provider+' · '+check['model']+' · '+display_time(check['generated_at']),f'background:transparent;color:{color};font-size:11px;font-weight:700;'))
                note_layout.addWidget(plain(check['finding']['statement'],'background:transparent;font-size:12px;'))
                note_layout.addWidget(plain('Rubric '+str(check['finding']['rubric_score'])+'/100 · saved analysis snapshot; rerun after evidence changes','background:transparent;color:#a4aaaf;font-size:10px;'))
                note_layout.addWidget(button('View generated finding',lambda checked=False,value=check:self.view_api_finding(value),True));l.addWidget(card)
            if len(generated)>6:l.addWidget(plain('Showing the latest 6 matching findings. Full reports remain in the private analysis folder.','font-size:10px;color:#a4aaaf;'))
        if any(e.get('ai_notes',{}).values()):
            l.addWidget(button('View legacy manual notes (not API output)',lambda checked=False,entry=e:self.view_legacy_notes(entry),True),0,Qt.AlignmentFlag.AlignLeft)
        for f in e['files']:
            path=self.store.data/f['path'];thumb=QPixmap(str(path));image=QPushButton();image.setProperty('secondary',True);image.setFixedSize(240,145)
            if not thumb.isNull():
                from PySide6.QtGui import QIcon
                image.setIcon(QIcon(thumb));image.setIconSize(image.size()*0.92)
            else:image.setText('Image unavailable')
            image.clicked.connect(lambda checked=False,p=path,n=f['name']:ImageDialog(p,n,self).exec());l.addWidget(image)
            l.addWidget(plain(f['name']+'  ·  attached '+display_time(f['added_at']),'font-size:10px;color:#a4aaaf;'))
            hashlabel=plain('SHA 256  '+f['sha256'],'font-size:9px;color:#8f989f;');l.addWidget(hashlabel)
            cluster=f.get('visual_cluster',{})
            l.addWidget(plain('Visual cluster: '+(cluster.get('cluster_id') or 'unassigned')+'  ·  '+str(cluster.get('cluster_size',0))+' submission(s)','font-size:10px;color:#b7c6b3;'))
            metadata=json.loads(f.get('metadata_json') or '{}')
            if metadata:
                created=metadata.get('creation_timestamp')
                l.addWidget(plain('Image creation timestamp: '+(str(created)+'  ·  '+metadata.get('creation_source','')+'  ·  timezone '+metadata.get('timezone_status','unknown') if created else 'not present in image metadata'),'font-size:10px;color:#c9c6ad;'))
                if metadata.get('source_filesystem_created_at'):l.addWidget(plain('Source file created: '+metadata['source_filesystem_created_at']+' (not verified capture time)','font-size:10px;color:#a4aaaf;'))
                flags=metadata.get('sensitive_fields',[])
                l.addWidget(plain('Metadata flags: '+(', '.join(flags) if flags else 'no recognized sensitive fields detected; this is not a privacy guarantee'),'font-size:10px;color:#e1b887;'))
            else:l.addWidget(plain('Metadata inspection not recorded for this older attachment.','font-size:10px;color:#a4aaaf;'))

            if f.get('phash') and f.get('dhash'):
                l.addWidget(plain('pHash  '+f['phash']+'    ·    dHash  '+f['dhash'],'font-size:10px;color:#bdcdae;'))
                l.addWidget(plain('Computed '+display_time(f['hash_computed_at'])+'  ·  '+f['hash_method'],'font-size:9px;color:#8f989f;'))
            else:l.addWidget(plain('pHash / dHash not recorded for this older attachment.','font-size:10px;color:#8f989f;'))

        if e.get('network_captures'):
            l.addWidget(plain('Private network evidence','font-size:12px;font-weight:700;'))
            for capture in e['network_captures']:
                summary=json.loads(capture['summary_json']);statuses={}
                for request in summary['requests']:
                    status=str(request.get('status') if request.get('status') is not None else 'unknown');statuses[status]=statuses.get(status,0)+1
                description=(summary['kind']+' · '+str(len(summary.get('timestamps',[])))+' reported timestamp(s) · DKIM not verified') if summary['kind'] in ('EML','SMTP headers') else str(len(summary['requests']))+' request(s) · statuses '+str(statuses)
                l.addWidget(plain(capture['name']+' · '+description,'color:#c5bedc;font-size:11px;'))
                l.addWidget(plain('Imported '+display_time(capture['imported_at'])+' · SHA 256 '+capture['sha256'],'font-size:9px;color:#8f989f;'))
                l.addWidget(button('Inspect email headers and timing' if summary['kind'] in ('EML','SMTP headers') else 'Inspect HTTP statuses, server times and bodies',lambda checked=False,c=capture:self.view_capture(c),True),0,Qt.AlignmentFlag.AlignLeft)
        l.addWidget(button('+ Attach raw email / SMTP headers',lambda checked=False,eid=e['id']:self.attach_email(eid),True),0,Qt.AlignmentFlag.AlignLeft)
        l.addWidget(button('+ Attach HAR / JSON response',lambda checked=False,eid=e['id']:self.attach_network(eid),True),0,Qt.AlignmentFlag.AlignLeft)
        for a in e['addenda']:
            l.addWidget(plain('ADDENDUM  ·  '+display_time(a['recorded_at']),'color:#b7c6b3;font-size:10px;'));l.addWidget(plain(a['text']))
        bottom=QHBoxLayout();bottom.addWidget(plain('Recorded '+display_time(e['recorded_at']),'color:#929da5;font-size:10px;'));bottom.addStretch();bottom.addWidget(button('Edit entry',lambda checked=False,entry=e:self.edit_entry(entry),True));bottom.addWidget(button('+ Add correction or note',lambda checked=False,eid=e['id']:self.amend(eid),True));l.addLayout(bottom)
        if e['revisions']:
            fields=set()
            for revision in e['revisions']:
                before=json.loads(revision['before_json']);after=json.loads(revision['after_json'])
                fields.update(k for k in before if before[k]!=after[k])
            names={'title':'Title','event_at':'Event timestamp','event_timezone':'Event timezone','certainty':'Time certainty','source':'Source and context','facts':'Factual description','notes':'Notes and explanation','screenshots':'Screenshots','ai_notes':'Legacy manual AI notes'}
            summary='Edited '+display_time(e['revisions'][-1]['edited_at'])+'  ·  '+str(len(e['revisions']))+' saved edit(s)'
            l.addWidget(plain(summary,'color:#d3c99f;font-size:11px;'))
            l.addWidget(plain('Changed: '+', '.join(names[k] for k in names if k in fields),'color:#a4aaaf;font-size:11px;'))
            l.addWidget(button('View edit history',lambda checked=False,entry=e:self.history(entry),True),0,Qt.AlignmentFlag.AlignLeft)
        row.addWidget(content,1);return container
    def edit_entry(self,entry):
        dialog=EntryDialog(self,entry)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            try:
                changed=self.store.edit(entry['id'],*dialog.values(),[f['id'] for f in dialog.existing_files],expected=self.store.snapshot(entry),event_timezone=dialog.timezone.currentText().strip())
                self.refresh();self.status.setText('Changes saved with edit history  ·  '+display_time(now()) if changed else 'No changes to save.')
            except Exception as e:QMessageBox.critical(self,'Could not save changes',str(e))
    def history(self,entry):
        d=QDialog(self);d.setWindowTitle('Edit history — '+entry['title']);d.resize(780,700)
        outer=QVBoxLayout(d);outer.addWidget(plain('Edit history','font-size:22px;font-weight:700;'))
        outer.addWidget(plain('Original recorded time: '+display_time(entry['recorded_at']),'color:#a4aaaf;'))
        scroll=QScrollArea();scroll.setWidgetResizable(True);body=QWidget();layout=QVBoxLayout(body)
        names={'title':'Title','event_at':'Event timestamp','event_timezone':'Event timezone','certainty':'Time certainty','source':'Source and context','facts':'Factual description','notes':'Notes and explanation','screenshots':'Screenshots','ai_notes':'Legacy manual AI notes'}
        for index,r in reversed(list(enumerate(entry['revisions'],1))):
            layout.addWidget(plain(f"EDIT {index}  ·  {display_time(r['edited_at'])}",'font-weight:700;color:#d3c99f;'))
            before=json.loads(r['before_json']);after=json.loads(r['after_json'])
            for key,label in names.items():
                if before.get(key)==after.get(key):continue
                layout.addWidget(plain(label,'font-weight:700;'))
                if key=='ai_notes':
                    for provider in ('Gemini','ChatGPT','Grok'):
                        old=before.get(key,{}).get(provider,'');new=after.get(key,{}).get(provider,'')
                        if old==new:continue
                        layout.addWidget(plain(provider,'font-weight:700;'))
                        layout.addWidget(plain('Before: '+(old or '(empty)'),'background:#2d3134;padding:10px;border-radius:5px;'))
                        layout.addWidget(plain('After: '+(new or '(empty)'),'background:#303a31;padding:10px;border-radius:5px;'))
                elif key=='screenshots':
                    old={f['id']:f for f in before[key]};new={f['id']:f for f in after[key]}
                    for fid in old.keys()-new.keys():
                        f=old[fid];layout.addWidget(plain('Removed from current entry: '+f['name']+' (original copy retained)'))
                        layout.addWidget(button('View retained screenshot: '+f['name'],lambda checked=False,f=f:ImageDialog(self.store.data/f['path'],f['name'],d).exec(),True))
                    for fid in new.keys()-old.keys():layout.addWidget(plain('Added: '+new[fid]['name']))
                else:
                    def text(value):return display_time(value) if key=='event_at' else (value or '(empty)')
                    layout.addWidget(plain('Before: '+text(before.get(key)),'background:#2d3134;padding:10px;border-radius:5px;'))
                    layout.addWidget(plain('After: '+text(after.get(key)),'background:#303a31;padding:10px;border-radius:5px;'))
            layout.addSpacing(20)
        scroll.setWidget(body);outer.addWidget(scroll);outer.addWidget(button('Close',d.accept,True));d.exec()
    def new_entry(self):
        dialog=EntryDialog(self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            try:self.store.add(*dialog.values(),event_timezone=dialog.timezone.currentText().strip());self.refresh();self.status.setText('Entry saved  ·  '+display_time(now()))
            except Exception as e:QMessageBox.critical(self,'Could not save',str(e))
    def amend(self,eid):
        d=QDialog(self);d.setWindowTitle('Add a correction or note');d.resize(540,340);l=QVBoxLayout(d);l.addWidget(plain('The original entry stays visible. Your addition receives its own timestamp.'));text=QTextEdit();text.setAcceptRichText(False);l.addWidget(text);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);l.addWidget(buttons);buttons.accepted.connect(lambda:d.accept() if text.toPlainText().strip() else None);buttons.rejected.connect(d.reject)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.store.amend(eid,text.toPlainText().strip());self.refresh();self.status.setText('Addendum saved  ·  '+display_time(now()))
            except Exception as e:QMessageBox.critical(self,'Could not save',str(e))
    def process_existing(self):
        progress=QProgressDialog('Checking saved attachments…','Cancel',0,1,self)
        progress.setWindowTitle('Process existing attachments');progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0);progress.setAutoClose(False);progress.setAutoReset(False)
        def advance(index,total,name):
            progress.setMaximum(max(total,1));progress.setValue(index);progress.setLabelText(f'Checking {index+1} of {total}: {name}')
            QApplication.processEvents();return not progress.wasCanceled()
        try:
            result=self.store.process_existing(advance);progress.close();self.refresh()
            message=(f"Processed: {result['processed']}\nAlready complete: {result['already_complete']}\nFailed or changed: {result['failed']}"+
                     ('\nCancelled. Completed work was saved.' if result['cancelled'] else '')+
                     '\n\nOriginal files, entry timestamps and submission counts are unchanged. Processing results are logged in private backups.')
            if result['issues']:message+='\n\n'+ '\n'.join(result['issues'][:15])
            self.status.setText(f"Attachment processing: {result['processed']} updated, {result['failed']} failed.")
            QMessageBox.information(self,'Attachment processing complete',message)
        except Exception as e:progress.close();QMessageBox.critical(self,'Processing failed',str(e))
    def view_legacy_notes(self,entry):
        d=QDialog(self);d.setWindowTitle('Legacy manual notes — not API generated');d.resize(640,440);layout=QVBoxLayout(d)
        layout.addWidget(plain('Historical user-entered notes, preserved for reference. These are not verified API cross-checks and cannot be edited here.'))
        text=QTextEdit();text.setReadOnly(True);text.setPlainText(json.dumps(entry['ai_notes'],ensure_ascii=False,indent=2));layout.addWidget(text);layout.addWidget(button('Close',d.accept,True));d.exec()
    def view_api_finding(self,value):
        d=QDialog(self);d.setWindowTitle('Read-only API cross-check');d.resize(780,620);layout=QVBoxLayout(d);text=QTextEdit();text.setReadOnly(True);text.setPlainText(json.dumps(value,ensure_ascii=False,indent=2));layout.addWidget(text);layout.addWidget(button('Close',d.accept,True));d.exec()
    def text_analysis(self):
        from analysis_ui import AnalysisDialog
        AnalysisDialog(self.store.data,ROOT,self).exec()
        self.refresh()
    def attach_email(self,eid):
        choice,ok=QInputDialog.getItem(self,'Private email evidence','Export the original .eml from your mail client (Download original / Save as). A screenshot omits transport headers. Choose:', ['Import original .eml','Paste raw SMTP headers'],0,False)
        if not ok:return
        try:
            if choice=='Import original .eml':
                filename,_=QFileDialog.getOpenFileName(self,'Import original email','','Email (*.eml)')
                if not filename:return
                path=Path(filename)
                if path.stat().st_size>100*1024*1024:raise ValueError('Email exceeds 100 MB.')
                self.store.attach_email(eid,path.read_bytes(),path.name)
            else:
                d=QDialog(self);d.setWindowTitle('Paste complete SMTP headers');d.resize(740,560);l=QVBoxLayout(d)
                l.addWidget(plain('Pasted headers are a derivative, not an original email. Include Date, all Received hops, DKIM-Signature and Authentication-Results when available. Contains private addresses and IPs.'))
                text=QTextEdit();text.setAcceptRichText(False);l.addWidget(text)
                buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);l.addWidget(buttons);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject)
                if d.exec()!=QDialog.DialogCode.Accepted:return
                self.store.attach_email(eid,text.toPlainText().encode('utf-8'),'Pasted SMTP headers',True)
            self.refresh();self.status.setText('Email evidence saved privately; header clocks are unverified.')
        except Exception as e:QMessageBox.critical(self,'Email import failed',str(e))
    def view_email(self,capture):
        summary=json.loads(capture['summary_json']);d=QDialog(self);d.setWindowTitle('Private email headers and timing');d.resize(900,760);l=QVBoxLayout(d)
        l.addWidget(plain(summary['note'],'color:#e1b887;font-size:11px;'))
        content=QTextEdit();content.setReadOnly(True);content.setPlainText(json.dumps(summary,ensure_ascii=False,indent=2));l.addWidget(content,1)
        clocks=QComboBox()
        for t in summary['timestamps']:
            if t['utc']:clocks.addItem(t['source']+' · '+t['raw'],t)
        references=QComboBox()
        for e in self.store.list():
            if e['event_at']:references.addItem(e['title']+' · '+e['event_at'],{'id':e['id'],'at':e['event_at'],'certainty':e['certainty']})
        l.addWidget(plain('Compare a reported email clock against an explicitly selected event time.'));l.addWidget(clocks);l.addWidget(references)
        result=plain('');l.addWidget(result)
        def comparison():
            t=clocks.currentData();ref=references.currentData()
            if not t or not ref:return None
            start=datetime.fromisoformat(ref['at']);end=datetime.fromisoformat(t['utc'])
            if start.tzinfo is None:return None
            seconds=(end-start).total_seconds()
            category='negative interval — check chronology and clocks' if seconds<0 else ('under 3 hours based on selected clocks' if seconds<10800 else '3 hours or longer based on selected clocks')
            return f"Email timing comparison: capture {capture['id']}; {t['source']} {t['raw']} ({t['utc']}) minus event {ref['id']} {ref['at']} ({ref['certainty']}) = {seconds:g} seconds; {category}. Header authentication not verified; interval does not establish automation or lack of human intervention."
        def update(*args):result.setText(comparison() or 'No comparable timezone-aware timestamps available.')
        def save():
            value=comparison()
            if not value:return
            try:self.store.amend(capture['entry_id'],value);self.refresh();QMessageBox.information(d,'Comparison saved','Saved as a timestamped addendum to this email’s entry.')
            except Exception as e:QMessageBox.critical(d,'Could not save',str(e))
        clocks.currentIndexChanged.connect(update);references.currentIndexChanged.connect(update);update()
        l.addWidget(button('Save timing comparison as addendum',save,True));l.addWidget(button('Close',d.accept,True));d.exec()
    def capture_guide(self):
        QMessageBox.information(self,'Capture portal glitches — HAR / JSON',
            'Before reproducing a portal glitch, open your browser developer tools (usually F12 or Ctrl+Shift+I), select Network, enable Preserve log, and clear unrelated requests.\n\n'
            'Reproduce the missing violation or rejection. Export the relevant Network requests as HAR, including response content if your browser offers it. Alternatively, save the API response body as a JSON file. Attach it to the relevant BanShield entry with “Attach HAR / JSON response”.\n\n'
            'A capture must be running when the problem happens; it cannot reconstruct earlier requests. Browser sanitization may omit credentials or bodies. Raw JSON alone cannot establish HTTP status or server time.\n\n'
            'HAR files can contain session cookies, authorization tokens, private URLs and account details. Use only captures you are authorized to collect. BanShield imports files locally; it does not intercept traffic, sign in, or submit requests. Captures are excluded from public exports, but included in private backups.')
    def attach_network(self,eid):
        filename,_=QFileDialog.getOpenFileName(self,'Attach private network evidence','','Network evidence (*.har *.json)')
        if not filename:return
        try:
            summary=self.store.attach_network(eid,filename);self.refresh();self.status.setText('Private network evidence saved · '+summary['kind']+' · '+str(len(summary['requests']))+' request(s)')
        except Exception as e:QMessageBox.critical(self,'Capture import failed',str(e))
    def view_capture(self,capture):
        if json.loads(capture['summary_json'])['kind'] in ('EML','SMTP headers'):return self.view_email(capture)
        d=QDialog(self);d.setWindowTitle('Private HTTP evidence — '+capture['name']);d.resize(900,700);layout=QVBoxLayout(d)
        summary=json.loads(capture['summary_json']);layout.addWidget(plain('Private network evidence — excluded from public export','font-weight:700;color:#e1b887;'))
        layout.addWidget(plain(summary['note'],'font-size:11px;color:#a4aaaf;'))
        selector=QComboBox()
        for i,r in enumerate(summary['requests']):selector.addItem(f"{i+1} · {r.get('status') if r.get('status') is not None else 'unknown status'} · {r.get('method') or ''} · {r.get('url') or 'Raw JSON payload'}")
        layout.addWidget(selector);body=QTextEdit();body.setReadOnly(True);layout.addWidget(body,1)
        def show(index):
            if index<0:return
            r=summary['requests'][index];details={k:v for k,v in r.items() if k!='body'}
            text=json.dumps(details,ensure_ascii=False,indent=2)+'\n\nRESPONSE BODY\n'+(r.get('body') if r.get('body') is not None else '[Not present in capture]')
            body.setPlainText(text[:1000000]+('\n[Preview limited to 1,000,000 characters; full content retained in private backup.]' if len(text)>1000000 else ''))
        selector.currentIndexChanged.connect(show);show(selector.currentIndex());layout.addWidget(button('Close',d.accept,True));d.exec()
    def public_export(self):
        d=QDialog(self);d.setWindowTitle('Review public dataset export');d.resize(760,680);layout=QVBoxLayout(d)
        layout.addWidget(plain('Public dataset — review before sharing','font-size:20px;font-weight:700;'))
        layout.addWidget(plain('Original screenshots, names, notes, AI notes, sources, filenames and edit history are excluded. Only generic event IDs, event times, certainty, attachment counts and visual-cluster statistics are included. Each current attachment is one submission. CSV and summary files are included. Review or remove identifying timestamps below.','color:#d3c99f;'))
        preview=QTextEdit();preview.setAcceptRichText(False);preview.setPlainText(json.dumps(public_manifest(self.store.list()),indent=2));layout.addWidget(preview,1)
        paths=[];listing=QListWidget();listing.setMaximumHeight(75)
        def add_images():
            selected,_=QFileDialog.getOpenFileNames(d,'Select already redacted images','','Images (*.png *.jpg *.jpeg *.webp *.bmp)')
            for path in selected:
                if path not in paths:paths.append(path);listing.addItem(Path(path).name)
            reviewed.setChecked(False)
        def remove_image():
            i=listing.currentRow()
            if i>=0:paths.pop(i);listing.takeItem(i)
        row=QHBoxLayout();row.addWidget(button('Add reviewed / redacted images',add_images,True));row.addWidget(button('Remove selected',remove_image,True));layout.addLayout(row);layout.addWidget(listing)
        layout.addWidget(plain('Optional images are re-encoded without metadata. Visible identifiers are NOT automatically removed. Redact usernames, faces, email addresses, QR codes and other personal details before selecting images. This export never uploads to GitHub.','color:#e1b887;'))
        reviewed=QCheckBox('I reviewed the JSON and selected images for personal identifiers.');layout.addWidget(reviewed)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);layout.addWidget(buttons)
        def save():
            if not reviewed.isChecked():QMessageBox.warning(d,'Review needed','Review the dataset and images, then check the confirmation.');return
            try:
                manifest=json.loads(preview.toPlainText())
                if not isinstance(manifest,dict):raise ValueError('Dataset must be a JSON object.')
            except Exception as e:QMessageBox.warning(d,'Invalid JSON',str(e));return
            filename,_=QFileDialog.getSaveFileName(d,'Save reviewed public dataset','banshield-public.zip','ZIP archive (*.zip)')
            if not filename:return
            if not filename.lower().endswith('.zip'):filename+='.zip'
            try:export_public(filename,manifest,paths);self.status.setText('Public derivative saved: '+filename);d.accept()
            except Exception as e:QMessageBox.critical(d,'Export failed',str(e))
        buttons.accepted.connect(save);buttons.rejected.connect(d.reject);d.exec()
    def backup(self):
        filename,_=QFileDialog.getSaveFileName(self,'Export backup of current audit log',str(Path.home()/'Desktop'/('audit-backup-'+datetime.now().strftime('%Y-%m-%d-%H%M%S')+'.zip')),'ZIP backup (*.zip)')
        if not filename:return
        if not filename.lower().endswith('.zip'):filename+='.zip'
        try:self.store.backup(filename);self.status.setText('Backup saved to '+filename);QMessageBox.information(self,'Backup saved','Saved this audit log’s database, readable JSON, and every attached screenshot. Other account logs are separate; export them individually.\n\n'+filename)
        except Exception as e:QMessageBox.critical(self,'Backup failed',str(e))
    def more(self):
        from PySide6.QtWidgets import QMenu
        menu=QMenu(self);folder=menu.addAction('Open saved data folder');web=menu.addAction('Import browser app backup');info=menu.addAction('About saving and backups');chosen=menu.exec(self.cursor().pos())
        if chosen==folder:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.data)))
        elif chosen==web:
            path,_=QFileDialog.getOpenFileName(self,'Import browser app backup','','JSON backup (*.json)')
            if path:
                try:n=self.store.import_web(path);self.refresh();QMessageBox.information(self,'Import complete',f'Imported {n} entries. Existing IDs were preserved.')
                except Exception as e:QMessageBox.critical(self,'Import failed',str(e))
        elif chosen==info:QMessageBox.information(self,'Local records','Saved entries and addenda persist immediately in data/audit-log.sqlite3. Screenshot copies are kept in data/attachments. Closing this app does not delete them.\n\nExport ZIP backups regularly. To restore with the app closed, extract a backup into the app folder so its data folder is restored. Keep a copy of existing data before restoring.\n\nThe log is editable on disk and relies on your computer clock. It is not a tamper-proof or independently verified legal record. Hashes compare file contents; they do not establish when an event occurred.')

STYLE='''
QWidget{background:#222527;color:#eceeef;font-family:"Segoe UI";font-size:13px;}
QPushButton{background:#dce8d9;color:#222b22;border:1px solid transparent;border-radius:6px;padding:9px 14px;font-weight:600;}
QPushButton:hover{background:#ecf5e9;} QPushButton[secondary="true"]{background:#2a2e31;color:#eceeef;border:1px solid #41474c;} QPushButton[secondary="true"]:hover{background:#363d40;}
QLineEdit,QTextEdit,QDateTimeEdit,QComboBox,QListWidget{background:#292d30;border:1px solid #41474c;border-radius:5px;padding:8px;selection-background-color:#53644e;}
QLineEdit:focus,QTextEdit:focus,QDateTimeEdit:focus{border:1px solid #a9bda4;}QScrollArea{border:0;}QScrollBar:vertical{background:#25292c;width:10px;}QScrollBar::handle:vertical{background:#51595e;border-radius:4px;min-height:30px;}QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}QMenu{border:1px solid #41474c;}QMenu::item{padding:9px 18px;}QMenu::item:selected{background:#41474c;}QTabWidget::pane{border:1px solid #41474c;}QTabBar::tab{background:#292d30;padding:9px 16px;color:#a4aaaf;}QTabBar::tab:selected{background:#3d493b;color:#eceeef;}QToolTip{background:#34393d;color:#fff;}
'''

def main():
    app=QApplication(sys.argv);QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf');QFontDatabase.addApplicationFont('C:/Windows/Fonts/seguisym.ttf');app.setFont(QFont('Segoe UI',10));app.setApplicationName('BanShield');app.setStyle('Fusion');app.setStyleSheet(STYLE)
    try:
        library=LogLibrary(ROOT);log_id=library.selected();store=Store(library.location(log_id))
    except Exception as e:QMessageBox.critical(None,'Cannot open audit log',f'Could not open the data folder:\n{e}');return 1
    window=Window(store,library,log_id);window.show()
    result=app.exec();window.store.db.close();library.db.close();return result
if __name__=='__main__':sys.exit(main())



