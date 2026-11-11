from __future__ import annotations
import sys, os, json, sqlite3, hashlib, shutil, uuid, zipfile, tempfile
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt, QDateTime, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices, QFontDatabase, QFont
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QScrollArea, QFrame, QDialog, QFormLayout, QTextEdit, QDateTimeEdit, QFileDialog, QMessageBox, QListWidget, QDialogButtonBox, QSizePolicy, QTabWidget, QInputDialog)

ROOT = Path(__file__).resolve().parent

def now(): return datetime.now().astimezone().isoformat(timespec='seconds')
def display_time(value):
    if not value: return 'Unknown'
    try: return datetime.fromisoformat(value).astimezone().strftime('%b %d, %Y | %I:%M:%S %p %Z')
    except ValueError: return value

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
        CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY,entry_id TEXT NOT NULL REFERENCES entries(id),edited_at TEXT NOT NULL,before_json TEXT NOT NULL,after_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS addenda(id TEXT PRIMARY KEY,entry_id TEXT NOT NULL REFERENCES entries(id),text TEXT NOT NULL,recorded_at TEXT NOT NULL);
        ''');
        if 'active' not in {r[1] for r in self.db.execute('PRAGMA table_info(files)')}:
            self.db.execute('ALTER TABLE files ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
        if 'ai_notes' not in {r[1] for r in self.db.execute('PRAGMA table_info(entries)')}:
            self.db.execute("ALTER TABLE entries ADD COLUMN ai_notes TEXT NOT NULL DEFAULT '{}'")
        self.db.commit()
    def add(self, title, event_at, certainty, source, facts, notes, paths, ai_notes=None):
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
                records.append((fid,eid,original.name,'attachments/'+filename,digest.hexdigest(),timestamp))
            with self.db:
                self.db.execute('INSERT INTO entries(id,title,event_at,certainty,recorded_at,source,facts,notes) VALUES(?,?,?,?,?,?,?,?)',(eid,title,event_at,certainty,timestamp,source,facts,notes))
                self.db.execute('UPDATE entries SET ai_notes=? WHERE id=?',(json.dumps(ai_notes or {},ensure_ascii=False),eid))
                self.db.executemany('INSERT INTO files(id,entry_id,name,path,sha256,added_at) VALUES(?,?,?,?,?,?)',records)
            return eid
        except Exception:
            for dest in copied: dest.unlink(missing_ok=True)
            raise
    def list(self, query='', descending=True):
        order='DESC' if descending else 'ASC'
        rows=self.db.execute(f'''SELECT * FROM entries ORDER BY COALESCE(event_at,recorded_at) {order}''').fetchall()
        result=[]
        for row in rows:
            e=dict(row); e['ai_notes']=json.loads(e['ai_notes']); e['files']=[dict(r) for r in self.db.execute('SELECT * FROM files WHERE entry_id=? AND active=1 ORDER BY added_at,id',(e['id'],))]
            e['addenda']=[dict(r) for r in self.db.execute('SELECT * FROM addenda WHERE entry_id=? ORDER BY recorded_at,rowid',(e['id'],))]
            e['revisions']=[dict(r) for r in self.db.execute('SELECT * FROM revisions WHERE entry_id=? ORDER BY edited_at,rowid',(e['id'],))]
            searchable=' '.join(str(v) for v in row)+' '+ ' '.join(f['name'] for f in e['files'])+' '+ ' '.join(a['text'] for a in e['addenda'])+' '+ ' '.join(r['before_json']+' '+r['after_json'] for r in e['revisions'])
            if query.casefold() in searchable.casefold(): result.append(e)
        return result
    @staticmethod
    def snapshot(entry):
        result={k:entry[k] for k in ('title','event_at','certainty','source','facts','notes')}
        result['ai_notes']=entry.get('ai_notes',{})
        result['screenshots']=[{k:f[k] for k in ('id','name','path','sha256')} for f in entry['files']]
        return result
    def edit(self, eid, title, event_at, certainty, source, facts, notes, paths, keep_ids, expected=None, ai_notes=None):
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
                records.append((fid,eid,original.name,rel,digest.hexdigest(),timestamp))
            after={'title':title,'event_at':event_at,'certainty':certainty,'source':source,'facts':facts,'notes':notes,
                   'screenshots':[{k:f[k] for k in ('id','name','path','sha256')} for f in current['files'] if f['id'] in keep_ids]}
            after['ai_notes']=current['ai_notes'] if ai_notes is None else ai_notes
            after['screenshots'] += [dict(zip(('id','name','path','sha256'),(r[0],r[2],r[3],r[4]))) for r in records]
            if before==after:
                self.db.rollback();return False
            self.db.execute('UPDATE entries SET title=?,event_at=?,certainty=?,source=?,facts=?,notes=? WHERE id=?',(title,event_at,certainty,source,facts,notes,eid))
            self.db.execute('UPDATE entries SET ai_notes=? WHERE id=?',(json.dumps(after['ai_notes'],ensure_ascii=False),eid))
            for fid in active-set(keep_ids):self.db.execute('UPDATE files SET active=0 WHERE id=?',(fid,))
            self.db.executemany('INSERT INTO files(id,entry_id,name,path,sha256,added_at) VALUES(?,?,?,?,?,?)',records)
            self.db.execute('INSERT INTO revisions VALUES(?,?,?,?,?)',(uuid.uuid4().hex,eid,timestamp,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False)))
            self.db.commit();return True
        except Exception:
            self.db.rollback()
            for path in copied:path.unlink(missing_ok=True)
            raise
    def amend(self, eid, text):
        with self.db: self.db.execute('INSERT INTO addenda VALUES(?,?,?,?)',(uuid.uuid4().hex,eid,text,now()))
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
                    z.writestr('audit-log.json',json.dumps({'version':1,'exported_at':now(),'entries':entries},ensure_ascii=False,indent=2))
                    # Include retired attachments referenced by revision history, too.
                    for f in self.db.execute('SELECT * FROM files'):
                        source=self.data/f['path']
                        if not source.is_file(): raise ValueError('Missing attachment: '+f['name'])
                        if hashlib.sha256(source.read_bytes()).hexdigest()!=f['sha256']: raise ValueError('Attachment has changed: '+f['name'])
                        z.write(source,'data/'+f['path'])
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
                        self.db.execute('INSERT INTO files(id,entry_id,name,path,sha256,added_at) VALUES(?,?,?,?,?,?)',(fid,e['id'],f['name'],rel,hashlib.sha256(content).hexdigest(),e['recorded']))
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
        self.event=QDateTimeEdit(QDateTime.currentDateTime());self.event.setCalendarPopup(True);self.event.setKeyboardTracking(False);self.event.setDisplayFormat('yyyy-MM-dd hh:mm:ss AP');form.addRow('Event date and time  ·  local time',self.event)
        self.certainty=QComboBox();self.certainty.addItems(['Exact as reported','Estimated','Unknown']);self.certainty.currentTextChanged.connect(lambda s:self.event.setEnabled(s!='Unknown'));form.addRow('Time certainty',self.certainty)
        self.source=QLineEdit();self.source.setPlaceholderText('Document, URL, person, device, or timestamp context');form.addRow('Source and context',self.source)
        self.facts=QTextEdit();self.facts.setAcceptRichText(False);self.facts.setPlaceholderText('What you directly saw, heard, or received');self.facts.setMinimumHeight(110);form.addRow('Factual description',self.facts)
        self.notes=QTextEdit();self.notes.setAcceptRichText(False);self.notes.setPlaceholderText('Explanation, uncertainties, and follow-up');self.notes.setMinimumHeight(90);form.addRow('Notes and explanation  ·  optional',self.notes)
        self.ai_fields={};ai_notes_widget=QWidget();ai_layout=QVBoxLayout(ai_notes_widget);ai_layout.setContentsMargins(0,0,0,0);ai_layout.setSpacing(8)
        for provider,color in (('Gemini','#b6a3ed'),('ChatGPT','#8bcbb0'),('Grok','#edbd83')):
            ai_layout.addWidget(plain(provider,f'color:{color};font-weight:700;font-size:12px;'))
            editor=QTextEdit();editor.setAcceptRichText(False);editor.setFixedHeight(76)
            editor.setStyleSheet(f'border:1px solid {color};border-radius:6px;padding:7px;')
            editor.setPlaceholderText(f'Add {provider} notes…')
            self.ai_fields[provider]=editor;ai_layout.addWidget(editor)
        form.addRow('AI cross check notes',ai_notes_widget)
        layout.addLayout(form)
        row=QHBoxLayout();row.addWidget(button('+ Attach screenshots',self.attach,True));row.addWidget(button('Remove selected',self.remove,True));layout.addLayout(row)
        self.files=QListWidget();self.files.setMaximumHeight(95);layout.addWidget(self.files)
        layout.addWidget(plain('Screenshot copies are saved locally. Edits retain previous values and removed screenshots in the history.','color:#a4aaaf;font-size:11px;'))
        scroll.setWidget(body);outer.addWidget(scroll)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);outer.addWidget(buttons)
        if entry:
            self.setWindowTitle('Edit audit entry')
            self.title.setText(entry['title']);self.source.setText(entry['source'])
            self.facts.setPlainText(entry['facts']);self.notes.setPlainText(entry['notes'])
            for provider,editor in self.ai_fields.items():editor.setPlainText(entry.get('ai_notes',{}).get(provider,''))
            if entry['event_at']:
                self.event.setDateTime(QDateTime.fromSecsSinceEpoch(int(datetime.fromisoformat(entry['event_at']).timestamp())))
            self.certainty.setCurrentText(entry['certainty'])
            self.existing_files=list(entry['files'])
            for f in self.existing_files:self.files.addItem(f['name']+'  (saved)')

    def attach(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Attach screenshots','','Images (*.png *.jpg *.jpeg *.webp *.bmp)')
        for path in paths:
            if path not in self.paths:
                if QPixmap(path).isNull(): QMessageBox.warning(self,'Invalid image',f'Cannot read {Path(path).name}');continue
                self.paths.append(path); self.files.addItem(Path(path).name)
    def remove(self):
        i=self.files.currentRow()
        if i>=0:
            if i<len(self.existing_files):self.existing_files.pop(i)
            else:self.paths.pop(i-len(self.existing_files))
            self.files.takeItem(i)
    def validate(self):
        if not self.title.text().strip() or not self.facts.toPlainText().strip():
            QMessageBox.warning(self,'Missing information','Enter a title and factual description.');return
        self.accept()
    def ai_values(self):
        return {provider:editor.toPlainText().strip() for provider,editor in self.ai_fields.items() if editor.toPlainText().strip()}
    def values(self):
        event=None if self.certainty.currentText()=='Unknown' else datetime.fromtimestamp(self.event.dateTime().toSecsSinceEpoch()).astimezone().isoformat(timespec='seconds')
        if self.entry and self.entry['event_at'] and event and datetime.fromisoformat(event)==datetime.fromisoformat(self.entry['event_at']):event=self.entry['event_at']
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

        tools=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Search notes, titles, sources, and evidence…');self.search.textChanged.connect(self.refresh);tools.addWidget(self.search,1)
        self.sort=QComboBox();self.sort.addItems(['Newest event first','Oldest event first']);self.sort.currentIndexChanged.connect(self.refresh);tools.addWidget(self.sort)
        tools.addWidget(button('Export backup',self.backup,True));tools.addWidget(button('More',self.more,True));outer.addLayout(tools)
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
        rows=self.store.list(self.search.text(),self.sort.currentIndex()==0)
        total=self.store.db.execute('SELECT count(*) FROM entries').fetchone()[0]
        self.count.setText(f'{total} entries  ·  {len(rows)} shown                                      EVENT TIMELINE')
        body=QWidget();layout=QVBoxLayout(body);layout.setContentsMargins(0,5,5,5);layout.setSpacing(0)
        if not rows:
            layout.addSpacing(70);layout.addWidget(plain('◇','font-size:40px;color:#a4b19f;'),0,Qt.AlignmentFlag.AlignHCenter)
            layout.addWidget(plain('Your record starts here' if total==0 else 'No matching entries','font-size:21px;font-weight:700;'),0,Qt.AlignmentFlag.AlignHCenter)
            layout.addWidget(plain('Add an event, write what happened, and attach its screenshots.','color:#a4aaaf;'),0,Qt.AlignmentFlag.AlignHCenter)
            if not total: layout.addWidget(button('+ Create your first entry',self.new_entry),0,Qt.AlignmentFlag.AlignHCenter)
        for e in rows:layout.addWidget(self.card(e))
        layout.addStretch();self.scroll.setWidget(body)
    def card(self,e):
        container=QWidget();row=QHBoxLayout(container);row.setContentsMargins(0,0,0,0);row.setSpacing(15)
        rail=QWidget();rail.setFixedWidth(24);rl=QVBoxLayout(rail);rl.setContentsMargins(0,4,0,0);rl.setSpacing(6);rl.addWidget(plain('◇','font-family:Segoe UI Symbol;font-size:20px;color:#e3e7e9;'),0,Qt.AlignmentFlag.AlignHCenter);line=QFrame();line.setFrameShape(QFrame.Shape.VLine);line.setStyleSheet('color:#485057;');rl.addWidget(line,1,Qt.AlignmentFlag.AlignHCenter);row.addWidget(rail)
        content=QWidget();l=QVBoxLayout(content);l.setContentsMargins(0,0,0,28);l.setSpacing(8)
        l.addWidget(plain(e['title'],'font-weight:700;font-size:14px;'))
        when='Event time unknown' if not e['event_at'] else display_time(e['event_at'])
        if e['certainty']=='Estimated':when+='  ·  Estimated'
        l.addWidget(plain(when,'font-size:12px;color:#dde1e3;'))
        l.addWidget(plain(e['id']+('  ·  '+e['source'] if e['source'] else ''),'font-size:10px;color:#929da5;'))
        l.addSpacing(4);l.addWidget(plain(e['facts'],'font-size:13px;'))
        if e['notes']:
            l.addWidget(plain('Notes and explanation','font-size:12px;font-weight:700;'))
            note=plain(e['notes']);note.setStyleSheet('background:#2d3134;border:1px solid #41474c;border-radius:7px;padding:13px;font-size:13px;');l.addWidget(note)
        if any(e.get('ai_notes',{}).values()):
            l.addWidget(plain('AI cross check notes','font-size:12px;font-weight:700;'))
            for provider,color,bg,border in (('Gemini','#c9b9f3','#302b3b','#514364'),('ChatGPT','#a1ddbf','#263830','#3f6350'),('Grok','#f0ce9f','#3b3227','#67543a')):
                value=e['ai_notes'].get(provider,'').strip()
                if not value:continue
                card=QFrame();card.setObjectName('providerNote');card.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Maximum)
                card.setStyleSheet(f'QFrame#providerNote{{background:{bg};border:1px solid {border};border-radius:7px;}}')
                note_layout=QVBoxLayout(card);note_layout.setContentsMargins(12,8,12,9);note_layout.setSpacing(4)
                note_layout.addWidget(plain(provider,f'background:transparent;color:{color};font-size:11px;font-weight:700;'))
                note_text=plain(value,'background:transparent;color:#e6e7e8;font-size:12px;')
                note_text.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
                note_layout.addWidget(note_text);l.addWidget(card)
        for f in e['files']:
            path=self.store.data/f['path'];thumb=QPixmap(str(path));image=QPushButton();image.setProperty('secondary',True);image.setFixedSize(240,145)
            if not thumb.isNull():
                from PySide6.QtGui import QIcon
                image.setIcon(QIcon(thumb));image.setIconSize(image.size()*0.92)
            else:image.setText('Image unavailable')
            image.clicked.connect(lambda checked=False,p=path,n=f['name']:ImageDialog(p,n,self).exec());l.addWidget(image)
            l.addWidget(plain(f['name']+'  ·  attached '+display_time(f['added_at']),'font-size:10px;color:#a4aaaf;'))
            hashlabel=plain('SHA 256  '+f['sha256'],'font-size:9px;color:#8f989f;');l.addWidget(hashlabel)
        for a in e['addenda']:
            l.addWidget(plain('ADDENDUM  ·  '+display_time(a['recorded_at']),'color:#b7c6b3;font-size:10px;'));l.addWidget(plain(a['text']))
        bottom=QHBoxLayout();bottom.addWidget(plain('Recorded '+display_time(e['recorded_at']),'color:#929da5;font-size:10px;'));bottom.addStretch();bottom.addWidget(button('Edit entry',lambda checked=False,entry=e:self.edit_entry(entry),True));bottom.addWidget(button('+ Add correction or note',lambda checked=False,eid=e['id']:self.amend(eid),True));l.addLayout(bottom)
        if e['revisions']:
            fields=set()
            for revision in e['revisions']:
                before=json.loads(revision['before_json']);after=json.loads(revision['after_json'])
                fields.update(k for k in before if before[k]!=after[k])
            names={'title':'Title','event_at':'Event timestamp','certainty':'Time certainty','source':'Source and context','facts':'Factual description','notes':'Notes and explanation','screenshots':'Screenshots','ai_notes':'AI cross check notes'}
            summary='Edited '+display_time(e['revisions'][-1]['edited_at'])+'  ·  '+str(len(e['revisions']))+' saved edit(s)'
            l.addWidget(plain(summary,'color:#d3c99f;font-size:11px;'))
            l.addWidget(plain('Changed: '+', '.join(names[k] for k in names if k in fields),'color:#a4aaaf;font-size:11px;'))
            l.addWidget(button('View edit history',lambda checked=False,entry=e:self.history(entry),True),0,Qt.AlignmentFlag.AlignLeft)
        row.addWidget(content,1);return container
    def edit_entry(self,entry):
        dialog=EntryDialog(self,entry)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            try:
                changed=self.store.edit(entry['id'],*dialog.values(),[f['id'] for f in dialog.existing_files],expected=self.store.snapshot(entry),ai_notes=dialog.ai_values())
                self.refresh();self.status.setText('Changes saved with edit history  ·  '+display_time(now()) if changed else 'No changes to save.')
            except Exception as e:QMessageBox.critical(self,'Could not save changes',str(e))
    def history(self,entry):
        d=QDialog(self);d.setWindowTitle('Edit history — '+entry['title']);d.resize(780,700)
        outer=QVBoxLayout(d);outer.addWidget(plain('Edit history','font-size:22px;font-weight:700;'))
        outer.addWidget(plain('Original recorded time: '+display_time(entry['recorded_at']),'color:#a4aaaf;'))
        scroll=QScrollArea();scroll.setWidgetResizable(True);body=QWidget();layout=QVBoxLayout(body)
        names={'title':'Title','event_at':'Event timestamp','certainty':'Time certainty','source':'Source and context','facts':'Factual description','notes':'Notes and explanation','screenshots':'Screenshots','ai_notes':'AI cross check notes'}
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
                    layout.addWidget(plain('Before: '+text(before[key]),'background:#2d3134;padding:10px;border-radius:5px;'))
                    layout.addWidget(plain('After: '+text(after[key]),'background:#303a31;padding:10px;border-radius:5px;'))
            layout.addSpacing(20)
        scroll.setWidget(body);outer.addWidget(scroll);outer.addWidget(button('Close',d.accept,True));d.exec()
    def new_entry(self):
        dialog=EntryDialog(self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            try:self.store.add(*dialog.values(),ai_notes=dialog.ai_values());self.refresh();self.status.setText('Entry saved  ·  '+display_time(now()))
            except Exception as e:QMessageBox.critical(self,'Could not save',str(e))
    def amend(self,eid):
        d=QDialog(self);d.setWindowTitle('Add a correction or note');d.resize(540,340);l=QVBoxLayout(d);l.addWidget(plain('The original entry stays visible. Your addition receives its own timestamp.'));text=QTextEdit();text.setAcceptRichText(False);l.addWidget(text);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);l.addWidget(buttons);buttons.accepted.connect(lambda:d.accept() if text.toPlainText().strip() else None);buttons.rejected.connect(d.reject)
        if d.exec()==QDialog.DialogCode.Accepted:
            try:self.store.amend(eid,text.toPlainText().strip());self.refresh();self.status.setText('Addendum saved  ·  '+display_time(now()))
            except Exception as e:QMessageBox.critical(self,'Could not save',str(e))
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



