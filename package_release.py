"""Package and smoke-test the local Windows build."""

import argparse
from hashlib import file_digest
import os
from pathlib import Path, PurePosixPath
import re
from struct import unpack_from
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from build_preview import ART, COLOR_CREST, EDITOR_ICON, GAME_ICON, ITEM_TEXT, NAME, NOTICES, ROOT
from version import VERSION


ARCHIVE_NAME = f'Cold-Steel-II-Save-Editor-v{VERSION}-Windows.zip'
DOCUMENTS = (
    'LICENSE', 'README.md', 'docs/asset-provenance.md', 'docs/editor.jpg',
    'third_party/README.md', 'third_party/Python-LICENSE.txt',
    'third_party/GPL-3.0-only.txt', 'third_party/LGPL-3.0-only.txt',
    'third_party/PyInstaller-COPYING.txt',
    'third_party/SenPatcher-MIT.txt', 'third_party/LGPL-2.1-or-later.txt',
)
RUNTIME_FILE = re.compile(
    r'_internal/(?:[\w.+-]+\.(?:pyd|dll)|(?:shiboken6|PySide6)/[\w.+-]+\.(?:pyd|dll)'
    r'|PySide6/(?:translations/[\w.+-]+\.qm|plugins/[\w-]+/[\w.+-]+\.dll))'
)


def bundle_files(bundle: Path, portable: bool):
    allowed = {*DOCUMENTS, f'{NAME}.exe', '_internal/base_library.zip'}
    allowed.update(('_internal/branding/app.ico',) if portable else (f'_internal/assets/{name}' for name in ART))
    if not portable:
        allowed.add('_internal/branding/thors-color.png')
    for path in sorted(bundle.rglob('*')):
        member = path.relative_to(bundle)
        if path.is_symlink() or path.is_junction():
            raise ValueError(f'Unexpected file link in build: {member}')
        if any(part.startswith('.') for part in member.parts):
            raise ValueError(f'Unexpected file in build: {member}')
        if path.is_dir():
            continue
        if member.as_posix() not in allowed and not RUNTIME_FILE.fullmatch(member.as_posix()):
            raise ValueError(f'Unexpected file in build: {member}')
        yield path


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return file_digest(stream, 'sha256').hexdigest()


def validate_onefile(executable: Path, *, original_icon: bool = False):
    from PyInstaller.archive.readers import CArchiveReader

    app = CArchiveReader(str(executable))
    members = {name.replace('\\', '/'): name for name in app.toc}
    required = {'branding/app.ico', 'PySide6/translations/qtbase_ru.qm', 'LICENSE',
                'PySide6/plugins/multimedia/ffmpegmediaplugin.dll', 'PySide6/avcodec-61.dll'}
    required.update(f'{NOTICES}/{Path(name).name}' for name in DOCUMENTS if name.startswith(f'{NOTICES}/'))
    if not required <= members.keys():
        raise ValueError(f'Missing embedded resources: {", ".join(sorted(required - members.keys()))}')
    icon = GAME_ICON if original_icon else EDITOR_ICON
    if app.extract(members['branding/app.ico']) != icon.read_bytes():
        raise ValueError('The embedded application icon differs from the selected icon.')
    dictionary = members.get('translations/item-text.json')
    crest = members.get('branding/thors-color.png')
    if original_icon:
        if dictionary is None or app.extract(dictionary) != ITEM_TEXT.read_bytes():
            raise ValueError('The local standalone executable lacks the current item dictionary.')
        embedded_crest = app.extract(crest) if crest is not None else None
        local_crest = COLOR_CREST.read_bytes() if COLOR_CREST.is_file() else None
        if embedded_crest != local_crest:
            raise ValueError('The embedded color crest differs from the local artwork.')
    elif dictionary is not None or crest is not None:
        raise ValueError('The public executable contains local artwork or translations.')
    if any(name.startswith('assets/') or PurePosixPath(name).suffix.lower() in {'.dat', '.bak', '.vdf', '.log', '.key', '.pem'}
           for name in members):
        raise ValueError('Unexpected private files or game resources embedded in the executable.')


def package(*, portable: bool, tag: str | None, save: Path | None, original_icon: bool = False) -> Path:
    if tag is not None and tag != f'v{VERSION}':
        raise ValueError(f'Tag must be v{VERSION}.')
    if original_icon and not portable:
        raise ValueError('--original-icon requires --portable.')
    variant = 'local-standalone' if original_icon else 'portable'
    dist = ROOT / 'dist' / variant if portable else ROOT / 'dist'
    bundle = dist / NAME
    internal = bundle / '_internal'
    assets = internal / 'assets'
    if portable:
        executable = dist / f'{NAME}.exe'
        validate_onefile(executable, original_icon=original_icon)
    else:
        executable = bundle / f'{NAME}.exe'
        required = (*DOCUMENTS, '_internal/PySide6/translations/qtbase_ru.qm', '_internal/base_library.zip')
        missing = [name for name in required if not (bundle / name).is_file()]
        if missing:
            raise ValueError(f'Missing package files: {", ".join(missing)}. Rebuild first.')
        if any(not (assets / name).is_file() or digest(assets / name) != digest(ROOT / 'assets' / name)
               for name in ART):
            raise ValueError('The built assets differ from the local source assets. Rebuild first.')
    binary = executable.read_bytes()
    pe = unpack_from('<I', binary, 0x3C)[0]
    if (not binary.startswith(b'MZ') or binary[pe:pe+4] != b'PE\0\0'
            or unpack_from('<H', binary, pe+4)[0] != 0x8664
            or unpack_from('<H', binary, pe+92)[0] != 2):
        raise ValueError('Expected a 64-bit Windows GUI executable.')

    output = ROOT / 'release' / (variant if portable else 'local')
    output.mkdir(parents=True, exist_ok=True)
    archive = output / ARCHIVE_NAME
    with TemporaryDirectory(dir=output, prefix='.package-') as directory:
        stage = Path(directory)
        candidate = stage / archive.name
        with ZipFile(candidate, 'w', ZIP_DEFLATED) as release:
            if portable:
                release.write(executable, executable.name)
            for path in (() if portable else bundle_files(bundle, False)):
                member = path.relative_to(bundle.parent).as_posix()
                if path == internal / 'base_library.zip':
                    # CPython also accepts a directory at the base_library.zip sys.path entry.
                    with ZipFile(path) as library:
                        for entry in library.infolist():
                            if not entry.is_dir():
                                name = PurePosixPath(entry.filename)
                                if (name.is_absolute() or '..' in name.parts or name.suffix != '.pyc'
                                        or '\\' in entry.filename or ':' in entry.filename):
                                    raise ValueError(f'Unexpected entry in Python runtime: {entry.filename}')
                                release.writestr(f'{member}/{entry.filename}', library.read(entry))
                else:
                    release.write(path, member)
            if not portable:
                for doc in ('CHANGELOG.md', 'docs/release-notes.md'):
                    release.write(ROOT / doc, f'{NAME}/{doc}')

        with ZipFile(candidate) as release:
            if (release.testzip() is not None or len(release.namelist()) != len(set(release.namelist()))
                    or any(Path(member).suffix.lower() == '.zip' for member in release.namelist())
                    or (portable and release.namelist() != [executable.name])):
                raise ValueError('ZIP integrity check failed.')
            release.extractall(stage)
        unpacked = stage if portable else stage / NAME
        system = Path(os.environ['SystemRoot'])
        env = {key: value for key, value in os.environ.items() if not key.upper().startswith(('PYTHON', 'QT_'))}
        env['PATH'] = os.pathsep.join(map(str, (system / 'System32', system)))
        run = [str(unpacked / executable.name)]
        work = stage / 'separate working directory'
        work.mkdir()
        subprocess.run([*run, '--smoke-test-clean'], cwd=work, env=env, timeout=30, check=True)
        fixture = stage / 'test-slot.dat'
        args = ['--smoke-test-portable' if portable else '--smoke-test', '--save', str(fixture)]
        if save is None:
            from test_catalog import item, table
            from test_cs2 import make_save
            from qt_backend import ITEM_TABLE

            game = stage / 'fixture-game'
            item_table = game / ITEM_TABLE
            item_table.parent.mkdir(parents=True)
            item_table.write_bytes(table((b'item', b'item_q', b'condition'), [
                (b'item', item(0, 0x81, name=b'Sample Potion')),
                (b'item', item(3200, 0xC9, name=b'Sample Master', limit=1)),
                (b'item_q', item(3300, 0xC8, name=b'Sample Quartz')),
                (b'condition', b'fixture'),
            ]))
            snapshot = make_save((0, 2))
            args.extend(['--game', str(game)])
        else:
            snapshot = save.read_bytes()
        fixture.write_bytes(snapshot)
        subprocess.run([*run, *args], cwd=work, env=env, timeout=30, check=True)
        if fixture.read_bytes() != snapshot or (save is not None and save.read_bytes() != snapshot):
            raise ValueError('The startup check modified the save.')
        checksum = stage / 'SHA256SUMS.txt'
        checksum.write_text(f'{digest(candidate)}  {archive.name}\n', encoding='ascii')
        candidate.replace(archive)
        checksum.replace(output / checksum.name)
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--portable', action='store_true', help='Package an asset-free build for public distribution.')
    parser.add_argument('--original-icon', action='store_true', help='Package the local standalone EXE with the game icon and dictionary.')
    parser.add_argument('--tag')
    parser.add_argument('--save', type=Path, help='Smoke-test the extracted EXE with a temporary copy of this save.')
    options = parser.parse_args()
    print(package(portable=options.portable, tag=options.tag, save=options.save, original_icon=options.original_icon))
