# Cold Steel II Save Editor v1.0.3

## Overview

An offline Windows inventory editor for the Steam PC version of *The Legend of Heroes: Trails of Cold Steel II*.

## Features

- Detect Steam installations and recent saves, or open a `.dat` or `.bak` file manually.
- Search, sort, and filter the installed game's catalog and inventory. Edit quantities in batches, review changes, and undo or reset before saving.
- Export inventory to CSV, write a separate save copy, or overwrite the open slot with a verified backup. Restore that backup from the Tools panel.
- Switch between English and Russian controls, item names, and descriptions. Item data comes from the installed game.

## Improvements

- Russian descriptions cover all 1,205 catalog entries, including fish and DLC packs. The remaining descriptions were translated with offline machine assistance and terminology corrections.
- All 75 distinct master quartz effect titles are available in Russian. English continues to use the original Steam text.
- The Windows EXE uses the original Steam game icon.

## Installation

Extract and run `Cold_Steel_II_Save_Editor.exe`. The ZIP contains one standalone executable with Python and Qt included. Keep the Steam PC game installed for access to its item tables.

## Requirements

- 64-bit Windows 10 or 11.
- The Steam PC edition of *Trails of Cold Steel II*, including `data/text/dat_us/t_item.tbl`.

## Important Notes

Close the game before overwriting a slot. The editor creates and verifies a backup before replacement and writes only the active inventory block. The package is unsigned.

## Downloads

- `Cold-Steel-II-Save-Editor-v1.0.3-Windows.zip` contains only `Cold_Steel_II_Save_Editor.exe`.
- `SHA256SUMS.txt` is a separate release download with the SHA-256 checksum for the ZIP.

The executable uses Qt and Qt for Python under LGPLv3 and FFmpeg under LGPLv2.1 or later. [Third-party notices, sources and rebuild instructions](https://github.com/Sqzzzzzzz/Cold-Steel-II-Save-Editor/blob/v1.0.3/third_party/README.md)

## Known Limitations

- Verified against Steam PC 1.4.1, build 3518949, version-8 saves. Other editions are unverified.
- Exporting a `.dat` does not register it in the game's slot list. Protected quest and equipment entries have editing restrictions. Restoring a DLC item absent from the current slot requires opening and exporting the original backup as a separate file.
- Game artwork loads from the full Steam installation. The logo depends on Steam's local cache.
