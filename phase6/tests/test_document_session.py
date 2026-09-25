import json
import tempfile
import unittest
from pathlib import Path

from phase6.document_session import DocumentSession


def _document(text="题目"):
    return {
        "schema_version": "1.0",
        "blocks": [
            {"type": "heading", "text": "标题"},
            {"type": "paragraph", "runs": [{"kind": "text", "text": text}]},
        ],
    }


class TestDocumentSession(unittest.TestCase):
    def test_load_and_summarize_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.json"
            source.write_text(json.dumps(_document(), ensure_ascii=False), encoding="utf-8")
            session = DocumentSession()
            session.load(source)
            self.assertEqual(session.validation_messages(), [])
            self.assertEqual(session.block_summaries(), ["1: heading  标题", "2: paragraph  题目"])

    def test_invalid_json_cannot_be_saved(self):
        session = DocumentSession()
        session.raw_text = "{"
        self.assertTrue(session.validation_messages()[0].startswith("JSON 格式错误"))
        with self.assertRaisesRegex(ValueError, "无法保存"):
            session.save("ignored.json")

    def test_save_writes_valid_edited_document(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "edited.json"
            session = DocumentSession()
            session.raw_text = json.dumps(_document("已编辑"), ensure_ascii=False)
            self.assertEqual(session.save(target), target)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["blocks"][1]["runs"][0]["text"], "已编辑")


if __name__ == "__main__":
    unittest.main()
