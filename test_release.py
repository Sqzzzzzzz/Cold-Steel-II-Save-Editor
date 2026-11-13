from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from package_release import ARCHIVE_NAME, bundle_files
from version import VERSION


class WindowsReleaseTests(TestCase):
    def test_release_archive_uses_the_versioned_windows_name(self):
        self.assertEqual(ARCHIVE_NAME, f'Cold-Steel-II-Save-Editor-v{VERSION}-Windows.zip')

    def test_only_expected_documents_assets_and_runtime_paths_can_be_packaged(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            expected = ('README.md', '_internal/branding/app.ico', '_internal/PySide6/plugins/platforms/qwindows.dll')
            for name in expected:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            self.assertCountEqual(list(bundle_files(root, True)), [root / name for name in expected])
            for name in ('.env', '_internal/runtime.ini', '_internal/assets/app.ico', 'docs/private.txt'):
                with self.subTest(name=name):
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
                    with self.assertRaisesRegex(ValueError, 'Unexpected file in build'):
                        list(bundle_files(root, True))
                    path.unlink()
