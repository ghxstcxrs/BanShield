"""Attachment drop target with explicit clipboard paste support."""
from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QListWidget

def local_paths(mime):
    return [u.toLocalFile() for u in mime.urls() if u.isLocalFile()] if mime.hasUrls() else []
class ScreenshotDropList(QListWidget):
    filesDropped=Signal(list)
    pasteRequested=Signal()
    def __init__(self):
        super().__init__();self.setAcceptDrops(True);self.viewport().setAcceptDrops(True)
        self.setToolTip('Drop image files here. Ctrl+V pastes a PNG/JPEG file or clipboard image as PNG.')
        self.setStyleSheet('QListWidget{border:1px dashed #72816e;border-radius:7px;padding:8px;min-height:65px;}')
    def dragEnterEvent(self,event):
        if local_paths(event.mimeData()):event.acceptProposedAction()
        else:event.ignore()
    def dragMoveEvent(self,event):
        if local_paths(event.mimeData()):event.acceptProposedAction()
        else:event.ignore()
    def dropEvent(self,event):
        paths=local_paths(event.mimeData())
        if paths:self.filesDropped.emit(paths);event.acceptProposedAction()
        else:event.ignore()
    def keyPressEvent(self,event):
        if event.matches(QKeySequence.StandardKey.Paste):self.pasteRequested.emit();event.accept()
        else:super().keyPressEvent(event)
