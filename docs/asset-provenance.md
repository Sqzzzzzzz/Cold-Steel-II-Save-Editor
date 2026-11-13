# Local game artwork

The Windows release uses its own airship icon in `branding/app.ico`. When it scans an installed game, it extracts the original UI and item icons from that installation and reads the Courageous background from the intro movie. It uses Steam's local logo cache when available. The generated artwork stays in `%LOCALAPPDATA%\ColdSteelSaveEditor`. The release itself contains no Falcom artwork or translation dictionary. The public README screenshot uses sample data.

| Local file | Source |
| --- | --- |
| `courageous-backdrop.jpg` | Frame at 1:52 of `data/movie/ed82_OP.avi` in the installed game. |
| `logo.png` | Steam library cache for app `748490`. |
| `app.ico` | Icon resources of the locally installed `ed8_2_PC_US.exe`. |
| Item, menu, master quartz, and fish atlases, crest, arrows, and individual item art | Original game packages. The editor extracts these automatically during a catalog scan. `python game_art.py <game directory>` can also extract them into `assets` for a local build. |
| `item-text.json` | Local dictionary, including matched entries from the Cold Steel I project and translations of common Cold Steel II items. |

The MIT license applies to the editor source. Falcom's public guidelines address gameplay video and streaming and do not provide a license for bundling extracted artwork in software. Falcom also describes its licensing process separately. Redistribution rights for the themed archive were not established. Keep it and the themed screenshots local unless the required rights are confirmed. [Gameplay video guidelines](https://www.falcom.co.jp/guideline-en) · [Falcom licensing FAQ](https://www.falcom.co.jp/license/faq)

For a local build with embedded game artwork, place the images and the dictionary listed in `build_preview.py` in the project's `assets` folder. Use `python build_preview.py` and `python package_release.py`. The standalone release EXE contains only the editor's own branding and runtime resources.
