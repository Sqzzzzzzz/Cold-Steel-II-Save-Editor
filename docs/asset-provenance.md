# Local game artwork

The standard CI build uses the editor's airship icon in `branding/app.ico`. The v1.0.2 download in this private repository embeds the original executable icon and the Russian item dictionary. Both builds extract the original UI and item icons from the installed game and read the Courageous background from the intro movie. The editor uses Steam's local logo cache when available. The generated artwork stays in `%LOCALAPPDATA%\ColdSteelSaveEditor`. The README screenshot shows a demo inventory with artwork loaded from the installed game.

| Local file | Source |
| --- | --- |
| `courageous-backdrop.jpg` | Frame at 1:52 of `data/movie/ed82_OP.avi` in the installed game. |
| `logo.png` | Steam library cache for app `748490`. |
| `app.ico` | Icon resources of the locally installed `ed8_2_PC_US.exe`. |
| Item, menu, master quartz, and fish atlases, crest, arrows, and individual item art | Original game packages. The editor extracts these automatically during a catalog scan. `python game_art.py <game directory>` can also extract them into `assets` for a local build. |
| `item-text.json` | Local Russian dictionary covering all 1,205 item names and selected descriptions, including matched entries from the Cold Steel I project. |

The MIT license applies to the editor source. Public redistribution rights for the extracted game artwork have not been established. [Gameplay video guidelines](https://www.falcom.co.jp/guideline-en) · [Falcom licensing FAQ](https://www.falcom.co.jp/license/faq)

To build a single EXE locally with the original Windows icon and the local Russian item dictionary, place `app.ico` and `item-text.json` in `assets`. Run `python build_preview.py --without-assets --original-icon`, then `python package_release.py --portable --original-icon`. Find the ZIP in `release/local-standalone`. At runtime the EXE loads the background and item art from your local game installation.

For a local build with all artwork embedded, supply the images and dictionary listed in `build_preview.py` and run `python build_preview.py` followed by `python package_release.py`.
