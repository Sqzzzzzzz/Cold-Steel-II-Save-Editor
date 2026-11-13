# Cold Steel II Save Editor v1.0.0

## Overview

An offline Windows inventory editor for the Steam PC version of *The Legend of Heroes: Trails of Cold Steel II*.

## Features

- Detect Steam installations and recent saves, or open a `.dat` or `.bak` file manually.
- Search, sort, and filter the installed game's catalog and inventory. Edit quantities in batches, review changes, and undo or reset before saving.
- Export inventory to CSV, write a separate save copy, or overwrite the open slot with a verified backup. Restore that backup from the Tools panel.
- Switch between English and Russian controls. Item data comes from the installed game.

## Improvements

The local build retains the original layout, colors, and Courageous background. The release package uses the same layout with built-in styling and original editor branding. The catalog reads each DLC table once and indexes categories as it loads. Qt skips unchanged rows and loads special item art on demand.

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

- `Cold-Steel-II-Save-Editor-v1.0.0-Windows.zip` contains only `Cold_Steel_II_Save_Editor.exe`.
- `SHA256SUMS.txt` is a separate release download with the SHA-256 checksum for the ZIP.

The executable uses Qt and Qt for Python under LGPLv3. The project source and the instructions for using a modified runtime are available alongside this release. [Third-party notices and rebuild instructions](https://github.com/Sqzzzzzzz/Cold-Steel-II-Save-Editor/blob/v1.0.0/third_party/README.md)

## Known Limitations

- Verified against Steam PC 1.4.1, build 3518949, version-8 saves. Other editions are unverified.
- Exporting a `.dat` does not register it in the game's slot list. Protected quest and equipment entries have editing restrictions. Restoring a DLC item absent from the current slot requires opening and exporting the original backup as a separate file.
- The public package excludes game artwork and the local item translation dictionary. Untranslated text is read from the installed game.
