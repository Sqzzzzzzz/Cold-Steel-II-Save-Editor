# Changelog

## 1.0.0

- Added a Windows inventory editor for Trails of Cold Steel II Steam saves with English and Russian controls.
- Added Steam discovery, local game catalog parsing, item search and filters, multi-selection, edit review, undo, CSV export, save copies, and verified backup and restore.
- Reduced repeated DLC table reads and category filtering work. Bounded the table's elided text cache and skipped duplicate layout updates.
- Fixed latest-save discovery when a remembered directory contains no compatible slots, save-copy handling for existing links, and closing during background file work.
- Kept first-launch setup available when a save opens before the catalog. Added scrolling when the available screen area is smaller than the editor layout.
- Applied the same ownership checks to editing and restoring DLC items. A backup with a removed DLC item can be exported separately.
- Added verified Windows packaging, SHA-256 manifests, and a GitHub Actions workflow for the portable build and draft releases.
- The public Windows ZIP contains one standalone EXE. Packaged smoke tests exercise switching between Russian and English, including Qt dialog translations.
