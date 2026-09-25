import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit

from phase6.main_window import FurtherEvolutionMainWindow, configure_application_font


class TestFurtherEvolutionMainWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_initial_form_does_not_contain_an_api_key(self):
        window = FurtherEvolutionMainWindow()
        self.assertEqual(window.api_key_input.text(), "")
        self.assertEqual(window.api_key_input.echoMode(), QLineEdit.EchoMode.Password)
        self.assertTrue(window.output_input.text().endswith("output"))
        self.assertFalse(window.open_editor_button.isEnabled())
        window.close()

    def test_configures_a_font_family(self):
        self.assertTrue(configure_application_font(self.app))


if __name__ == "__main__":
    unittest.main()
