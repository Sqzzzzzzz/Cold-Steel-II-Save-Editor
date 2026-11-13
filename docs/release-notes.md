# Cold Steel II Save Editor v1.0.2

## Overview

An offline Windows inventory editor for the Steam PC version of *The Legend of Heroes: Trails of Cold Steel II*.

## Features

- Detect Steam installations and recent saves, or open a `.dat` or `.bak` file manually.
- Search, sort, and filter the installed game's catalog and inventory. Edit quantities in batches, review changes, and undo or reset before saving.
- Export inventory to CSV, write a separate save copy, or overwrite the open slot with a verified backup. Restore that backup from the Tools panel.
- Switch between English and Russian controls and item names. Item data comes from the installed game.

## Improvements

- The standalone Windows executable uses the same icon as the Steam game's EXE.
- All 1,205 item names are available in Russian. Switching languages updates the catalog, inventory, and selected item.
- The README shows the Russian catalog with the Courageous background and original game icons. The editor loads this artwork from the installed game and caches it on your computer.

## Installation

Extract and run `Cold_Steel_II_Save_Editor.exe`. The ZIP contains one standalone executable with Python and Qt included. Keep the Steam PC game installed for access to its item tables.

## Requirements

- 64-bit Windows 10 or 11.
- The Steam PC edition of *Trails of Cold Steel II*, including `data/text/dat_us/t_item.tbl`.

## Important Notes

Close the game before overwriting a slot. The editor creates and verifies a backup before replacement and writes only the active inventory block. The package is unsigned.

## Downloads

- `Cold-Steel-II-Save-Editor-v1.0.2-Windows.zip` contains only `Cold_Steel_II_Save_Editor.exe`.
- `SHA256SUMS.txt` is a separate release download with the SHA-256 checksum for the ZIP.

The executable uses Qt and Qt for Python under LGPLv3 and FFmpeg under LGPLv2.1 or later. [Third-party notices, sources and rebuild instructions](https://github.com/Sqzzzzzzz/Cold-Steel-II-Save-Editor/blob/v1.0.2/third_party/README.md)

## Known Limitations

- Verified against Steam PC 1.4.1, build 3518949, version-8 saves. Other editions are unverified.
- Exporting a `.dat` does not register it in the game's slot list. Protected quest and equipment entries have editing restrictions. Restoring a DLC item absent from the current slot requires opening and exporting the original backup as a separate file.
- Game artwork loads from the full Steam installation. The logo depends on Steam's local cache, and untranslated item text comes from the installed game.
