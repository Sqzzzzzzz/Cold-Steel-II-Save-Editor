"""Inventory sessions and the file adapter for Cold Steel II on Steam."""

from collections.abc import Mapping
import os
from pathlib import Path
import re

from cs2 import INVENTORY_END, INVENTORY_OFFSET, SLOTS, Save
from item_catalog import CatalogItem


def _saved_games() -> Path:
    if os.name == "nt":
        import ctypes
        from uuid import UUID

        folder_id = (ctypes.c_ubyte * 16).from_buffer_copy(
            UUID("4c5c32ff-bb9d-43b0-b5b4-2d72e54eaaa4").bytes_le
        )
        result = ctypes.c_wchar_p()
        status = ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(result))
        try:
            if status == 0 and result.value:
                return Path(result.value)
        finally:
            ctypes.windll.ole32.CoTaskMemFree(result)
    return Path.home() / "Saved Games"


STEAM_SAVE_DIRECTORY = _saved_games() / "Falcom" / "ed8_2"
SLOT_NAME = re.compile(r"(?:save[01]\d{2}|autosave\d{2})\.dat", re.IGNORECASE)


class InventorySession:
    def __init__(self, quantities: Mapping[int, int]):
        self.original_items = dict(quantities)
        self.quantities = self.original_items

    @property
    def changed(self) -> bool:
        return self.quantities != self.original_items

    @property
    def occupied_count(self) -> int:
        return len(self.quantities)

class SteamInventorySession(InventorySession):
    capacity = SLOTS

    def __init__(self, source: Path, save: Save):
        super().__init__(save.items)
        self.source = source
        self.original_bytes = save.original
        self.equipped_masters = frozenset(save.equipped_masters)
        self.equipped_covers = frozenset(save.equipped_covers)
        try:
            self.modified_at = source.stat().st_mtime
        except OSError:
            self.modified_at = None


class SteamSaveStorage:
    def read(self, path: Path) -> SteamInventorySession:
        source = path.resolve()
        return SteamInventorySession(source, Save.open(source))

    def latest(self, directory: Path) -> SteamInventorySession:
        candidates = []
        if directory.is_dir():
            for path in directory.iterdir():
                if SLOT_NAME.fullmatch(path.name):
                    try:
                        candidates.append((path.stat().st_mtime_ns, path))
                    except OSError:
                        continue
        for _, path in sorted(candidates, key=lambda entry: (entry[0], entry[1].name), reverse=True):
            try:
                return self.read(path)
            except (OSError, ValueError):
                continue
        raise FileNotFoundError("No compatible Cold Steel II Steam slots were found.")

    def save_copy(
        self, session: SteamInventorySession, destination: Path, catalog: Mapping[int, CatalogItem]
    ) -> Path:
        if not destination.suffix:
            destination = destination.with_suffix(".dat")
        if destination.suffix.lower() != ".dat":
            raise ValueError("Choose a .dat file for the save copy.")
        if destination.resolve() == session.source:
            raise ValueError("Use Save with backup to replace the opened slot.")
        # Preserve the leaf so an existing link is rejected by publish_new.
        destination = destination.parent.resolve() / destination.name
        self._prepare(session, catalog).write(destination, original_path=False)
        return destination

    def overwrite(
        self, session: SteamInventorySession, catalog: Mapping[int, CatalogItem]
    ) -> tuple[SteamInventorySession, Path | None]:
        if session.source.suffix.lower() != ".dat":
            raise ValueError("Save a new .dat copy when a backup is open.")
        save = self._prepare(session, catalog)
        backup = save.write(session.source, original_path=True)
        return SteamInventorySession(session.source, Save(save.edited_bytes())), backup

    def restore(
        self, session: SteamInventorySession, backup: Path, catalog: Mapping[int, CatalogItem],
    ) -> tuple[SteamInventorySession, Path | None]:
        target = session.source
        if (target.suffix.lower() != ".dat" or backup.parent.resolve() != target.parent
                or not backup.name.startswith(target.name + ".") or backup.suffix.lower() != ".bak"):
            raise ValueError("Select a backup belonging to the opened slot.")
        previous = Save.open(backup)
        snapshot = Save(session.original_bytes)
        if (previous.original[:INVENTORY_OFFSET] != snapshot.original[:INVENTORY_OFFSET]
                or previous.original[INVENTORY_END:] != snapshot.original[INVENTORY_END:]):
            raise ValueError("The backup does not match this slot outside the inventory.")
        try:
            self._apply_quantities(snapshot, previous.original_items, catalog)
        except ValueError as exc:
            raise ValueError("The backup changes protected or invalid inventory entries.") from exc
        rollback = snapshot.replace_inventory(target, previous)
        return SteamInventorySession(target, previous), rollback

    @staticmethod
    def _prepare(session: SteamInventorySession, catalog: Mapping[int, CatalogItem]) -> Save:
        save = Save(session.original_bytes)
        SteamSaveStorage._apply_quantities(save, session.quantities, catalog)
        return save

    @staticmethod
    def _apply_quantities(save: Save, quantities: Mapping[int, int], catalog: Mapping[int, CatalogItem]):
        # Apply removals first so they free slots in a full inventory.
        for item_id in save.original_items.keys() - quantities.keys():
            if item_id not in catalog:
                raise ValueError("This item cannot be edited.")
            save.set_quantity(item_id, 0, catalog[item_id])
        for item_id, quantity in quantities.items():
            if save.original_items.get(item_id) != quantity:
                if item_id not in catalog:
                    raise ValueError("This item cannot be edited.")
                save.set_quantity(item_id, quantity, catalog[item_id])
