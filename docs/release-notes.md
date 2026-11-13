# Cold Steel II Save Editor v1.0.1

## Overview

An offline Windows inventory editor for the Steam PC version of *The Legend of Heroes: Trails of Cold Steel II*.

## Features

- Detect Steam installations and recent saves, or open a `.dat` or `.bak` file manually.
- Search, sort, and filter the installed game's catalog and inventory. Edit quantities in batches, review changes, and undo or reset before saving.
- Export inventory to CSV, write a separate save copy, or overwrite the open slot with a verified backup. Restore that backup from the Tools panel.
- Switch between English and Russian controls. Item data comes from the installed game.

## Improvements

The standalone Windows executable has a new airship icon. When the editor scans the installed game, it loads the Courageous background, the Thors crest, and the original item and interface icons. These images are cached on your computer.

## Bug Fixes

- Latest Save falls back to Steam when the remembered folder has no compatible slots.
- Save a Copy rejects an existing file link, including a link whose target is missing.
- Background file errors leave the editor open so edits can be reviewed or saved separately.
- Restoring a backup validates the changed item IDs and quantities against the catalog and refreshes the displayed quantities from the restored file.
- Opening a save before locating the game leaves the first-launch setup visible.
- At high DPI or on small displays, the editor can scroll to controls outside the available work area.

## Installation

Extract and run `Cold_Steel_II_Save_Editor.exe`. The ZIP contains one standalone executable with Python and Qt included. Keep the Steam PC game installed for access to its item tables.

## Requirements

- 64-bit Windows 10 or 11.
- The Steam PC edition of *Trails of Cold Steel II*, including `data/text/dat_us/t_item.tbl`.

## Important Notes

Close the game before overwriting a slot. The editor creates and verifies a backup before replacement and writes only the active inventory block. The package is unsigned.

## Downloads

- `Cold-Steel-II-Save-Editor-v1.0.1-Windows.zip` contains only `Cold_Steel_II_Save_Editor.exe`.
- `SHA256SUMS.txt` is a separate release download with the SHA-256 checksum for the ZIP.

The executable uses Qt and Qt for Python under LGPLv3 and FFmpeg under LGPLv2.1 or later. [Third-party notices, sources and rebuild instructions](https://github.com/Sqzzzzzzz/Cold-Steel-II-Save-Editor/blob/v1.0.1/third_party/README.md)

## Known Limitations

- Verified against Steam PC 1.4.1, build 3518949, version-8 saves. Other editions are unverified.
- Exporting a `.dat` does not register it in the game's slot list. Protected quest and equipment entries have editing restrictions. Restoring a DLC item absent from the current slot requires opening and exporting the original backup as a separate file.
- Game artwork loads from the full Steam installation. The logo depends on Steam's local cache, and untranslated item text comes from the installed game.
