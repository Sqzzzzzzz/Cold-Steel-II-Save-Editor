"""Binary inventory records for the Cold Steel II Steam save format."""

from contextlib import contextmanager
from datetime import datetime
import os
from pathlib import Path
from struct import Struct, unpack_from
from tempfile import NamedTemporaryFile

from item_catalog import CatalogItem, EMPTY_ID


SAVE_SIZE = 493976
SAVE_HEADER = bytes.fromhex("98 89 07 00 08 00 00 00")
INVENTORY_OFFSET = 0x354EC
SLOTS = 2048
RECORD = Struct("<HH28s")
INVENTORY_END = INVENTORY_OFFSET + SLOTS * RECORD.size
EMPTY_EXTRA = bytes(28)
EMPTY_RECORD = RECORD.pack(EMPTY_ID, 0, EMPTY_EXTRA)
EMPTY_INVENTORY = EMPTY_RECORD * SLOTS
ORBMENTS_OFFSET = 0x26A4
ARCUS_COVERS_OFFSET = 0x2644
ORBMENT_SLOTS = 48
ORBMENT_SIZE = 18
MASTER_ALIASES = {3240: 3205, 3241: 3226, 3242: 3212, 3243: 3218, 3244: 3200,
                  3245: 3225, 3246: 3217, 3247: 3212, 3248: 3219}


class Save:
    def __init__(self, data: bytes):
        if len(data) != SAVE_SIZE or not data.startswith(SAVE_HEADER):
            raise ValueError("Expected a Cold Steel II Steam save (493,976 bytes, version 8).")

        items = {}
        inventory = memoryview(data)[INVENTORY_OFFSET:INVENTORY_END]
        for slot, (item_id, quantity, extra) in enumerate(RECORD.iter_unpack(inventory)):
            if item_id == EMPTY_ID:
                offset = slot * RECORD.size
                if not data.endswith(EMPTY_INVENTORY[offset:], INVENTORY_OFFSET, INVENTORY_END):
                    raise ValueError("Unrecognized inventory record in the save.")
                break
            if item_id >= EMPTY_ID or not 1 <= quantity <= 99 or extra != EMPTY_EXTRA:
                raise ValueError("Unrecognized inventory record in the save.")
            if item_id in items:
                raise ValueError(f"Duplicate inventory ID {item_id:04X} in the save.")
            items[item_id] = quantity

        self.original = data
        self.original_items = items
        self.items = items.copy()
        equipped = {
            unpack_from("<H", data, ORBMENTS_OFFSET + slot * ORBMENT_SIZE)[0]
            for slot in range(ORBMENT_SLOTS)
        } - {EMPTY_ID}
        self.equipped_masters = equipped | {MASTER_ALIASES[i] for i in equipped & MASTER_ALIASES.keys()}
        self.equipped_covers = set(unpack_from("<48H", data, ARCUS_COVERS_OFFSET)) - {EMPTY_ID}

    @classmethod
    def open(cls, path: Path) -> "Save":
        initial_path = path.stat()
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            data = stream.read(SAVE_SIZE + 1)
            read = os.fstat(stream.fileno())
        after = path.stat()
        def signature(stat):
            return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
        different_file = read.st_ino and after.st_ino and (read.st_dev, read.st_ino) != (after.st_dev, after.st_ino)
        # Path stat and fstat can report different creation-time precision on Windows.
        if (different_file or signature(before) != signature(read) or signature(initial_path) != signature(after)
                or (read.st_size, read.st_mtime_ns) != (after.st_size, after.st_mtime_ns)):
            raise ValueError("The save changed while it was being read. Reopen it.")
        return cls(data)

    @property
    def changed(self) -> bool:
        return self.items != self.original_items

    def set_quantity(self, item_id: int, quantity: int, item: CatalogItem) -> None:
        if type(item_id) is not int or not 0 <= item_id < EMPTY_ID or not item.editable:
            raise ValueError("This item cannot be edited.")
        if type(quantity) is not int or not 0 <= quantity <= min(item.limit, 99):
            raise ValueError(f"Quantity must be between 0 and {item.limit}.")
        if item_id in self.equipped_masters:
            raise ValueError("This Master Quartz is already equipped.")
        if item_id in self.equipped_covers:
            raise ValueError("This ARCUS cover is already equipped.")
        if item.dlc_pack is not None and item_id not in self.original_items:
            raise ValueError("This DLC item is not in the original inventory.")
        if quantity == 0:
            self.items.pop(item_id, None)
        else:
            if item_id not in self.items and len(self.items) >= SLOTS:
                raise ValueError("The inventory has no free slots.")
            self.items[item_id] = quantity

    def edited_bytes(self) -> bytes:
        if not self.changed:
            return self.original
        # Keep the original order when an item is removed and added back.
        records = b"".join(
            RECORD.pack(item_id, self.items[item_id], EMPTY_EXTRA)
            for item_id in dict.fromkeys((*self.original_items, *self.items))
            if item_id in self.items
        )
        empty = EMPTY_INVENTORY[len(self.items) * RECORD.size:]
        return self.original[:INVENTORY_OFFSET] + records + empty + self.original[INVENTORY_END:]

    def write(self, path: Path, *, original_path: bool) -> Path | None:
        """Publish a new copy or back up and replace the exact opened snapshot."""
        candidate = self.edited_bytes()
        parsed = Save(candidate)
        if (parsed.items != self.items
                or candidate[:INVENTORY_OFFSET] != self.original[:INVENTORY_OFFSET]
                or candidate[INVENTORY_END:] != self.original[INVENTORY_END:]):
            raise ValueError("The edited save failed verification.")
        if not original_path:
            with staged_file(path, candidate) as temporary:
                publish_new(temporary, path)
            verify_written(path, candidate)
            return None
        return self.replace_inventory(path, parsed)

    def replace_inventory(self, path: Path, replacement: "Save") -> Path | None:
        """Replace the opened snapshot with a verified save, preserving a rollback copy."""
        candidate = replacement.original
        if (candidate[:INVENTORY_OFFSET] != self.original[:INVENTORY_OFFSET]
                or candidate[INVENTORY_END:] != self.original[INVENTORY_END:]):
            raise ValueError("The backup does not match this slot outside the inventory.")

        def verify_source():
            try:
                with path.open("rb") as stream:
                    current = stream.read(SAVE_SIZE + 1)
            except FileNotFoundError:
                current = None
            if current != self.original:
                raise ValueError("The source save changed on disk. Reopen it or save a copy.")

        verify_source()
        if candidate == self.original:
            return None

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = path.with_name(f"{path.name}.{stamp}.bak")
        with staged_file(path, candidate) as temporary:
            with staged_file(backup, self.original) as staged_backup:
                publish_new(staged_backup, backup)
            verify_written(backup, self.original)
            if os.name == "nt":
                displaced = backup.with_suffix(".displaced.bak")
                try:
                    with read_without_writers(path) as stream:
                        if stream.read(SAVE_SIZE + 1) != self.original:
                            raise ValueError("The source save changed on disk. Reopen it or save a copy.")
                        replace_with_backup(path, temporary, displaced)
                except OSError:
                    # ReplaceFile can fail after moving the old file aside.
                    if displaced.is_file():
                        try:
                            publish_new(displaced, path)
                        except OSError:
                            pass
                    raise
                with displaced.open("rb") as stream:
                    matches = stream.read(SAVE_SIZE + 1) == self.original
                if not matches:
                    # A concurrent rename is possible despite the write-sharing lock.
                    # Keep both snapshots for explicit recovery instead of racing a second replacement.
                    raise ValueError(f"A concurrent save was preserved as: {displaced}")
                verify_written(path, candidate)
                displaced.unlink()
            else:
                verify_source()
                os.replace(temporary, path)
                verify_written(path, candidate)
        return backup


@contextmanager
def read_without_writers(path: Path):
    """On Windows allow reads and renames while blocking writes to the verified file."""
    import ctypes
    from ctypes import wintypes
    import msvcrt

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    # GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL.
    handle = create(str(path), 0x80000000, 0x1 | 0x4, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except OSError:
        kernel.CloseHandle(ctypes.c_void_p(handle))
        raise
    with os.fdopen(fd, "rb") as stream:
        yield stream


def replace_with_backup(path: Path, temporary: Path, displaced: Path):
    import ctypes
    from ctypes import wintypes

    replace = ctypes.WinDLL("kernel32", use_last_error=True).ReplaceFileW
    replace.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                        wintypes.LPVOID, wintypes.LPVOID)
    replace.restype = wintypes.BOOL
    if not replace(str(path), str(temporary), str(displaced), 0, None, None):
        raise ctypes.WinError(ctypes.get_last_error())


@contextmanager
def staged_file(destination: Path, data: bytes):
    temporary = None
    try:
        with NamedTemporaryFile(dir=destination.parent, prefix=f".{destination.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        yield temporary
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def publish_new(temporary: Path, destination: Path):
    if os.name == "nt":
        os.rename(temporary, destination)
    else:
        os.link(temporary, destination)


def verify_written(path: Path, expected: bytes):
    if Save.open(path).original != expected:
        raise ValueError(f"The written file failed verification: {path}")
