"""Phase 6 基础 OCRDocument 预览与编辑窗口。"""

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from phase6.document_session import DocumentSession


class OCRDocumentEditor(QMainWindow):
    """显示 OCRDocument block 摘要，并允许用户编辑原始 JSON。"""

    def __init__(self, path=None):
        super().__init__()
        self.session = DocumentSession()
        self.setWindowTitle("FurtherEvolution - OCRDocument 编辑器")
        self.resize(1100, 720)

        self.block_list = QListWidget()
        self.block_list.setAccessibleName("OCR block 预览")
        self.editor = QPlainTextEdit()
        self.editor.setAccessibleName("OCRDocument JSON 编辑器")
        self.editor.setPlaceholderText("打开 OCRDocument JSON 后即可编辑")
        self.editor.textChanged.connect(self._mark_modified)
        self.path_label = QLabel("未打开文件")

        buttons = QHBoxLayout()
        for label, callback in (
            ("打开 JSON", self.open_document),
            ("刷新预览", self.refresh_preview),
            ("校验", self.validate_document),
            ("另存为", self.save_as),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        buttons.addStretch()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Block 预览"))
        left_layout.addWidget(self.block_list)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("OCRDocument JSON"))
        right_layout.addWidget(self.editor)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([340, 760])

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.path_label)
        layout.addLayout(buttons)
        layout.addWidget(splitter)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

        if path:
            self.load_document(path)

    def _set_session_text(self):
        self.session.raw_text = self.editor.toPlainText()

    def _mark_modified(self):
        if self.session.path:
            self.statusBar().showMessage("内容已修改，尚未保存")

    def _show_error(self, message):
        self.statusBar().showMessage(message, 8000)
        QMessageBox.warning(self, "FurtherEvolution", message)

    def load_document(self, path):
        """加载指定 JSON 到编辑器和 block 预览。"""
        try:
            self.session.load(path)
        except ValueError as exc:
            self._show_error(str(exc))
            return False
        self.editor.blockSignals(True)
        self.editor.setPlainText(self.session.raw_text)
        self.editor.blockSignals(False)
        self.path_label.setText(str(self.session.path))
        self.refresh_preview(show_success=False)
        return True

    def open_document(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开 OCRDocument", "", "JSON 文件 (*.json)")
        if path:
            self.load_document(path)

    def refresh_preview(self, show_success=True):
        """用当前编辑内容刷新左侧 block 摘要。"""
        self._set_session_text()
        messages = self.session.validation_messages()
        self.block_list.clear()
        self.block_list.addItems(self.session.block_summaries())
        if messages:
            if show_success:
                self._show_error("校验失败：{}".format(messages[0]))
            return False
        if show_success:
            self.statusBar().showMessage("预览已刷新，共 {} 个 block".format(self.block_list.count()), 5000)
        return True

    def validate_document(self):
        self._set_session_text()
        messages = self.session.validation_messages()
        if messages:
            self._show_error("校验失败：{}".format(messages[0]))
            return False
        self.statusBar().showMessage("OCRDocument 校验通过", 5000)
        return True

    def save_as(self):
        self._set_session_text()
        default_path = str(self.session.path) if self.session.path else "OCRDocument.json"
        path, _ = QFileDialog.getSaveFileName(self, "保存 OCRDocument", default_path, "JSON 文件 (*.json)")
        if not path:
            return False
        try:
            saved_path = self.session.save(path)
        except ValueError as exc:
            self._show_error(str(exc))
            return False
        self.path_label.setText(str(saved_path))
        self.statusBar().showMessage("已保存：{}".format(saved_path), 5000)
        return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="FurtherEvolution OCRDocument 编辑器")
    parser.add_argument("json_path", nargs="?", help="可选：启动时加载的 OCRDocument JSON")
    args = parser.parse_args(argv)

    app = QApplication.instance() or QApplication(sys.argv)
    window = OCRDocumentEditor(Path(args.json_path) if args.json_path else None)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
