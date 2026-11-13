# Third-party notices

This program uses Qt for Python (PySide6 Essentials and Shiboken 6.11.3) and Qt 6.11.3 under the GNU Lesser General Public License version 3. Copies of the LGPLv3 and GPLv3 are in this directory and embedded in the release EXE. You may modify the libraries and reverse-engineer the application to debug those modifications as provided by the LGPL.

- [Qt 6.11.3 corresponding source](https://download.qt.io/official_releases/qt/6.11/6.11.3/single/qt-everywhere-src-6.11.3.tar.xz)
- [Qt for Python and Shiboken 6.11.3 corresponding source](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.3-src/pyside-setup-everywhere-src-6.11.3.tar.xz)
- [Qt third-party licenses](https://doc.qt.io/qt-6/licenses-used-in-qt.html)

Qt Multimedia uses FFmpeg 7.1.5 under LGPL 2.1 or later. The included `LGPL-2.1-or-later.txt` gives the license terms. FFmpeg is loaded through shared DLLs. To replace it, use an interface-compatible build and Qt's Windows build instructions. [FFmpeg corresponding source](https://ffmpeg.org/releases/ffmpeg-7.1.5.tar.xz) · [Qt Multimedia attribution and build links](https://doc.qt.io/qt-6.11/qtmultimedia-attribution-ffmpeg.html)

The local artwork reader uses the format documented by SenPatcher. Its attribution is in `SenPatcher-MIT.txt`. [SenPatcher source](https://github.com/AdmiralCurtiss/SenPatcher/blob/master/native/sen/pkg_extract.cpp)

The Windows executable also includes the Python runtime and OpenSSL 3. See the embedded `Python-LICENSE.txt` for the Python notices and Apache License 2.0. [Python 3.14.4 license](https://docs.python.org/release/3.14.4/license.html)

The Windows executable embeds the PyInstaller bootloader. Its license and bootloader exception are in the embedded `PyInstaller-COPYING.txt`. [PyInstaller license](https://pyinstaller.org/en/v6.22.3/license.html)

## Use a modified Qt runtime

Download the editor source at this release's Git tag. Use Windows x64 with Python 3.14.4 and install `requirements-build.txt` into a virtual environment. Install your compatible Qt for Python and Shiboken builds into that environment in place of the corresponding wheels. Run `python build_preview.py --without-assets` to build a new standalone EXE, or add `--onedir` to build with replaceable DLLs and plugins under `_internal`. Run the resulting EXE from `dist/portable`. The application can also run directly with the modified libraries via `python app.py`.
