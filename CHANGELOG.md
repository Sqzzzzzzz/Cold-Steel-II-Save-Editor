# Changelog

## 1.0.4

- Display the Thors crest in the title bar and below the sidebar navigation.

## 1.0.3

- Complete Russian catalog descriptions, including fishing entries and DLC packs.
- Translate master quartz effect titles while preserving the original English text.
- Update the README screenshot with a Russian equipment description.

## 1.0.2

- Add a local single-executable build with the original Windows icon and Russian item-name dictionary.
- Verify that both inventory tables switch item names between Russian and English in the local standalone EXE.

## 1.0.1

- Restore the Courageous background, Thors crest, and original item and interface icons by loading them from the local Steam installation.
- Give the standalone Windows EXE a new airship icon.

## 1.0.0

- Added a Windows inventory editor for Trails of Cold Steel II Steam saves with English and Russian controls.
- Added Steam discovery, local game catalog parsing, item search and filters, multi-selection, edit review, undo, CSV export, save copies, and verified backup and restore.
- Reduced repeated DLC table reads and category filtering work. Bounded the table's elided text cache and skipped duplicate layout updates.
- Fixed latest-save discovery when a remembered directory contains no compatible slots, save-copy handling for existing links, and closing during background file work.
- Kept first-launch setup available when a save opens before the catalog. Added scrolling when the available screen area is smaller than the editor layout.
- Applied the same ownership checks to editing and restoring DLC items. A backup with a removed DLC item can be exported separately.
- Added verified Windows packaging, SHA-256 manifests, and a GitHub Actions workflow for the portable build and draft releases.
- The public Windows ZIP contains one standalone EXE. Packaged smoke tests exercise switching between Russian and English, including Qt dialog translations.
