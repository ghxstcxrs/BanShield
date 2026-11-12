import json,os,uuid
from pathlib import Path
from policy_files import read_policy,import_policy,validate_policy,policy_path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QThread,Signal
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTextEdit,QTabWidget,QLineEdit,QCheckBox,QFileDialog,QMessageBox,QComboBox
from analysis_backend import build_manifest,analyze,save_findings,SCHEMA
class Job(QThread):
    done=Signal(object);failed=Signal(str)
    def __init__(self,fn,parent):super().__init__(parent);self.fn=fn
    def run(self):
        try:self.done.emit(self.fn())
        except Exception as e:self.failed.emit(str(e))
class AnalysisDialog(QDialog):
    def __init__(self,data_dir,root,parent):
        super().__init__(parent);self.data_dir=Path(data_dir);self.root=Path(root);self.setWindowTitle('BanShield — text evidence analysis');self.resize(1000,800);self.job=None;self.result=None
        layout=QVBoxLayout(self);notice=QLabel('Build locally, review/redact the text, then explicitly send. No image bytes, original emails or HAR files are sent. OCR and header clocks are unverified. API use may incur charges.');notice.setWordWrap(True);layout.addWidget(notice)
        actions=QHBoxLayout();self.buttons=[]
        for name,fn in [('Build / update manifest',self.build),('Open policy folder',self.open_policy_folder),('Reload policy file',self.refresh),('Import manual policy',self.load_policy),('Save reviewed bundle',self.export)]:
            b=QPushButton(name);b.clicked.connect(fn);actions.addWidget(b);self.buttons.append(b)
        layout.addLayout(actions);self.include_bodies=QCheckBox('Include HAR response bodies in manifest (may contain secrets; review before sending)');layout.addWidget(self.include_bodies);tabs=QTabWidget();self.policy=QTextEdit();self.manifest=QTextEdit();self.findings=QTextEdit();self.findings.setReadOnly(True)
        for label,editor in [('Policy baseline',self.policy),('Evidence manifest',self.manifest),('Findings',self.findings)]:editor.setAcceptRichText(False);tabs.addTab(editor,label)
        layout.addWidget(tabs,1)
        self.policy.setReadOnly(True)
        try:self.policy.setPlainText(read_policy(self.root))
        except ValueError as e:self.policy.setPlaceholderText(str(e))
        self.policy.textChanged.connect(self.invalidate_review);self.manifest.textChanged.connect(self.invalidate_review)
        row=QHBoxLayout();row.addWidget(QLabel('Provider:'));self.provider=QComboBox();self.provider.addItem('OpenAI','openai');self.provider.addItem('Google / Gemini','gemini');row.addWidget(self.provider);row.addWidget(QLabel('Model ID:'));self.model=QLineEdit(os.environ.get('BANSHIELD_OPENAI_MODEL',''));self.model.setPlaceholderText('Structured Outputs-capable model available to your API account');row.addWidget(self.model);layout.addLayout(row)
        self.consent=QCheckBox('I reviewed both documents and authorize sending this text to the selected API provider.');layout.addWidget(self.consent)
        self.send=QPushButton('Send reviewed text for structured analysis');self.send.clicked.connect(self.send_analysis);layout.addWidget(self.send)
        self.status=QLabel('');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.models={'openai':os.environ.get('BANSHIELD_OPENAI_MODEL',''),'gemini':os.environ.get('BANSHIELD_GEMINI_MODEL','')};self.active_provider='openai'
        self.provider.currentIndexChanged.connect(self.provider_changed);self.model.textChanged.connect(self.invalidate_review);self.provider_changed()
    def provider_changed(self,*args):
        self.models[self.active_provider]=self.model.text();self.active_provider=self.provider.currentData()
        self.model.setText(self.models[self.active_provider]);self.model.setPlaceholderText('Enter a JSON Schema-capable '+self.provider.currentText()+' model ID')
        self.invalidate_review();self.status.setText('Selected: '+self.provider.currentText()+' · Set '+('OPENAI_API_KEY' if self.active_provider=='openai' else 'GEMINI_API_KEY (or GOOGLE_API_KEY)')+' before launching. No automatic provider fallback. Review that provider’s data-use terms.')
    def invalidate_review(self):
        self.result=None
        if hasattr(self,'consent'):self.consent.setChecked(False)
    def busy(self,value):
        for b in self.buttons+[self.send,self.provider,self.model]:b.setDisabled(value)
    def run_job(self,fn,callback):
        self.busy(True);self.job=Job(fn,self)
        self.job.done.connect(callback);self.job.failed.connect(lambda error:QMessageBox.warning(self,'Analysis task failed',error))
        self.job.finished.connect(lambda:self.busy(False));self.job.start()
    def build(self):
        self.status.setText('Building text manifest and cached local OCR…')
        def done(manifest):self.manifest.setPlainText(json.dumps(manifest,ensure_ascii=False,indent=2));self.consent.setChecked(False);self.status.setText('Manifest built locally. Review OCR accuracy and remove private details before sending.')
        include=self.include_bodies.isChecked()
        self.run_job(lambda:build_manifest(self.data_dir,include_response_bodies=include),done)
    def open_policy_folder(self):
        folder=self.root/'policies';folder.mkdir(exist_ok=True);QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
    def refresh(self):
        try:
            self.policy.setPlainText(read_policy(self.root));self.consent.setChecked(False);self.status.setText('Loaded manual policy: '+str(policy_path(self.root)))
        except Exception as e:
            self.policy.clear();self.policy.setPlaceholderText(str(e));self.consent.setChecked(False);QMessageBox.warning(self,'Manual policy required',str(e))
    def load_policy(self):
        path,_=QFileDialog.getOpenFileName(self,'Import completed manual policy','','UTF-8 policy text (*.txt)')
        if not path:return
        try:self.policy.setPlainText(import_policy(self.root,path));self.consent.setChecked(False);self.status.setText('Manual policy validated and copied to '+str(policy_path(self.root)))
        except Exception as e:QMessageBox.warning(self,'Invalid policy file',str(e))
    def reviewed(self):
        manifest=json.loads(self.manifest.toPlainText())
        if not isinstance(manifest,dict) or manifest.get('format')!='banshield-evidence-manifest' or not isinstance(manifest.get('entries'),list):raise ValueError('Build a valid evidence manifest first.')
        policy=self.policy.toPlainText()
        validate_policy(policy)
        if read_policy(self.root)!=policy:raise ValueError('Policy file changed on disk. Reload it and review again before continuing.')
        return policy,manifest
    def export(self):
        try:policy,manifest=self.reviewed()
        except Exception as e:QMessageBox.warning(self,'Cannot export',str(e));return
        folder=QFileDialog.getExistingDirectory(self,'Choose private bundle destination')
        if not folder:return
        target=Path(folder)/('banshield-review-'+uuid.uuid4().hex[:8]);target.mkdir()
        (target/'roblox_tos_and_policies.txt').write_text(policy,encoding='utf-8');(target/'evidence_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');(target/'findings.schema.json').write_text(json.dumps(SCHEMA,indent=2),encoding='utf-8')
        if self.result:save_findings(target,self.result,policy=policy,manifest=manifest)
        self.status.setText('Private reviewed bundle saved: '+str(target))
    def send_analysis(self):
        if not self.consent.isChecked():QMessageBox.warning(self,'Review required','Review both text documents and confirm API submission.');return
        try:
            policy,manifest=self.reviewed();model=self.model.text().strip();provider=self.provider.currentData();key=os.environ.get('OPENAI_API_KEY','') if provider=='openai' else (os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY',''))
            if not key or not model:raise ValueError('Set the selected provider’s API key before launching and enter a model ID. No request was sent.')
        except Exception as e:QMessageBox.warning(self,'Cannot send',str(e));return
        self.status.setText('Sending text only to '+self.provider.currentText()+'; waiting for validated findings…')
        def done(result):
            self.result=result;display=json.loads(json.dumps(result));display['findings']['summary']='Filtered rubric view. Full model output is retained in findings.json.';display['findings']['findings']=[f for f in display['findings']['findings'] if f.get('included_in_report',False)];self.findings.setPlainText(json.dumps(display,ensure_ascii=False,indent=2))
            target=self.data_dir/'analysis'/uuid.uuid4().hex;target.mkdir(parents=True)
            try:integrity=save_findings(target,result,policy=policy,manifest=manifest,data_dir=self.data_dir)
            except Exception as e:
                self.result=None;QMessageBox.critical(self,'Analysis persistence failed',str(e));return
            self.status.setText('Saved audit_report.json · SHA-256 '+integrity['report_sha256']+' · '+str(target))
        self.run_job(lambda:analyze(policy,manifest,model,key,provider=provider),done)
    def reject(self):
        if self.job and self.job.isRunning():QMessageBox.information(self,'Task running','Wait for the local task or API request to finish before closing.');return
        super().reject()
