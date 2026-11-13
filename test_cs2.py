from pathlib import Path
import os
from struct import pack_into
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch

from cs2 import (
    ARCUS_COVERS_OFFSET, EMPTY_EXTRA, EMPTY_RECORD, INVENTORY_END, INVENTORY_OFFSET, ORBMENTS_OFFSET,
    ORBMENT_SIZE, ORBMENT_SLOTS, RECORD, SAVE_HEADER, SAVE_SIZE, SLOTS, Save, publish_new, replace_with_backup,
)
from save_storage import SteamSaveStorage
from item_catalog import CatalogItem


POTION = CatalogItem("Tear Balm", "Restores 800 HP", "items", 99, 0x81, 0)
MASTER = CatalogItem("Force", "", "master", 1, 0xAB, 3)


def make_save(*items: tuple[int, int]) -> bytes:
    data = bytearray(SAVE_SIZE)
    data[:len(SAVE_HEADER)] = SAVE_HEADER
    pack_into("<48H", data, ARCUS_COVERS_OFFSET, *([9999] * 48))
    for slot in range(ORBMENT_SLOTS):
        pack_into("<9H", data, ORBMENTS_OFFSET + slot * ORBMENT_SIZE, *([9999] * 9))
    pack_into("<H", data, ORBMENTS_OFFSET, 3200)
    data[INVENTORY_OFFSET:INVENTORY_END] = (
        b"".join(RECORD.pack(item_id, quantity, EMPTY_EXTRA) for item_id, quantity in items)
        + EMPTY_RECORD * (SLOTS - len(items))
    )
    data[-4:] = b"tail"
    return bytes(data)


class SaveTests(TestCase):
    def test_edit_roundtrip_changes_only_inventory(self):
        original = make_save((0, 2), (1, 3), (6000, 8))
        save = Save(original)
        self.assertEqual(save.edited_bytes(), original)
        save.set_quantity(0, 5, POTION)
        save.set_quantity(1, 0, POTION)
        save.set_quantity(2, 4, POTION)

        edited = save.edited_bytes()
        self.assertEqual(list(Save(edited).items.items()), [(0, 5), (6000, 8), (2, 4)])
        self.assertEqual(edited[:INVENTORY_OFFSET], original[:INVENTORY_OFFSET])
        self.assertEqual(edited[INVENTORY_END:], original[INVENTORY_END:])

    def test_undo_by_restoring_quantities_preserves_exact_bytes(self):
        original = make_save((0, 2), (1, 3))
        save = Save(original)
        save.set_quantity(0, 0, POTION)
        save.set_quantity(0, 2, POTION)
        self.assertFalse(save.changed)
        self.assertEqual(save.edited_bytes(), original)

    def test_invalid_quantity_and_equipped_master_are_rejected(self):
        save = Save(make_save((0, 2)))
        with self.assertRaisesRegex(ValueError, "between"):
            save.set_quantity(0, 100, POTION)
        with self.assertRaisesRegex(ValueError, "equipped"):
            save.set_quantity(3200, 1, MASTER)
        self.assertFalse(save.changed)
        equipped_and_owned = Save(make_save((3200, 1)))
        with self.assertRaisesRegex(ValueError, "equipped"):
            equipped_and_owned.set_quantity(3200, 0, MASTER)
        self.assertEqual(equipped_and_owned.items[3200], 1)

    def test_equipped_alias_and_cover_and_absent_dlc_are_protected(self):
        original = bytearray(make_save((4038, 1)))
        pack_into("<H", original, ORBMENTS_OFFSET, 3244)
        pack_into("<H", original, ARCUS_COVERS_OFFSET + 32, 4038)
        save = Save(bytes(original))
        cover = CatalogItem("Anniversary Cover", "", "equipment", 1, 0xC5, 0, dlc_pack=212)
        with self.assertRaisesRegex(ValueError, "Master Quartz.*equipped"):
            save.set_quantity(3200, 1, MASTER)
        with self.assertRaisesRegex(ValueError, "ARCUS cover.*equipped"):
            save.set_quantity(4038, 0, cover)
        with self.assertRaisesRegex(ValueError, "DLC item"):
            save.set_quantity(4039, 1, cover)

    def test_reject_wrong_game_duplicate_and_nonempty_after_padding(self):
        for data in (bytes(SAVE_SIZE), make_save((0, 1), (0, 2)), make_save((9999, 0), (0, 1))):
            with self.subTest(header=data[:8]), self.assertRaises(ValueError):
                Save(data)

    def test_writes_backup_and_refuses_to_overwrite_newer_source(self):
        original = make_save((0, 2))
        with TemporaryDirectory() as directory:
            path = Path(directory) / "save001.dat"
            path.write_bytes(original)
            save = Save.open(path)
            save.set_quantity(0, 5, POTION)
            backup = save.write(path, original_path=True)
            self.assertEqual(backup.read_bytes(), original)
            self.assertEqual(Save.open(path).items, {0: 5})
            with self.assertRaisesRegex(ValueError, "changed on disk"):
                save.write(path, original_path=True)
            self.assertEqual(Save.open(path).items, {0: 5})

    def test_new_copy_preserves_source(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "save001.dat"
            target = Path(directory) / "save002.dat"
            original = make_save((0, 2))
            source.write_bytes(original)
            save = Save.open(source)
            save.set_quantity(0, 3, POTION)
            self.assertIsNone(save.write(target, original_path=False))
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(Save.open(target).items, {0: 3})

    def test_existing_destination_is_left_untouched_by_save_copy(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "save002.dat"
            existing = make_save((0, 9))
            destination.write_bytes(existing)
            save = Save(make_save((0, 2)))
            with self.assertRaises(FileExistsError):
                save.write(destination, original_path=False)
            self.assertEqual(destination.read_bytes(), existing)
            self.assertEqual(list(Path(directory).iterdir()), [destination])

    def test_overwrite_rechecks_source_after_creating_backup(self):
        original = make_save((0, 2))
        newer = make_save((0, 9))
        with TemporaryDirectory() as directory:
            path = Path(directory) / "save001.dat"
            path.write_bytes(original)
            save = Save.open(path)
            save.set_quantity(0, 5, POTION)

            def publish_and_update(staged, backup):
                publish_new(staged, backup)
                path.write_bytes(newer)

            with patch("cs2.publish_new", side_effect=publish_and_update):
                with self.assertRaisesRegex(ValueError, "changed on disk"):
                    save.write(path, original_path=True)
            self.assertEqual(path.read_bytes(), newer)
            backup, = path.parent.glob("*.bak")
            self.assertEqual(backup.read_bytes(), original)

    @skipUnless(os.name == "nt", "Windows replacement semantics")
    def test_in_place_writer_is_blocked_during_replacement(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "save001.dat"
            original = make_save((0, 2))
            path.write_bytes(original)
            save = Save.open(path)
            save.set_quantity(0, 5, POTION)

            def competing_write(target, temporary, displaced):
                with self.assertRaises(PermissionError):
                    target.write_bytes(make_save((0, 9)))
                replace_with_backup(target, temporary, displaced)

            with patch("cs2.replace_with_backup", side_effect=competing_write):
                backup = save.write(path, original_path=True)
            self.assertEqual(backup.read_bytes(), original)
            self.assertEqual(Save.open(path).items, {0: 5})

    @skipUnless(os.name == "nt", "Windows replacement semantics")
    def test_concurrent_rename_is_preserved_for_recovery(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "save001.dat"
            original, concurrent = make_save((0, 2)), make_save((0, 9))
            path.write_bytes(original)
            rival = root / "rival.dat"
            rival.write_bytes(concurrent)
            save = Save.open(path)
            save.set_quantity(0, 5, POTION)

            def competing_rename(target, temporary, displaced):
                replace_with_backup(target, rival, root / "competing-original.dat")
                replace_with_backup(target, temporary, displaced)

            with patch("cs2.replace_with_backup", side_effect=competing_rename):
                with self.assertRaisesRegex(ValueError, "concurrent save was preserved"):
                    save.write(path, original_path=True)
            self.assertCountEqual([backup.read_bytes() for backup in root.glob("*.bak")], [original, concurrent])

    @skipUnless(os.name == "nt", "Windows replacement semantics")
    def test_failed_replacement_restores_a_displaced_slot(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "save001.dat"
            original = make_save((0, 2))
            path.write_bytes(original)
            save = Save.open(path)
            save.set_quantity(0, 5, POTION)

            def failed_after_displacement(target, temporary, displaced):
                os.rename(target, displaced)
                raise OSError("replacement failed")

            with patch("cs2.replace_with_backup", side_effect=failed_after_displacement):
                with self.assertRaisesRegex(OSError, "replacement failed"):
                    save.write(path, original_path=True)
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue(all(backup.read_bytes() == original for backup in path.parent.glob("*.bak")))


class SteamStorageTests(TestCase):
    def test_save_copy_never_follows_existing_dangling_link(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'save001.dat'
            path.write_bytes(make_save((0, 2)))
            link = root / 'export.dat'
            target = root / 'elsewhere.dat'
            try:
                link.symlink_to(target)
            except OSError as exc:
                self.skipTest(f'Symlink creation unavailable: {exc}')
            storage = SteamSaveStorage()
            with self.assertRaises(FileExistsError):
                storage.save_copy(storage.read(path), link, {0: POTION})
            self.assertTrue(link.is_symlink())
            self.assertFalse(target.exists())

    def test_restore_rejects_unrelated_save_and_preserves_rollback(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "save001.dat"
            original = make_save((0, 2))
            path.write_bytes(original)
            storage = SteamSaveStorage()
            session = storage.read(path)
            session.quantities = {0: 7}
            updated, backup = storage.overwrite(session, {0: POTION})
            foreign = root / "save001.dat.foreign.bak"
            foreign.write_bytes(original[:-4] + b"fake")
            with self.assertRaisesRegex(ValueError, "outside the inventory"):
                storage.restore(updated, foreign, {0: POTION})
            self.assertEqual(path.read_bytes(), updated.original_bytes)
            restored, rollback = storage.restore(updated, backup, {0: POTION})
            self.assertEqual(restored.original_bytes, original)
            self.assertEqual(restored.quantities, {0: 2})
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(rollback.read_bytes(), updated.original_bytes)

    def test_restore_rejects_protected_and_invalid_backup_deltas(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'save001.dat'
            original = make_save((0, 2))
            path.write_bytes(original)
            storage = SteamSaveStorage()
            session = storage.read(path)
            backup = root / 'save001.dat.foreign.bak'
            for entry in ((3200, 1), (9998, 99), (1, 99)):
                with self.subTest(entry=entry):
                    backup.write_bytes(make_save((0, 2), entry))
                    with self.assertRaisesRegex(ValueError, 'protected or invalid'):
                        storage.restore(session, backup, {0: POTION, 1: MASTER, 3200: MASTER})
                    self.assertEqual(path.read_bytes(), original)

    def test_restore_cannot_grant_dlc_absent_from_the_current_slot(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'save001.dat'
            original = make_save((4038, 1))
            path.write_bytes(original)
            storage = SteamSaveStorage()
            catalog = {4038: CatalogItem('Cover', '', 'equipment', 1, 0xC5, 0, dlc_pack=212)}
            session = storage.read(path)
            session.quantities = {}
            updated, backup = storage.overwrite(session, catalog)
            with self.assertRaisesRegex(ValueError, 'protected or invalid'):
                storage.restore(updated, backup, catalog)
            self.assertEqual(storage.read(path).quantities, {})
            self.assertEqual(backup.read_bytes(), original)
            recovery = storage.save_copy(storage.read(backup), path.with_name('recovery.dat'), catalog)
            self.assertEqual(recovery.read_bytes(), original)

    def test_latest_skips_incompatible_slots_and_sidecars(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            older = root / "save001.dat"
            latest = root / "autosave00.dat"
            invalid = root / "save019.dat"
            sidecar = root / "autosave00_t.dat"
            clear = root / "save200.dat"
            for index, path in enumerate((older, latest, invalid, sidecar, clear), 1):
                path.write_bytes(b"not a slot" if path == invalid else make_save((0, index)))
                os.utime(path, (index, index))
            session = SteamSaveStorage().latest(root)
            self.assertEqual(session.source, latest.resolve())
            self.assertEqual(session.quantities, {0: 2})

    def test_backup_can_be_restored_as_a_new_slot_without_mutating_it(self):
        original = make_save((0, 2), (6000, 8))
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "save001.dat"
            target.write_bytes(original)
            storage = SteamSaveStorage()
            session = storage.read(target)
            session.quantities = {0: 7, 6000: 8}
            updated, backup = storage.overwrite(session, {0: POTION})
            self.assertFalse(updated.changed)
            self.assertEqual(updated.quantities, {0: 7, 6000: 8})
            self.assertEqual(backup.read_bytes(), original)
            restored = storage.read(backup)
            with self.assertRaisesRegex(ValueError, "backup is open"):
                storage.overwrite(restored, {0: POTION})
            copy = storage.save_copy(restored, root / "restored.dat", {})
            self.assertEqual(copy.read_bytes(), original)
            self.assertEqual(backup.read_bytes(), original)
