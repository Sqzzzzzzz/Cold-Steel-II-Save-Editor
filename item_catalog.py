"""Read original XSEED PC Cold Steel II inventory tables."""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re
from struct import error as StructError, iter_unpack, unpack_from


EMPTY_ID = 9999
SEPITH_IDS = range(241, 250)
NOTEBOOK_IDS = range(250, 259)
ItemKey = int | str
STAT_NAMES = ("STR", "DEF", "ATS", "ADF", "ACC", "EVA", "SPD", "MOV", "HP", "EP")
ITEM_SCHEMA = frozenset((b"item", b"item_q", b"condition"))
DLC_ITEM_SCHEMA = ITEM_SCHEMA - {b"condition"}
MASTER_SCHEMA = frozenset((
    b"MasterQuartzStatus", b"MasterQuartzBase", b"MasterQuartzData", b"MasterQuartzMemo",
    b"MasterQuartzDummy", b"MasterQuartzDummy2",
))
INTERNAL = re.compile(
    r"\b(?:dev use|debug|do not submit|unused|dummy)\b|can't be obtained|don't show in list",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class CatalogItem:
    name: str
    description: str
    category: str
    limit: int
    icon_type: int
    element: int
    editable: bool = True
    stats: tuple[int, ...] = ()
    listed: bool = True
    rarity: int = 0
    dlc_pack: int | None = None


def _table_records(path: Path, schema: frozenset[bytes]):
    max_size = 2 * 1024 * 1024
    with path.open("rb") as stream:
        data = stream.read(max_size + 1)
    error = f"Invalid Cold Steel II {path.name}."
    try:
        if not 6 <= len(data) <= max_size:
            raise ValueError
        count, kinds = unpack_from("<HI", data)
        if kinds != len(schema):
            raise ValueError
        pos = 6
        definitions = {}
        for _ in range(kinds):
            end = data.index(0, pos)
            kind = data[pos:end]
            if kind not in schema or kind in definitions:
                raise ValueError
            definitions[kind] = unpack_from("<I", data, end + 1)[0]
            pos = end + 5
        if sum(definitions.values()) != count:
            raise ValueError
        seen = Counter()
        records = []
        for _ in range(count):
            end = data.index(0, pos)
            kind = data[pos:end]
            length = unpack_from("<H", data, end + 1)[0]
            start = end + 3
            pos = start + length
            if kind not in definitions or pos > len(data):
                raise ValueError
            records.append((kind, data[start:pos]))
            seen[kind] += 1
        if pos != len(data) or seen != Counter(definitions):
            raise ValueError
        return records
    except (StructError, ValueError) as exc:
        raise ValueError(error) from exc


def _localized_strings(data: bytes, start: int) -> tuple[str, str, bytes]:
    name, description, remainder = data[start:].split(b"\0", 2)
    return name.decode("utf-8").strip(), description.decode("utf-8").strip(), remainder


def item_category(item_id: int, icon_type: int) -> str:
    if icon_type == 0xC8:
        return "quartz"
    if icon_type == 0xC9:
        return "master"
    if 0x8C <= icon_type <= 0xA3 or 0xBD <= icon_type <= 0xC2 or icon_type in (0xC4, 0xC5, 0xC6):
        return "equipment"
    if item_id in (50, 51, 52) or icon_type in (0x80, 0xD2):
        return "materials"
    if icon_type in (0x83, 0xC3):
        return "books"
    if icon_type == 0x82 and item_id != 25:
        return "key"
    return "items"


def _read_items(path: Path, *, dlc: bool) -> dict[int, CatalogItem]:
    result = {}
    try:
        for kind, body in _table_records(path, DLC_ITEM_SCHEMA if dlc else ITEM_SCHEMA):
            if kind == b"condition":
                continue
            item_id, _ = unpack_from("<HH", body)
            metadata = body.index(0, 4) + 1
            name, description, tail = _localized_strings(body, metadata + 60)
            if len(tail) != (20 if kind == b"item_q" else 8) or item_id in result:
                raise ValueError
            description = re.sub(r"#\d+[A-Z]", "", description)
            icon_type, element = body[metadata:metadata + 2]
            limit = body[metadata + 55]
            pack_id = unpack_from("<H", body, metadata + 58)[0]
            if dlc and pack_id == 0xFFFF:
                raise ValueError
            category = item_category(item_id, icon_type)
            listed = (item_id < EMPTY_ID and 1 <= limit <= 99 and bool(name)
                      and not name.startswith(("◆", "□", "◇", "Test:"))
                      and description not in ("", "◆", "□", "Prologue")
                      and not INTERNAL.search(f"{name} {description}")
                      and item_id not in NOTEBOOK_IDS and item_id not in range(3240, 3249)
                      and pack_id not in (10, 164))  # These packs have no valid grant in the original DLC tables.
            # Quest items and journal unlocks are coupled to progression flags outside the inventory.
            editable = listed and category != "key" and icon_type not in (0x80, 0x83) and item_id not in range(358, 373)
            result[item_id] = CatalogItem(
                name, description, category, limit, icon_type, element, editable,
                unpack_from("<10h", body, metadata + 31), listed,
                body[metadata + 3] if kind == b"item_q" else 0,
                None if pack_id == 0xFFFF else pack_id,
            )
        if not result or (not dlc and not any(item.editable for item in result.values())):
            raise ValueError
    except (IndexError, StructError, ValueError) as exc:
        raise ValueError("Invalid Cold Steel II item table.") from exc
    return result


def read_catalog(path: Path) -> dict[int, CatalogItem]:
    items = _read_items(path, dlc=False)
    if not all(items.get(item_id) and items[item_id].category == category
               for item_id, category in ((0, "items"), (3200, "master"), (3300, "quartz"))):
        raise ValueError("Expected a complete Cold Steel II item table.")
    return items


def read_dlc_items(path: Path) -> dict[int, CatalogItem]:
    return _read_items(path, dlc=True)


def read_fishing_notebook(path: Path) -> dict[str, tuple[str, str]]:
    records = {}
    try:
        for _, body in _table_records(path, frozenset((b"QSFish",))):
            fish_id = unpack_from("<H", body)[0]
            if fish_id > 23:
                continue
            name_end = body.index(0, 3)
            description_start = name_end + 103
            description_end = body.index(0, description_start)
            key = f"fish:{fish_id}"
            if name_end == 3 or description_end == description_start or key in records:
                raise ValueError
            records[key] = (body[3:name_end].decode("utf-8"),
                            body[description_start:description_end].decode("utf-8"))
    except (StructError, ValueError) as exc:
        raise ValueError("Invalid Cold Steel II fishing notebook table.") from exc
    if len(records) != 24:
        raise ValueError("Invalid Cold Steel II fishing notebook table.")
    return records


def read_dlc(path: Path) -> dict[int, tuple[str, str, tuple[tuple[int, int], ...]]]:
    records = {}
    seen = set()
    try:
        for _, body in _table_records(path, frozenset((b"dlc",))):
            pack_id = unpack_from("<H", body)[0]
            name, description, grants = _localized_strings(body, 12)
            if len(grants) != 80:
                raise ValueError
            if pack_id in seen:
                raise ValueError
            seen.add(pack_id)
            items = tuple((item_id, quantity) for item_id, quantity in iter_unpack("<HH", grants)
                          if item_id < EMPTY_ID and quantity)
            if name and description and items and not INTERNAL.search(f"{name} {description}"):
                records[pack_id] = (name, description, items)
    except (StructError, ValueError) as exc:
        raise ValueError("Invalid Cold Steel II DLC table.") from exc
    return records


def read_dlc_packs(path: Path) -> dict[str, tuple[str, str]]:
    return {f"dlc:{pack_id}": (name, description)
            for pack_id, (name, description, _) in read_dlc(path).items()}


def read_dlc_grants(path: Path) -> dict[int, tuple[tuple[int, int], ...]]:
    return {pack_id: items for pack_id, (_, _, items) in read_dlc(path).items()}


def read_master_quartz_effects(path: Path) -> dict[int, tuple[str, ...]]:
    titles = {}
    masters = set()
    try:
        for kind, body in _table_records(path, MASTER_SCHEMA):
            if kind == b"MasterQuartzBase":
                item_id = unpack_from("<H", body)[0]
                if len(body) != 20 or item_id in masters:
                    raise ValueError
                masters.add(item_id)
            elif kind == b"MasterQuartzMemo":
                item_id, slot = unpack_from("<HH", body)
                if slot not in (0, 10, 20):
                    continue
                end = body.index(0, 4)
                title = body[4:end].decode("utf-8").strip()
                if end != len(body) - 1 or not title.startswith("★") or (item_id, slot) in titles:
                    raise ValueError
                titles[item_id, slot] = title.removeprefix("★").strip()
        return {item_id: tuple(titles[item_id, slot] for slot in (0, 10, 20)) for item_id in sorted(masters)}
    except (KeyError, StructError, ValueError) as exc:
        raise ValueError("Invalid Cold Steel II master quartz table.") from exc
