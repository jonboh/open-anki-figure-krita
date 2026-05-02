# open_anki_figure_krita

Opens PNG figures embedded in an Anki card directly in Krita.

## Config options

- `krita`: path or executable name for Krita (default: `"krita"`)
- `open_editor`: if `true`, the Anki card browser is opened (or focused) after triggering the action (default: `false`)
- `new_figure_width`: pixel width of a newly created blank PNG (default: `600`)
- `new_figure_height`: pixel height of a newly created blank PNG (default: `600`)

## Usage

### Browser
Open the card browser, select a card, then use **Notes → Open Figure in Krita** or press `Ctrl+K`.

### Reviewer
While reviewing a card press `Ctrl+K` or right-click and choose **Open Figure in Krita**.

## Behaviour

| Images in card | Action |
|---|---|
| None | Prompts for a new filename, creates the PNG, appends `<img src="file.png">` to the note, and opens Krita |
| One | Opens that PNG in Krita |
| Multiple | Shows a selection dialog, then opens the chosen PNG in Krita |

If `open_editor` is `true`, the card browser is also opened or focused in all three cases.
