import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from phase6.editor_app import OCRDocumentEditor


def _document():
    return {"blocks": [{"type": "heading", "text": "标题"}]}


class TestOCRDocumentEditor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_loads_document_and_populates_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "document.json"
            path.write_text(json.dumps(_document(), ensure_ascii=False), encoding="utf-8")
            window = OCRDocumentEditor(path)
            self.assertEqual(window.block_list.count(), 1)
            self.assertEqual(window.block_list.item(0).text(), "1: heading  标题")
            self.assertIn("标题", window.editor.toPlainText())
            window.close()


if __name__ == "__main__":
    unittest.main()
