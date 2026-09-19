import ctypes
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from paste_claude import __main__ as app


class ClipboardTests(unittest.TestCase):
    def test_image_saved_without_clipboard_mutation(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(app.ImageGrab, 'grabclipboard', return_value=Image.new('RGB', (2, 2), 'red')), \
                patch.object(app.tempfile, 'gettempdir', return_value=directory), \
                patch.object(app, 'user32') as clipboard:
            path = app.process_clipboard()
            with Image.open(path) as saved:
                self.assertEqual(saved.getpixel((0, 0)), (255, 0, 0))
            self.assertEqual(clipboard.mock_calls, [])

    def test_file_list_and_empty_clipboard_are_ignored(self):
        for value in (None, ['image.png']):
            with patch.object(app.ImageGrab, 'grabclipboard', return_value=value):
                self.assertIsNone(app.process_clipboard())

    def test_browser_is_not_a_terminal(self):
        for name, expected in [('Chrome_WidgetWin_1', False), ('MozillaWindowClass', False),
                               ('ConsoleWindowClass', True), ('CASCADIA_HOSTING_WINDOW', True)]:
            def get_class(hwnd, output, size):
                output.value = name
                return len(name)
            with patch.object(app.user32, 'GetClassNameW', side_effect=get_class):
                self.assertEqual(app.is_terminal(123), expected)

    def test_paste_shortcuts(self):
        for key, held, expected in [(0x56, {0x11}, True), (0x56, {0x11, 0x10}, True),
                                    (0x2D, {0x10}, True), (0x56, set(), False),
                                    (0x56, {0x11, 0x12}, False)]:
            with patch.object(app, 'key_down', side_effect=lambda k: k in held):
                self.assertEqual(app.is_paste(key), expected)

    def test_focus_or_clipboard_change_cancels_paste(self):
        for foreground, sequence in [(999, 42), (123, 43)]:
            with patch.object(app, 'key_down', return_value=False), \
                    patch.object(app.user32, 'GetForegroundWindow', return_value=foreground), \
                    patch.object(app.user32, 'GetClipboardSequenceNumber', return_value=sequence), \
                    patch.object(app, 'process_clipboard') as save, \
                    patch.object(app, 'send_text') as send:
                app.paste_image(123, 42)
                save.assert_not_called()
                send.assert_not_called()

    def test_path_is_quoted_and_never_submitted(self):
        with patch.object(app, 'key_down', return_value=False), \
                patch.object(app.user32, 'GetForegroundWindow', return_value=123), \
                patch.object(app.user32, 'GetClipboardSequenceNumber', return_value=42), \
                patch.object(app, 'process_clipboard', return_value=r'C:\User Name\image.png'), \
                patch.object(app, 'send_text') as send:
            app.paste_image(123, 42)
            send.assert_called_once_with('"C:\\User Name\\image.png" ')

    def test_unicode_input_layout_and_key_pairs(self):
        self.assertEqual(ctypes.sizeof(app.Input), 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
        with patch.object(app.user32, 'SendInput', return_value=4) as send:
            app.send_text('A\u00e9')
            count, events, size = send.call_args.args
            self.assertEqual(count, 4)
            self.assertEqual([event.ki.wScan for event in events], [65, 65, 233, 233])
            self.assertEqual([event.ki.dwFlags for event in events], [4, 6, 4, 6])

    def test_blocked_input_is_reported(self):
        with patch.object(app.user32, 'SendInput', return_value=0):
            with self.assertRaises(OSError):
                app.send_text('path')

    def test_startup_uses_hidden_python_and_absolute_script(self):
        command = app.background_command()
        self.assertEqual(Path(command[0]).name, 'pythonw.exe')
        self.assertTrue(Path(command[1]).is_absolute())
        self.assertEqual(command[2], '--worker')


if __name__ == '__main__':
    unittest.main()
