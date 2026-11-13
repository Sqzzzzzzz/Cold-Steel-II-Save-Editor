"""Focused checks for the memory-only controller and the transplanted Qt window."""

import os
from dataclasses import replace
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
from threading import Event
from unittest import TestCase, skipUnless
from unittest.mock import patch

from PySide6.QtCore import QItemSelectionModel, QPoint, QSettings, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QStyle, QStyleOptionButton

from item_catalog import CatalogItem, NOTEBOOK_IDS
from edit_changes import EditChanges
from qt_backend import EditorCore, ITEM_TABLE, STEAM_GAME, ScanResult, find_game_install, scan_game_tables, write_csv
from qt_changes_dialog import ChangesDialog
from qt_window import MainWindow
from cs2 import INVENTORY_END, INVENTORY_OFFSET, SAVE_HEADER, SAVE_SIZE
from save_storage import STEAM_SAVE_DIRECTORY, SteamSaveStorage
from test_cs2 import make_save


class PreviewTests(TestCase):
    def test_discovery_finds_game_in_a_secondary_steam_library(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            steam = root / "Steam"
            library = root / "Another Steam Library"
            (steam / "steamapps").mkdir(parents=True)
            game = library / "steamapps/common/Trails of Cold Steel II"
            (game / ITEM_TABLE).parent.mkdir(parents=True)
            (game / ITEM_TABLE).touch()
            escaped = str(library).replace("\\", "\\\\")
            (steam / "steamapps/libraryfolders.vdf").write_text(f'"path" "{escaped}"', encoding="utf-8")
            default = steam / "steamapps/common/Trails of Cold Steel II"
            with patch("qt_backend.STEAM_GAME", default):
                if os.name == "nt":
                    with patch("winreg.OpenKey", side_effect=OSError):
                        self.assertEqual(find_game_install(), game)
                else:
                    self.assertEqual(find_game_install(), game)

    def test_invalid_optional_translation_does_not_hide_the_game_catalog(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            table = root / ITEM_TABLE
            table.parent.mkdir(parents=True)
            table.touch()
            translations = root / "item-text.json"
            for content in ('{"ru":', '[]', '{"ru":{"0":["Missing description"]}}'):
                with (self.subTest(content=content), patch("qt_backend.ITEM_TEXT", translations),
                      patch("qt_backend.read_catalog", return_value={0: CatalogItem("Tear Balm", "", "items", 99, 0x81, 0)})):
                    translations.write_text(content, encoding="utf-8")
                    result = scan_game_tables(root)
                    self.assertEqual(result.items[0].name, "Tear Balm")
                    self.assertFalse(result.translations)
                    self.assertIn("The optional item translations could not be loaded.", result.errors)

    def test_missing_russian_translation_uses_original_english_text(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            profile = QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
            core = EditorCore(profile=profile)
            items = {
                0: CatalogItem("Tear Balm", "Restores 800 HP", "items", 99, 0x81, 0),
                1: CatalogItem("Зелье", "Восстанавливает здоровье", "items", 99, 0x81, 0),
            }
            core.apply_scan_result(ScanResult(root, (), items))
            self.assertEqual(core.item_name(0), "Tear Balm")
            self.assertEqual(core.details_text(0), "Restores 800 HP")
            self.assertEqual(core.item_name(1), "Зелье")
            core.set_language("en")
            self.assertEqual(core.item_name(0), "Tear Balm")
            self.assertEqual(core.item_name(1), "Item #1")
            self.assertEqual(core.details_text(1), "")

    def test_standalone_dictionary_localizes_russian_text_and_preserves_english(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            table = root / ITEM_TABLE
            table.parent.mkdir(parents=True)
            table.touch()
            dictionary = root / "item-text.json"
            dictionary.write_text(
                '{"ru":{"0":["Зелье «Тиа»","Восполняет ОЗ"]},'
                '"ru_master_effects":{"Evasion up":"Повышает уклонение"}}',
                encoding="utf-8",
            )
            items = {0: CatalogItem("Tear Balm", "Restores HP", "items", 99, 0x81, 0)}
            profile = QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
            core = EditorCore(profile=profile)
            with (patch("qt_backend.BUNDLED_ITEM_TEXT", dictionary),
                  patch("qt_backend.ITEM_TEXT", root / "missing.json"),
                  patch("qt_backend.read_catalog", return_value=items),
                  patch("qt_backend.MASTER_TABLE", ITEM_TABLE),
                  patch("qt_backend.read_master_quartz_effects",
                        return_value={3200: ("Evasion up", "Accuracy up")})):
                core.apply_scan_result(scan_game_tables(root))
            for language, name, description in (("ru", "Зелье «Тиа»", "Восполняет ОЗ"),
                                                ("en", "Tear Balm", "Restores HP"),
                                                ("ru", "Зелье «Тиа»", "Восполняет ОЗ")):
                core.set_language(language)
                self.assertEqual((core.item_name(0), core.details_text(0)), (name, description))
                first_effect = "Повышает уклонение" if language == "ru" else "Evasion up"
                self.assertEqual(core.master_effect_titles(3200), (first_effect, "Accuracy up"))

    def test_invalid_profile_fields_are_discarded(self):
        with TemporaryDirectory() as directory:
            profile = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            profile.setValue("preview/preferences", '{"favorites":null,"recent":[{},true,0,0,7],"save_directory":42}')
            core = EditorCore(profile=profile)
            self.assertEqual(core.favorites, set())
            self.assertEqual(core.recent, [0, 7])
            self.assertEqual(core.save_directory.name, "ed8_2")

    def test_explicit_launch_slot_can_open_without_retargeting_latest(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            profile = QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
            core = EditorCore(profile=profile, storage=SteamSaveStorage())
            slot = root / "save000.dat"
            slot.write_bytes(make_save((0, 2)))
            core.use_opened_save(core.read_save(slot), remember_directory=False)
            self.assertEqual(core.source, slot.resolve())
            self.assertEqual(core.save_directory, STEAM_SAVE_DIRECTORY)

    def test_latest_falls_back_to_steam_after_opening_a_copy_folder(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            steam = root / 'steam'
            steam.mkdir()
            path = steam / 'save001.dat'
            path.write_bytes(make_save((0, 2)))
            profile = QSettings(str(root / 'settings.ini'), QSettings.Format.IniFormat)
            core = EditorCore(profile=profile, storage=SteamSaveStorage())
            core.settings['save_directory'] = str(root)
            with patch('qt_backend.STEAM_SAVE_DIRECTORY', steam):
                self.assertEqual(core.read_save().source, path.resolve())

    def test_csv_is_safe_to_open_and_refuses_to_replace_existing_file(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "inventory.csv"
            write_csv(target, [(0, "Tear Balm", 3), (1, "  =1+1", 2)])
            data = target.read_bytes()
            self.assertIn("Tear Balm,3", data.decode("utf-8-sig"))
            self.assertIn("'  =1+1,2", data.decode("utf-8-sig"))
            with self.assertRaises(FileExistsError):
                write_csv(target, [(0, "Tear Balm", 8)])
            self.assertEqual(target.read_bytes(), data)
            self.assertEqual(list(target.parent.iterdir()), [target])

    def test_batch_is_atomic_and_review_uses_the_original_sample(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            profile = QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
            core = EditorCore(profile=profile)
            potion = CatalogItem("Tear Balm", "Restores 800 HP", "items", 99, 0x81, 0)
            master = CatalogItem("Force", "", "master", 1, 0xC9, 3)
            core.apply_scan_result(ScanResult(root, (), {0: potion, 3200: master}))
            self.assertIsNone(core.storage)
            initial = core.save.quantities.copy()
            with self.assertRaisesRegex(ValueError, "between 0 and 1"):
                core.change({0: 10, 3200: 2})
            self.assertEqual(core.save.quantities, initial)
            self.assertFalse(core.undo_stack)

            core.change({0: 10, 3200: 0})
            review = EditChanges()
            review.refresh(core.save)
            self.assertEqual(review.counts(), {"added": 0, "removed": 1, "modified": 1})
            self.assertTrue(core.undo())
            review.refresh(core.save)
            self.assertFalse(review.changes)
            self.assertEqual(core.save.quantities, initial)
            self.assertEqual([path.name for path in root.iterdir()], ["settings.ini"])


class CleanWindowTests(TestCase):
    def test_color_crest_survives_game_art_loading_and_fits_the_rail(self):
        app = QApplication.instance() or QApplication([])
        with TemporaryDirectory() as directory:
            root = Path(directory)
            profile = QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
            crest = root / "thors-color.png"
            sample = QPixmap(160, 190)
            sample.fill(QColor("#fc220a"))
            self.assertTrue(sample.save(str(crest)))
            with patch("qt_window.BUNDLED_COLOR_CREST", crest), patch("qt_window.COLOR_CREST", root / "missing.png"):
                window = MainWindow(EditorCore(profile=profile))
            window.initial_load_timer.stop()
            window.show()
            try:
                window.on_art_ready(root, root)
                for size in (QSize(1536, 864), QSize(1138, 619)):
                    window.fit_work_area(size)
                    app.processEvents()
                    self.assertEqual(window.crest.pixmap().toImage().pixelColor(10, 10), QColor("#fc220a"))
                    rail = window.rail_crest.grab().toImage()
                    color = rail.pixelColor(rail.width() // 2, rail.height() - 25)
                    self.assertGreater(color.red(), color.green() + 100)
                    self.assertLess(window.rail_crest.geometry().bottom(), window.rail_file.geometry().top())
            finally:
                window.close()
                app.processEvents()

    def test_smaller_work_area_scrolls_without_changing_standard_layout(self):
        app = QApplication.instance() or QApplication([])
        with TemporaryDirectory() as directory:
            profile = QSettings(str(Path(directory) / 'settings.ini'), QSettings.Format.IniFormat)
            window = MainWindow(EditorCore(profile=profile))
            window.initial_load_timer.stop()
            window.show()
            try:
                self.assertIs(window.centralWidget(), window.canvas)
                small = QSize(1138, 619)
                window.fit_work_area(small)
                app.processEvents()
                viewport = window.centralWidget()
                self.assertEqual(window.size(), small)
                self.assertGreater(viewport.horizontalScrollBar().maximum(), 0)
                self.assertGreater(viewport.verticalScrollBar().maximum(), 0)
                close = window.window_buttons['close']
                point = close.mapTo(window.canvas, close.rect().center())
                viewport.ensureVisible(point.x(), point.y())
                self.assertTrue(viewport.viewport().rect().contains(close.mapTo(viewport.viewport(), close.rect().center())))
                window.fit_work_area(QSize(1536, 864))
                self.assertIs(window.centralWidget(), window.canvas)
            finally:
                window.close()
                app.processEvents()

    def test_opening_save_keeps_first_launch_visible_until_catalog_loads(self):
        app = QApplication.instance() or QApplication([])
        with TemporaryDirectory() as directory:
            root = Path(directory)
            profile = QSettings(str(root / 'settings.ini'), QSettings.Format.IniFormat)
            core = EditorCore(profile=profile, storage=SteamSaveStorage())
            window = MainWindow(core)
            window.initial_load_timer.stop()
            window.show()
            try:
                slot = root / 'save001.dat'
                slot.write_bytes(make_save((0, 2)))
                window._open_save_finished(core.read_save(slot))
                self.assertEqual(core.source, slot.resolve())
                self.assertTrue(window.startup_page.isVisible())
                potion = CatalogItem('Sample Potion', 'Restores health', 'items', 99, 0x81, 0)
                core.apply_scan_result(ScanResult(root, (), {0: potion}))
                window.refresh_catalog()
                self.assertTrue(window.invpage.isVisible())
                self.assertEqual(window.inv_table.model().rowCount(), 1)
            finally:
                window.close()
                app.processEvents()

    def test_close_pending_file_failure_keeps_edits_and_window_open(self):
        app = QApplication.instance() or QApplication([])
        with TemporaryDirectory() as directory:
            root = Path(directory)
            profile = QSettings(str(root / 'settings.ini'), QSettings.Format.IniFormat)
            core = EditorCore(profile=profile)
            potion = CatalogItem('Sample Potion', 'Restores health', 'items', 99, 0x81, 0)
            core.apply_scan_result(ScanResult(root, (), {0: potion}))
            window = MainWindow(core)
            window.initial_load_timer.stop()
            window.show()
            core.change({0: 12})
            failed = Event()

            def write():
                if failed.wait(2):
                    raise OSError('Simulated write failure')
                raise TimeoutError('Test did not release the worker')

            try:
                window._run_file(write, lambda _: None)
                self.assertFalse(window.close())
                with patch.object(QMessageBox, 'warning') as warning:
                    failed.set()
                    for _ in range(100):
                        if window._file_job is None:
                            break
                        QTest.qWait(15)
                    self.assertIsNone(window._file_job)
                    warning.assert_called_once()
                self.assertTrue(window.isVisible())
                self.assertEqual(core.quantity(0), 12)
                with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No) as confirm:
                    self.assertFalse(window.close())
                    confirm.assert_called_once()
            finally:
                failed.set()
                core.reset()
                window.close()
                app.processEvents()

    def test_catalog_and_language_switch_with_a_synthetic_table(self):
        app = QApplication.instance() or QApplication([])
        with TemporaryDirectory() as directory:
            root = Path(directory)
            profile = QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
            core = EditorCore(profile=profile)
            potion = CatalogItem("Sample Potion", "Restores health", "items", 99, 0x81, 0)
            core.apply_scan_result(ScanResult(root, (), {0: potion}, translations={
                "ru": {0: ("Пробное зелье", "Восстанавливает здоровье")}
            }))
            window = MainWindow(core)
            window.initial_load_timer.stop()
            try:
                window.show()
                window.navigate_section("catalog")
                model = window.cat_table.model()
                window.cat_table.selectRow(0)
                self.assertEqual(model.index(0, 0).data(), "Пробное зелье")
                self.assertIn("Восстанавливает здоровье", window.description.toPlainText())
                window.lang.setCurrentIndex(1)
                self.assertEqual(model.index(0, 0).data(), "Sample Potion")
                self.assertEqual(window.item_name.accessibleName(), "Sample Potion")
                self.assertIn("Restores health", window.description.toPlainText())
                window.lang.setCurrentIndex(0)
                self.assertIn("Восстанавливает здоровье", window.description.toPlainText())
                window.cat_search.setText("unmatched")
                window.update_tables("catalog")
                self.assertEqual(model.rowCount(), 0)
                self.assertFalse(window.apply_btn.isEnabled())
            finally:
                window.close()
                app.processEvents()


@skipUnless((STEAM_GAME / ITEM_TABLE).is_file(), "Cold Steel II Steam item table unavailable")
class NativeWindowTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.scan = scan_game_tables(STEAM_GAME)

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        profile = QSettings(str(Path(self.directory.name) / "settings.ini"), QSettings.Format.IniFormat)
        self.core = EditorCore(profile=profile)
        self.core.apply_scan_result(self.scan)
        self.window = MainWindow(self.core)
        self.window.initial_load_timer.stop()
        self.window.show()
        self.app.processEvents()
        self.addCleanup(self.close_window)

    def close_window(self):
        self.core.reset()
        self.window._quantity_user_edited = False
        self.window.close()
        self.app.processEvents()

    def test_tabs_search_sort_multiselection_and_language(self):
        window = self.window
        self.assertEqual(set(window.navigation), {"catalog", "inventory", "tools"})
        model = window.cat_table.model()
        self.assertEqual(model.rowCount(), len(self.core.visible()))
        window.cat_table.selectRow(0)
        self.assertEqual(window.active_item_id, 0)
        window.cat_search.setText("___no_item___")
        QTest.qWait(200)
        self.assertEqual(model.rowCount(), 0)
        self.assertIsNone(window.active_item_id)
        self.assertFalse(window.apply_btn.isEnabled())
        window.cat_search.clear()
        QTest.qWait(200)

        header = window.cat_table.horizontalHeader()
        point = QPoint(header.sectionViewportPosition(1) + 15, header.height() // 2)
        QTest.mouseClick(header.viewport(), Qt.MouseButton.LeftButton, pos=point)
        last_id = max(i for i in self.core.visible() if isinstance(i,int))
        self.assertEqual(model.index(0, 0).data(Qt.ItemDataRole.UserRole), last_id)
        window.sort_rows("catalog", 1)
        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        for row in (0, 1):
            window.cat_table.selectionModel().select(window.cat_table.model().index(row, 0), flags)
        self.assertEqual(len(window.selected_ids(window.cat_table)), 2)
        self.assertTrue(window.bulk_bar.isVisible())
        window.add_one.click()
        self.assertEqual(self.core.quantity(0), 1)
        self.assertEqual(self.core.quantity(1), 1)
        window.undo_btn.click()
        self.assertEqual(self.core.quantity(0), self.core.save.original_items[0])

        window.cat_table.selectRow(0)
        window.qty.setValue(27)
        self.assertTrue(window.has_pending_quantity())
        window.cat_tree.setCurrentItem(window._category_nodes["catalog"]["quartz_master"])
        self.assertEqual(model.rowCount(), 31)
        window.cat_table.selectRow(12)
        self.assertEqual(window.qty.maximum(), 1)
        self.assertFalse(window.has_pending_quantity())
        window.lang.setCurrentIndex(1)
        self.assertEqual(window.tabinv.text(), "My inventory")
        self.assertEqual(model.headerData(0, Qt.Orientation.Horizontal), "Item")
        window.tabinv.click()
        self.assertIs(window.pages.currentWidget(), window.invpage)
        window.navigation["tools"].click()
        self.assertIs(window.pages.currentWidget(), window.toolspage)
        self.assertFalse(window.detail.isVisible())

    def test_catalog_filters_read_only_reference_rows_and_dlc(self):
        window = self.window
        model = window.cat_table.model()
        self.assertGreater(model.rowCount(), 1000)
        self.assertFalse(model.index_for_id(250).isValid())
        window.cat_tree.setCurrentItem(window._category_nodes["catalog"]["fish"])
        self.assertEqual(model.rowCount(), 24)
        window.cat_table.selectRow(0)
        self.assertFalse(window.apply_btn.isEnabled())
        self.assertFalse(window._icon("fish:0").isNull())
        window.cat_tree.setCurrentItem(window._category_nodes["catalog"]["dlc_pack"])
        self.assertEqual({row.item_id for row in model.rows}, set(self.scan.dlc))
        self.assertGreater(model.rowCount(), 100)

    def test_round_trip_genuine_steam_slots_on_copies(self):
        candidates = sorted(STEAM_SAVE_DIRECTORY.glob("*.dat"))
        sources = []
        for path in candidates:
            if path.stat().st_size != SAVE_SIZE:
                continue
            with path.open("rb") as stream:
                if stream.read(len(SAVE_HEADER)) == SAVE_HEADER:
                    sources.append(path)
        if not sources:
            self.skipTest("No genuine Cold Steel II Steam saves available")
        root = Path(self.directory.name)
        storage = SteamSaveStorage()
        for source in sources:
            with self.subTest(slot=source.name):
                slot = root / source.name
                copyfile(source, slot)
                session = storage.read(slot)
                original = session.original_bytes
                editable = [i for i in range(11) if i in session.quantities]
                candidate = session.quantities.copy()
                if editable:
                    key = editable[0]
                    candidate[key] += 1 if candidate[key] < 99 else -1
                if len(editable) > 1:
                    del candidate[editable[1]]
                missing = next((i for i in range(11, 35) if i not in session.quantities), None)
                if missing is not None:
                    candidate[missing] = 1
                if candidate == session.original_items:
                    continue
                session.quantities = candidate
                exported = storage.save_copy(session, root / (source.stem + "_edited.dat"), self.scan.items)
                self.assertEqual(slot.read_bytes(), original)
                updated, backup = storage.overwrite(session, self.scan.items)
                result = exported.read_bytes()
                self.assertEqual(result, slot.read_bytes())
                self.assertEqual(storage.read(exported).quantities, candidate)
                self.assertEqual(result[:INVENTORY_OFFSET], original[:INVENTORY_OFFSET])
                self.assertEqual(result[INVENTORY_END:], original[INVENTORY_END:])
                self.assertEqual(backup.read_bytes(), original)
                restored, rollback = storage.restore(updated, backup, self.scan.items)
                self.assertEqual(restored.original_bytes, original)
                self.assertEqual(restored.quantities, session.original_items)
                self.assertEqual(slot.read_bytes(), original)
                self.assertEqual(rollback.read_bytes(), result)

    def test_genuine_quartz_master_and_equipment_on_a_copy(self):
        source = STEAM_SAVE_DIRECTORY / "save000.dat"
        if not source.is_file():
            self.skipTest("No genuine save000.dat available")
        slot = Path(self.directory.name) / source.name
        copyfile(source, slot)
        storage = SteamSaveStorage()
        session = storage.read(slot)
        catalog = self.scan.items
        quartz = next((item_id for item_id, item in catalog.items()
                       if item.icon_type == 0xC8 and item.editable and item.dlc_pack is None
                       and 0 < session.quantities.get(item_id, 0) < item.limit), None)
        master = next((item_id for item_id, item in catalog.items()
                       if item.icon_type == 0xC9 and item.editable and item.dlc_pack is None
                       and item_id not in session.quantities and item_id not in session.equipped_masters), None)
        equipment = next((item_id for item_id, item in catalog.items()
                          if item.category == "equipment" and item.editable and item.dlc_pack is None
                          and item_id in session.quantities and item_id not in session.equipped_covers), None)
        if None in (quartz, master, equipment):
            self.skipTest("The slot lacks suitable items for this round trip")
        candidate = dict(session.quantities)
        candidate[quartz] += 1
        candidate[master] = 1
        del candidate[equipment]
        session.quantities = candidate
        updated, backup = storage.overwrite(session, catalog)
        self.assertEqual(storage.read(slot).quantities, candidate)
        self.assertEqual(updated.equipped_masters, session.equipped_masters)
        self.assertEqual(updated.original_bytes[:INVENTORY_OFFSET], session.original_bytes[:INVENTORY_OFFSET])
        self.assertEqual(updated.original_bytes[INVENTORY_END:], session.original_bytes[INVENTORY_END:])
        restored, _ = storage.restore(updated, backup, catalog)
        self.assertEqual(restored.quantities, session.original_items)
        self.assertEqual(slot.read_bytes(), session.original_bytes)

    def test_actual_item_art_stats_and_master_effects(self):
        window = self.window
        window.lang.setCurrentIndex(1)
        model = window.cat_table.model()
        for item_id in (0, 400, 3200, 3388):
            window.cat_table.selectRow(model.index_for_id(item_id).row())
            self.assertFalse(window.big_icon.pixmap().isNull())
        self.assertIn("ATS +150", window.description.toPlainText())
        self.assertIn("ADF -150", window.description.toPlainText())
        window.cat_table.selectRow(model.index_for_id(3200).row())
        self.assertIn("Effects unlocked by level", window.description.toPlainText())
        for effect in self.scan.master_effects[3200]:
            self.assertIn(effect, window.description.toPlainText())

    def test_missing_checkbox_shows_a_tick_and_still_toggles_the_filter(self):
        checkbox = self.window.missing
        option = QStyleOptionButton()
        checkbox.initStyleOption(option)
        indicator = checkbox.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, checkbox)
        unchecked = checkbox.grab(indicator).toImage()
        count = self.window.cat_table.model().rowCount()
        QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton, pos=indicator.center())
        self.assertTrue(checkbox.isChecked())
        self.assertLess(self.window.cat_table.model().rowCount(), count)
        checkbox.initStyleOption(option)
        self.assertEqual(checkbox.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, checkbox), indicator)
        checked = checkbox.grab(indicator).toImage()
        dpr = checkbox.devicePixelRatioF()
        margin = round(3 * dpr)
        interior = [(x, y) for y in range(margin, checked.height() - margin)
                    for x in range(margin, checked.width() - margin)]
        self.assertTrue(all(unchecked.pixelColor(x, y).lightness() < 100 for x, y in interior))
        self.assertGreater(sum(checked.pixelColor(x, y).lightness() > 215 for x, y in interior), 8)
        QTest.keyClick(checkbox, Qt.Key.Key_Space)
        self.assertFalse(checkbox.isChecked())
        self.assertEqual(self.window.cat_table.model().rowCount(), count)

    def test_category_sort_and_tabs_preserve_selection_where_visible(self):
        window = self.window
        table = window.cat_table
        model = table.model()
        nodes = window._category_nodes["catalog"]
        self.core.toggle_favorite(0)
        table.verticalScrollBar().setValue(600)
        window.cat_tree.setCurrentItem(nodes["consumable"])
        self.assertEqual(table.verticalScrollBar().value(), 0)
        nodes["equipment"].setExpanded(False)
        window.cat_quick_favorite.click()
        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(model.index(0, 0).data(Qt.ItemDataRole.UserRole), 0)
        self.assertFalse(window.cat_tree.selectedItems())
        window.cat_tree.setCurrentItem(nodes["consumable"])
        self.assertFalse(window.cat_quick_favorite.isChecked())
        self.assertGreater(model.rowCount(), 1)
        window.cat_quick_favorite.click()
        window.cat_quick_favorite.click()
        self.assertEqual(window.cat_tree.selectedItems(), [nodes["consumable"]])
        window.cat_tree.setCurrentItem(nodes["all"])
        table.selectRow(100)
        selected_id = window.active_item_id
        table.verticalScrollBar().setValue(90)
        top_id = model.index(table.rowAt(0), 0).data(Qt.ItemDataRole.UserRole)
        window.sort_rows("catalog", 1)
        self.assertEqual(window.active_item_id, selected_id)
        self.assertEqual(model.index(table.rowAt(0), 0).data(Qt.ItemDataRole.UserRole), top_id)
        window.lang.setCurrentIndex(1)
        self.assertFalse(nodes["equipment"].isExpanded())
        window.tabinv.click()
        self.assertIsNone(window.active_item_id)
        self.assertFalse(window.favorite_btn.isEnabled())
        self.assertIn("Select an item", window.description.toPlainText())
        window.tabcat.click()
        self.assertEqual(window.active_item_id, selected_id)

    def test_item_details_and_quantity_buttons(self):
        window = self.window
        table = window.cat_table
        table.selectRow(0)
        self.assertEqual(window.id_field.text(), "0")
        self.assertIn("99", window.qty_caption.toolTip())
        self.assertFalse(window.apply_btn.isEnabled())
        window.qty.setValue(27)
        window.lang.setCurrentIndex(1)
        self.assertEqual(window.qty.value(), 27)
        self.assertTrue(window.has_pending_quantity())
        self.assertTrue(window.apply_btn.isEnabled())
        window.apply_btn.click()
        self.assertEqual(self.core.quantity(0), 27)
        self.assertFalse(window.apply_btn.isEnabled())
        window.delete_btn.click()
        self.assertEqual(self.core.quantity(0), 0)
        self.assertFalse(window.delete_btn.isEnabled())
        window.undo_btn.click()
        self.assertEqual(self.core.quantity(0), 27)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            window.reset_btn.click()
        self.assertEqual(self.core.quantity(0), self.core.save.original_items[0])
        self.assertFalse(window.reset_btn.isEnabled())

        item_id = next(i for i, item in self.core.native.items() if item.editable and item.stats and item.stats[0])
        table.selectRow(table.model().index_for_id(item_id).row())
        item = self.core.native[item_id]
        self.assertIn(item.description.strip(), window.description.toPlainText())
        self.assertIn(f"STR +{item.stats[0]}", window.description.toPlainText())
        self.assertFalse(window.big_icon.pixmap().isNull())

    def test_file_buttons_have_memory_only_previews(self):
        window = self.window
        self.core.change({0: 42})
        window.update_tables()
        dialog = ChangesDialog(window, "overwrite")
        self.assertEqual(dialog.table.rowCount(), 1)
        self.assertFalse(dialog.proceed.isEnabled())
        self.assertIn("Запись игровых файлов", dialog.note.text())
        with patch.object(window, "show_changes") as review:
            window.btn_overwrite.click()
            review.assert_called_with("overwrite")
            window.btn_savecopy.click()
            review.assert_called_with("copy")
        with patch.object(QMessageBox, "information") as compare:
            window.btn_compare.click()
            self.assertIn("Изменено: 1", compare.call_args.args[2])
        with (
            patch.object(QFileDialog, "getOpenFileName") as picker,
            patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No),
        ):
            window.btn_open.click()
            picker.assert_not_called()
        self.assertEqual(self.core.quantity(0), 42)
        self.assertEqual(list(Path(self.directory.name).glob("*.dat")), [])

    def test_overwrite_keeps_gui_responsive_and_preserves_pending_quantity(self):
        entered = Event()
        release = Event()

        class GatedStorage(SteamSaveStorage):
            def overwrite(self, session, catalog):
                entered.set()
                if not release.wait(2):
                    raise TimeoutError("The GUI did not release the background write.")
                return super().overwrite(session, catalog)

        window = self.window
        self.core.storage = GatedStorage()
        target = Path(self.directory.name) / "save001.dat"
        original = make_save((0, 4), (1, 2))
        target.write_bytes(original)
        self.assertTrue(window.open_save(target))
        self.wait_for_file_job()
        self.assertEqual(self.core.source, target)
        window.tabcat.click()
        window.cat_table.selectRow(0)
        self.core.change({0: 6, 1: 0, 4: 1})
        window.update_tables()
        window.show_item(0)
        window.qty.setValue(12)
        with patch.object(window, "show_changes", return_value=True):
            window.btn_overwrite.click()
        try:
            self.assertTrue(entered.wait(1))
            self.assertFalse(window.qty.isEnabled())
            self.assertFalse(window.btn_overwrite.isEnabled())
            self.assertFalse(window.open_save(target))
            self.assertEqual(target.read_bytes(), original)
            window.lang.setCurrentIndex(1)
            self.assertEqual(window.qty.value(), 12)
            QTimer.singleShot(20, release.set)
            self.wait_for_file_job()
        finally:
            release.set()
        self.assertEqual(self.core.save.quantities, {0: 6, 4: 1})
        self.assertEqual(self.core.last_backup.read_bytes(), original)
        self.assertEqual(self.core.compare(self.core.last_backup), (1, 1, 1))
        self.assertEqual(window.qty.value(), 12)
        self.assertTrue(window.has_pending_quantity())
        self.assertTrue(window.apply_btn.isEnabled())

    def test_closing_during_compare_does_not_open_a_result_dialog(self):
        window = self.window
        release = Event()

        def compare():
            release.wait(1)
            return 0, 0, 0

        self.assertTrue(window._run_file(compare, window._show_comparison))
        with patch.object(QMessageBox, "information") as report:
            self.assertFalse(window.close())
            release.set()
            self.wait_for_file_job()
            QTest.qWait(15)
            report.assert_not_called()
            self.assertFalse(window.isVisible())

    def test_overwrite_uses_catalog_snapshot_from_the_review(self):
        window = self.window
        self.core.storage = SteamSaveStorage()
        target = Path(self.directory.name) / "save001.dat"
        target.write_bytes(make_save((0, 4)))
        window.open_save(target)
        self.wait_for_file_job()
        self.core.change({0: 6})
        window.update_tables()
        release = Event()
        window._file_pool.submit(release.wait, 2)
        try:
            with patch.object(window, "show_changes", return_value=True):
                window.btn_overwrite.click()
            new_items = self.core.native | {0: replace(self.core.native[0], limit=5)}
            self.core.apply_scan_result(replace(self.scan, items=new_items))
            window.refresh_catalog()
        finally:
            release.set()
        self.wait_for_file_job()
        self.assertEqual(self.core.storage.read(target).quantities, {0: 6})

    def wait_for_file_job(self):
        for _ in range(100):
            if self.window._file_job is None:
                return
            QTest.qWait(15)
        self.fail("Background file job did not finish.")
