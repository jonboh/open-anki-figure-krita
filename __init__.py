import os
import re
import struct
import subprocess
import zlib

import aqt
from anki.hooks import addHook
from aqt import gui_hooks, mw, qt
from aqt.utils import tooltip


def get_media_dir():
    return mw.col.media.dir()


def find_png_images(note):
    """Return list of unique PNG filenames referenced in all fields of the note."""
    combined_html = " ".join(note.fields)
    return list(dict.fromkeys(re.findall(r'<img\s[^>]*src="([^"]+\.png)"[^>]*>', combined_html, re.IGNORECASE)))


def open_in_krita(filepath):
    subprocess.Popen(
        ["krita", filepath],
        stdin=None,
        stdout=None,
        stderr=None,
    )


def ensure_editor_open(note_id):
    """Open the card browser and navigate to the note. Returns the browser."""
    browser = aqt.dialogs.open("Browser", mw)
    browser.show()
    browser.raise_()
    browser.search_for(f"nid:{note_id}")
    return browser


def add_img_tag_to_note(note, filename):
    """Append two blank lines + <img src='filename'> to the last non-empty field."""
    tag = f'<br><br><img src="{filename}">'
    target_field = 0
    for i, field in enumerate(note.fields):
        if field.strip():
            target_field = i
    note.fields[target_field] = note.fields[target_field] + tag
    note.flush()


def _ask_new_filename():
    """Prompt the user for a PNG filename. Returns (filename, ok)."""
    filename, ok = qt.QInputDialog.getText(
        mw,
        "New Figure",
        "Enter filename for the new PNG figure (e.g. my_figure.png):",
    )
    if not ok or not filename.strip():
        return None, False
    filename = filename.strip()
    if not filename.lower().endswith(".png"):
        filename += ".png"
    return filename, True


def _resolve_new_filename(media_dir):
    """
    Ask for a filename, handling the case where the file already exists in the
    media collection. Returns (filename, create_new_file) or (None, _) on cancel.
    - create_new_file=True  → caller should write a blank PNG before opening Krita.
    - create_new_file=False → file already exists; open it directly in Krita.
    """
    while True:
        filename, ok = _ask_new_filename()
        if not ok:
            return None, False

        filepath = os.path.join(media_dir, filename)
        if not os.path.exists(filepath):
            return filename, True

        # File already exists — ask what to do
        msg_box = qt.QMessageBox(mw)
        msg_box.setWindowTitle("File Already Exists")
        msg_box.setText(
            f'"{filename}" already exists in the media collection.\n'
            "What would you like to do?"
        )
        btn_use = msg_box.addButton("Open existing file", qt.QMessageBox.ButtonRole.AcceptRole)
        btn_rename = msg_box.addButton("Choose a different name", qt.QMessageBox.ButtonRole.ResetRole)
        btn_cancel = msg_box.addButton("Cancel", qt.QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()

        clicked = msg_box.clickedButton()
        if clicked == btn_use:
            return filename, False
        elif clicked == btn_rename:
            continue  # loop back and ask again
        else:
            return None, False


def open_figure(note_id):
    note = mw.col.get_note(note_id)
    media_dir = get_media_dir()
    images = find_png_images(note)
    config = mw.addonManager.getConfig(__name__)
    open_editor = config.get("open_editor", False)

    if len(images) == 0:
        filename, create_new = _resolve_new_filename(media_dir)
        if filename is None:
            tooltip("Cancelled.")
            return

        filepath = os.path.join(media_dir, filename)

        if create_new:
            _create_blank_png(filepath)

        # Add img tag to the note only when inserting a brand-new reference
        add_img_tag_to_note(note, filename)

        if open_editor:
            ensure_editor_open(note_id)

        open_in_krita(filepath)
        tooltip(f"Opened {filename} in Krita. Image tag added to note.")

    elif len(images) == 1:
        filepath = os.path.join(media_dir, images[0])
        if open_editor:
            ensure_editor_open(note_id)
        open_in_krita(filepath)
        tooltip(f"Opened {images[0]} in Krita.")

    else:
        # Multiple images — ask user to pick one
        item, ok = qt.QInputDialog.getItem(
            mw,
            "Select Figure",
            "Multiple PNG images found. Select one to open in Krita:",
            images,
            0,
            False,
        )
        if not ok:
            tooltip("Cancelled.")
            return
        filepath = os.path.join(media_dir, item)
        if open_editor:
            ensure_editor_open(note_id)
        open_in_krita(filepath)
        tooltip(f"Opened {item} in Krita.")


def _png_chunk(tag, data):
    """Build a PNG chunk: length + tag + data + CRC."""
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _create_blank_png(filepath, width=100, height=100):
    """Create a fully transparent RGBA PNG of the given size using only stdlib."""
    signature = b"\x89PNG\r\n\x1a\n"

    # IHDR: width, height, bit-depth=8, color-type=6 (RGBA), compression=0, filter=0, interlace=0
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr = _png_chunk(b"IHDR", ihdr_data)

    # Raw image data: each row = filter byte (0x00) + width * 4 bytes of 0x00 (fully transparent)
    raw_row = b"\x00" + b"\x00" * (width * 4)
    raw_data = raw_row * height
    idat = _png_chunk(b"IDAT", zlib.compress(raw_data))

    iend = _png_chunk(b"IEND", b"")

    with open(filepath, "wb") as f:
        f.write(signature + ihdr + idat + iend)


def open_figure_browser():
    browser = aqt.dialogs._dialogs["Browser"][1]
    note_id = None
    if browser is not None and browser.card is not None:
        note_id = browser.card.nid
    if note_id:
        open_figure(note_id)
    else:
        tooltip("No note is selected.")


def open_figure_reviewer():
    if mw.state == "review" and mw.reviewer.card:
        open_figure(mw.reviewer.card.nid)
    else:
        tooltip("No note is being reviewed.")


def addKritaActionToMenu(menu, f):
    menu.addSeparator()
    a = menu.addAction("Open Figure in Krita")
    a.setShortcut(qt.QKeySequence("Ctrl+K"))
    a.triggered.connect(f)


def setupMenuBrowser(self):
    menu = self.form.menu_Notes
    addKritaActionToMenu(menu, open_figure_browser)


def setupMenuReviewer(self, menu):
    if mw.state != "review":
        return
    addKritaActionToMenu(menu, open_figure_reviewer)


def fix_reviewer_shortcut(state, shortcuts):
    if state == "review":
        shortcuts.append(("Ctrl+K", open_figure_reviewer))


addHook("browser.setupMenus", setupMenuBrowser)
addHook("Reviewer.contextMenuEvent", setupMenuReviewer)
gui_hooks.state_shortcuts_will_change.append(fix_reviewer_shortcut)
