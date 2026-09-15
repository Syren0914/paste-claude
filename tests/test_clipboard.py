import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from paste_claude import __main__ as app


class ClipboardTests(unittest.TestCase):
    def test_default_saves_png_without_changing_clipboard(self):
        screenshot = Image.new("RGB", (2, 2), "red")
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(app.ImageGrab, "grabclipboard", return_value=screenshot), \
                    patch.object(app.tempfile, "gettempdir", return_value=directory), \
                    patch.object(app, "user32") as clipboard:
                filepath = app.process_clipboard()
                self.assertTrue(Path(filepath).is_file())
                with Image.open(filepath) as saved:
                    self.assertEqual(saved.getpixel((0, 0)), (255, 0, 0))
                self.assertEqual(clipboard.mock_calls, [])

    def test_unchanged_image_is_saved_only_once(self):
        with patch("sys.argv", ["paste-claude"]), \
                patch.object(app, "user32") as clipboard, \
                patch.object(app, "clipboard_has_image_only", return_value=True), \
                patch.object(app, "process_clipboard", return_value="image.png") as process, \
                patch.object(app.time, "sleep", side_effect=[None, KeyboardInterrupt]), \
                patch("builtins.print"):
            clipboard.GetClipboardSequenceNumber.return_value = 42
            app.main()
            process.assert_called_once_with(copy_path=False)

    def test_cli_mode_is_explicit_and_new_images_are_processed(self):
        with patch("sys.argv", ["paste-claude", "--copy-path"]), \
                patch.object(app, "user32") as clipboard, \
                patch.object(app, "clipboard_has_image_only", return_value=True), \
                patch.object(app, "process_clipboard", return_value="image.png") as process, \
                patch.object(app.time, "sleep", side_effect=[None, KeyboardInterrupt]), \
                patch("builtins.print"):
            clipboard.GetClipboardSequenceNumber.side_effect = [42, 43]
            app.main()
            self.assertEqual(process.call_count, 2)
            process.assert_called_with(copy_path=True)


if __name__ == "__main__":
    unittest.main()
