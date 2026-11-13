from hashlib import sha256
from pathlib import Path
from struct import pack
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

from PySide6.QtGui import QImage

from game_art import ASSETS, _decompress_type1, _pkg_textures, import_art
from qt_backend import STEAM_GAME


class GameArtworkTests(TestCase):
    def test_package_reads_only_requested_texture(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'textures.pkg'
            tokens = b'ab\xff\x02\x04\xff\xff'
            compressed = pack('<III', 7, 12 + len(tokens), 255) + tokens
            path.write_bytes(pack('<2I64s4I', 0, 1, b'texture', 7, len(compressed), 88, 1) + compressed)
            self.assertEqual(_pkg_textures(path, {'texture'}), {'texture': b'ababab\xff'})
            with self.assertRaisesRegex(ValueError, 'Required textures missing'):
                _pkg_textures(path, {'missing'})

    def test_decompression_rejects_out_of_bounds_reference(self):
        with self.assertRaisesRegex(ValueError, 'reference'):
            _decompress_type1(pack('<III', 3, 15, 255) + b'\xff\x01\x03', 3)

    @skipUnless((STEAM_GAME / 'data/asset/D3D11_us/I_SYSTEM.pkg').is_file(), 'Cold Steel II game textures unavailable')
    def test_import_matches_the_approved_art_and_preserves_game_packages(self):
        system = STEAM_GAME / 'data/asset/D3D11_us/I_SYSTEM.pkg'
        before = sha256(system.read_bytes()).digest()
        with TemporaryDirectory() as directory:
            output = Path(directory)
            import_art(STEAM_GAME, output)
            for name in ('item-atlas.png', 'secondary-atlas.png', 'master-atlas.png', 'menu-atlas.png',
                         'arrow-up.png', 'arrow-down.png', 'fish-art.png', 'blade-ii.png', 'shining-pom.png', 'thors.png'):
                with self.subTest(name=name):
                    image = QImage(str(output / name))
                    self.assertFalse(image.isNull())
                    reference = ASSETS / name
                    if reference.is_file():
                        self.assertEqual(image, QImage(str(reference)))
        self.assertEqual(sha256(system.read_bytes()).digest(), before)
