import argparse
import ctypes
import datetime
import os
import tempfile
import time
import uuid

from PIL import ImageGrab

# Windows clipboard format constants
CF_DIB = 8
CF_UNICODETEXT = 13
CF_HDROP = 15
GMEM_MOVEABLE = 0x0002

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Fix return/argument types for 64-bit pointer safety
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GlobalSize.restype = ctypes.c_size_t
kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
user32.GetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]


def clipboard_has_image_only():
    """True if clipboard has an image but no text or file list."""
    return bool(
        user32.IsClipboardFormatAvailable(CF_DIB)
        and not user32.IsClipboardFormatAvailable(CF_UNICODETEXT)
        and not user32.IsClipboardFormatAvailable(CF_HDROP)
    )


def process_clipboard(copy_path=False):
    """Save an image, optionally adding its path to the clipboard for CLI use.

    By default leave all clipboard formats untouched so web apps paste images.
    """
    img = ImageGrab.grabclipboard()
    if img is None:
        return None

    # Save to temp file
    temp_dir = os.path.join(tempfile.gettempdir(), "paste-claude")
    os.makedirs(temp_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    short_id = uuid.uuid4().hex[:6]
    filepath = os.path.join(temp_dir, f"clipboard_{timestamp}_{short_id}.png")
    img.save(filepath, "PNG")

    if not copy_path:
        return filepath

    # Read the raw DIB data so we can re-set it alongside the text
    if not user32.OpenClipboard(0):
        return filepath

    try:
        handle = user32.GetClipboardData(CF_DIB)
        if not handle:
            return filepath

        size = kernel32.GlobalSize(handle)
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return filepath
        dib_data = ctypes.string_at(ptr, size)
        kernel32.GlobalUnlock(handle)

        # Clear clipboard and re-set both image + text
        user32.EmptyClipboard()

        # Re-set the image (CF_DIB)
        h_dib = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(dib_data))
        p = kernel32.GlobalLock(h_dib)
        ctypes.memmove(p, dib_data, len(dib_data))
        kernel32.GlobalUnlock(h_dib)
        user32.SetClipboardData(CF_DIB, h_dib)

        # Add the file path as text (CF_UNICODETEXT)
        encoded = filepath.encode("utf-16-le") + b"\x00\x00"
        h_text = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        p = kernel32.GlobalLock(h_text)
        ctypes.memmove(p, encoded, len(encoded))
        kernel32.GlobalUnlock(h_text)
        user32.SetClipboardData(CF_UNICODETEXT, h_text)
    finally:
        user32.CloseClipboard()

    return filepath


def main():
    parser = argparse.ArgumentParser(description="Save clipboard images as PNG files.")
    parser.add_argument(
        "--copy-path", action="store_true",
        help="Add the PNG path as clipboard text for CLI use (web apps may paste the path).",
    )
    args = parser.parse_args()
    print("paste-claude: watching clipboard for images...")
    if args.copy_path:
        print("CLI mode: image file paths will be added to the clipboard.")
    else:
        print("Web mode: images stay on the clipboard; saved paths are printed here.")
    print("Press Ctrl+C to stop.\n")

    last_sequence = None
    while True:
        try:
            sequence = user32.GetClipboardSequenceNumber()
            if sequence != last_sequence and clipboard_has_image_only():
                filepath = process_clipboard(copy_path=args.copy_path)
                if filepath:
                    print(f"Saved: {filepath}")
                last_sequence = sequence
            time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception:
            time.sleep(0.5)


if __name__ == "__main__":
    main()
