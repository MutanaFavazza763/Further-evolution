"""面向用户的 OCR2Word 主窗口。"""

import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from phase6.editor_app import OCRDocumentEditor
from phase6.processing import ProcessingRequest, process_request


def configure_application_font(app):
    """为 Windows 桌面 UI 选择可显示中文的字体，不打包字体文件。"""
    preferred_families = ("Microsoft YaHei UI", "Microsoft YaHei")
    available = set(QFontDatabase.families())
    if not any(family in available for family in preferred_families) and sys.platform == "win32":
        QFontDatabase.addApplicationFont(r"C:\Windows\Fonts\msyh.ttc")
        available = set(QFontDatabase.families())
    family = next((name for name in preferred_families if name in available), app.font().family())
    app.setFont(QFont(family, 10))
    return family


class ProcessingWorker(QObject):
    """在后台线程执行可能耗时的网络 OCR。"""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, request):
        super().__init__()
        self.request = request

    def run(self):
        try:
            result = process_request(self.request)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        if result.status in ("success", "skipped_duplicate") and result.output_json:
            self.completed.emit(result)
        else:
            self.failed.emit(result.error or "处理未完成：{}".format(result.status))


class OCR2WordMainWindow(QMainWindow):
    """选择图片、配置临时 AI 凭据并启动 OCR 的主窗口。"""

    def __init__(self):
        super().__init__()
        configure_application_font(QApplication.instance())
        self.latest_json = None
        self.editor_windows = []
        self.worker_thread = None
        self.worker = None
        self.setWindowTitle("OCR2Word")
        self.resize(860, 670)
        self._build_ui()

    def _path_row(self, placeholder, chooser):
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        button = QPushButton("浏览…")
        button.clicked.connect(chooser)
        row = QHBoxLayout()
        row.addWidget(field)
        row.addWidget(button)
        return field, row

    def _build_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("OCR2Word")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        subtitle = QLabel("选择一张图片，填写本次使用的模型配置，即可生成可编辑 Word。")
        subtitle.setStyleSheet("color: #5f6368;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        files_box = QGroupBox("1. 选择文件")
        files_form = QFormLayout(files_box)
        self.image_input, image_row = self._path_row("选择 jpg、png、webp 等图片", self.choose_image)
        self.output_input, output_row = self._path_row("选择生成 JSON 和 DOCX 的文件夹", self.choose_output_directory)
        self.output_input.setText(str(Path.cwd() / "output"))
        files_form.addRow("输入图片", image_row)
        files_form.addRow("输出目录", output_row)
        self.reflow_checkbox = QCheckBox("竖转横：生成 16:9 横向多栏 Word（不勾选则为竖向）")
        files_form.addRow("排版方式", self.reflow_checkbox)
        layout.addWidget(files_box)

        ai_box = QGroupBox("2. 本次 AI 配置")
        ai_form = QFormLayout(ai_box)
        self.endpoint_input = QLineEdit("https://api.deepseek.com")
        self.model_input = QLineEdit("deepseek-flash")
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("仅用于本次处理，不会保存到磁盘")
        self.api_key_input.setClearButtonEnabled(True)
        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(5, 600)
        self.timeout_input.setValue(120)
        self.timeout_input.setSuffix(" 秒")
        self.retry_input = QSpinBox()
        self.retry_input.setRange(0, 5)
        self.retry_input.setValue(2)
        ai_form.addRow("API Endpoint", self.endpoint_input)
        ai_form.addRow("模型名称", self.model_input)
        ai_form.addRow("API Key", self.api_key_input)
        ai_form.addRow("超时时间", self.timeout_input)
        ai_form.addRow("重试次数", self.retry_input)
        layout.addWidget(ai_box)

        notice = QLabel("安全说明：API Key 不会写入配置、日志或项目文件；关闭或完成处理后将从界面清除。")
        notice.setWordWrap(True)
        notice.setStyleSheet("padding: 10px; background: #eef5ff; color: #245a92; border-radius: 4px;")
        layout.addWidget(notice)

        actions = QHBoxLayout()
        self.process_button = QPushButton("开始识别并生成 Word")
        self.process_button.setDefault(True)
        self.process_button.clicked.connect(self.start_processing)
        self.open_editor_button = QPushButton("打开结果编辑器")
        self.open_editor_button.setEnabled(False)
        self.open_editor_button.clicked.connect(self.open_editor)
        actions.addWidget(self.process_button)
        actions.addWidget(self.open_editor_button)
        actions.addStretch()
        layout.addLayout(actions)

        log_box = QGroupBox("处理状态")
        log_layout = QVBoxLayout(log_box)
        self.status_label = QLabel("等待选择图片")
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(100)
        self.log_output.setMaximumHeight(110)
        log_layout.addWidget(self.status_label)
        log_layout.addWidget(self.log_output)
        layout.addWidget(log_box)
        self.setCentralWidget(central)

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择输入图片",
            self.image_input.text(),
            "图片 (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.gif)",
        )
        if path:
            self.image_input.setText(path)

    def choose_output_directory(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_input.text())
        if path:
            self.output_input.setText(path)

    def _request_from_form(self):
        return ProcessingRequest(
            image_path=Path(self.image_input.text().strip()),
            output_dir=Path(self.output_input.text().strip()),
            api_key=self.api_key_input.text(),
            base_url=self.endpoint_input.text().strip(),
            model=self.model_input.text().strip(),
            timeout=self.timeout_input.value(),
            max_retries=self.retry_input.value(),
            reflow=self.reflow_checkbox.isChecked(),
        )

    def _append_status(self, message):
        self.status_label.setText(message)
        self.log_output.appendPlainText(message)

    def start_processing(self):
        request = self._request_from_form()
        try:
            request.validate()
        except ValueError as exc:
            QMessageBox.warning(self, "请检查输入", str(exc))
            return

        self.process_button.setEnabled(False)
        self.open_editor_button.setEnabled(False)
        self._append_status("正在识别图片并生成 Word，请稍候…")
        self.worker_thread = QThread(self)
        self.worker = ProcessingWorker(request)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.completed.connect(self._processing_completed)
        self.worker.failed.connect(self._processing_failed)
        self.worker.completed.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self._processing_finished)
        self.worker_thread.start()

    def _processing_completed(self, result):
        self.latest_json = result.output_json
        self.open_editor_button.setEnabled(True)
        self._append_status("处理完成：已生成 {} 和 {}".format(result.output_json.name, result.output_docx.name))
        if result.error:
            self._append_status("警告：{}".format(result.error))

    def _processing_failed(self, message):
        self._append_status("处理失败：{}".format(message))
        QMessageBox.warning(self, "处理失败", message)

    def _processing_finished(self):
        self.process_button.setEnabled(True)
        self.api_key_input.clear()
        self.worker = None
        self.worker_thread = None

    def open_editor(self):
        if not self.latest_json:
            return
        editor = OCRDocumentEditor(self.latest_json)
        editor.show()
        self.editor_windows.append(editor)


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    configure_application_font(app)
    window = OCR2WordMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
