"""Build the Windows application from a clean checkout or with local artwork."""

import argparse
from importlib.metadata import distribution
import os
from pathlib import Path
from shutil import copy2, copytree
import subprocess
import sys

from version import VERSION


ROOT = Path(__file__).resolve().parent
NAME = "Cold_Steel_II_Save_Editor"
EDITOR_ICON = ROOT / "branding/app.ico"
NOTICES = "third_party"
ART = (
    "courageous-backdrop.jpg", "item-text.json",
    "thors.png", "logo.png", "app.ico", "item-atlas.png",
    "secondary-atlas.png", "master-atlas.png", "menu-atlas.png", "fish-art.png", "blade-ii.png",
    "shining-pom.png", "arrow-up.png", "arrow-down.png",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--without-assets", action="store_true", help="Build without locally supplied game assets")
    parser.add_argument("--onedir", action="store_true", help="Build with replaceable runtime libraries beside the EXE")
    args = parser.parse_args()
    onefile = args.without_assets and not args.onedir
    assets = ROOT / "assets"
    if not args.without_assets:
        missing = [name for name in ART if not (assets / name).is_file()]
        if missing:
            parser.error(f"Missing local assets: {', '.join(missing)}. See README.md.")

    system = Path(os.environ["SystemRoot"])
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join(map(str, (Path(sys.executable).parent, system / "System32", system)))
    environment["PYINSTALLER_CONFIG_DIR"] = str(ROOT / "build/pyinstaller-cache")
    for key in ("PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QML2_IMPORT_PATH"):
        environment.pop(key, None)
    build = ROOT / "build" / ("portable" if args.without_assets else "local")
    build.mkdir(parents=True, exist_ok=True)
    dist = ROOT / "dist" / "portable" if args.without_assets else ROOT / "dist"
    version_resource = build / "windows-version.txt"
    version_tuple = (*map(int, VERSION.split(".")), 0)
    version_resource.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={version_tuple}, prodvers={version_tuple}, mask=0x3f,
    flags=0, OS=0x40004, fileType=0x1, subtype=0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('FileDescription', 'Cold Steel II Save Editor'),
    StringStruct('FileVersion', '{VERSION}'),
    StringStruct('OriginalFilename', '{NAME}.exe'),
    StringStruct('ProductName', 'Cold Steel II Save Editor'),
    StringStruct('ProductVersion', '{VERSION}')
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)""",
        encoding="utf-8",
    )
    arguments = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile" if onefile else "--onedir", "--windowed",
        "--name", NAME, "--specpath", str(build), "--version-file", str(version_resource),
        "--workpath", str(build / "pyinstaller"), "--distpath", str(dist),
    ]
    if args.without_assets:
        arguments += ["--icon", str(EDITOR_ICON), "--add-data", f"{EDITOR_ICON};branding"]
    else:
        arguments += ["--icon", str(assets / "app.ico")]
        for name in ART:
            arguments += ["--add-data", f"{assets / name};assets"]
    pyinstaller = distribution("PyInstaller")
    copying = next(file for file in pyinstaller.files if file.name == "COPYING.txt")
    notices = build / NOTICES
    copytree(ROOT / NOTICES, notices, dirs_exist_ok=True)
    copy2(Path(sys.base_prefix) / "LICENSE.txt", notices / "Python-LICENSE.txt")
    copy2(pyinstaller.locate_file(copying), notices / "PyInstaller-COPYING.txt")
    if onefile:
        for name in ("README.md", "GPL-3.0-only.txt", "LGPL-3.0-only.txt", "Python-LICENSE.txt", "PyInstaller-COPYING.txt"):
            arguments += ["--add-data", f"{notices / name};{NOTICES}"]
        arguments += ["--add-data", f"{ROOT / 'LICENSE'};."]
    subprocess.run([*arguments, str(ROOT / "app.py")], cwd=ROOT, env=environment, check=True)
    if onefile:
        return
    output = dist / NAME
    copy2(ROOT / "LICENSE", output)
    copy2(ROOT / "README.md", output)
    docs = output / 'docs'
    docs.mkdir(exist_ok=True)
    copy2(ROOT / 'docs/asset-provenance.md', docs)
    copy2(ROOT / 'docs/editor-en.jpg', docs)
    copytree(notices, output / NOTICES, dirs_exist_ok=True)


if __name__ == "__main__":
    main()
