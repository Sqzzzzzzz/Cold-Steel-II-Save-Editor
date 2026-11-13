from pathlib import Path
from struct import pack, pack_into
from tempfile import TemporaryDirectory
from unittest import TestCase

from item_catalog import (
    read_catalog, read_dlc_grants, read_dlc_items, read_dlc_packs, read_fishing_notebook,
    read_master_quartz_effects,
)


def table(definitions, rows):
    headers = b"".join(kind + b"\0" + pack("<I", sum(key == kind for key, _ in rows)) for kind in definitions)
    records = b"".join(kind + b"\0" + pack("<H", len(body)) + body for kind, body in rows)
    return pack("<HI", len(rows), len(definitions)) + headers + records


def item(item_id, icon_type, *, element=0, rarity=0, limit=99, stat=0, pack_id=0xFFFF, name=b"Item"):
    metadata = bytearray(60)
    metadata[:4] = bytes((icon_type, element, 0, rarity))
    metadata[55] = limit
    pack_into("<h", metadata, 31, stat)
    pack_into("<H", metadata, 58, pack_id)
    tail = bytes(20 if icon_type == 0xC8 else 8)
    return pack("<HH", item_id, 0xFFFD) + b"SLZ\0" + metadata + name + b"\0Description\0" + tail


class CatalogTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write(self, name, data):
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_native_base_catalog_and_signed_stats(self):
        data = table((b"item", b"item_q", b"condition"), [
            (b"item", item(0, 0x81)),
            (b"item", item(3200, 0xC9, element=3, limit=1)),
            (b"item", item(3244, 0xC9, element=3, limit=1)),
            (b"item", item(250, 0x82, limit=1)),
            (b"item", item(101, 0x82, limit=1)),
            (b"item", item(1197, 0xC2, name=b"Test: Glasses")),
            (b"item_q", item(3300, 0xC8, element=1, rarity=2, stat=-150)),
            (b"condition", b"Not an inventory row"),
        ])
        path = self.write("t_item.tbl", data)
        result = read_catalog(path)
        self.assertEqual(len(result), 7)
        self.assertEqual(result[3200].category, "master")
        self.assertEqual(result[3300].category, "quartz")
        self.assertEqual((result[3300].rarity, result[3300].stats[0]), (2, -150))
        self.assertTrue(result[101].listed)
        self.assertFalse(result[101].editable)
        self.assertTrue(all(not result[i].listed and not result[i].editable for i in (250, 1197, 3244)))
        for bad in (data[:-1], data + b"\0", b"\x01\0item\0" + item(0, 0x81)):
            with self.subTest(size=len(bad)), self.assertRaisesRegex(ValueError, "Cold Steel II"):
                read_catalog(self.write("t_item.tbl", bad))

    def test_dlc_items_and_grants(self):
        path = self.write("t_item.tbl", table((b"item", b"item_q"), [
            (b"item", item(3821, 0xC1, pack_id=101)),
            (b"item", item(3931, 0xC2, pack_id=164)),
        ]))
        items = read_dlc_items(path)
        self.assertEqual((items[3821].category, items[3821].dlc_pack), ("equipment", 101))
        self.assertFalse(items[3931].listed)
        with self.assertRaises(ValueError):
            read_catalog(path)

        def pack_record(pack_id, description):
            return pack("<H", pack_id) + bytes(10) + b"Pack\0" + description + b"\0" + (
                pack("<HHHH", 3821, 1, 50, 5) + pack("<HH", 9999, 0) * 18
            )

        path = self.write("t_dlc.tbl", table((b"dlc",), [
            (b"dlc", pack_record(101, b"Costume set")),
            (b"dlc", pack_record(164, b"DO NOT SUBMIT")),
        ]))
        self.assertEqual(read_dlc_packs(path), {"dlc:101": ("Pack", "Costume set")})
        self.assertEqual(read_dlc_grants(path), {101: ((3821, 1), (50, 5))})

    def test_master_quartz_ability_titles(self):
        schema = (b"MasterQuartzStatus", b"MasterQuartzBase", b"MasterQuartzData", b"MasterQuartzMemo",
                  b"MasterQuartzDummy", b"MasterQuartzDummy2")
        rows = [(b"MasterQuartzBase", pack("<H", 3200) + bytes(18))]
        for slot, effect in ((0, "★ First\r\n"), (1, "Damage: %g"), (10, "★Second"), (20, "★Third")):
            rows.append((b"MasterQuartzMemo", pack("<HH", 3200, slot) + effect.encode("utf-8") + b"\0"))
        path = self.write("t_mstqrt.tbl", table(schema, rows))
        self.assertEqual(read_master_quartz_effects(path), {3200: ("First", "Second", "Third")})
        path = self.write("t_mstqrt.tbl", table(schema, rows[:-1]))
        with self.assertRaisesRegex(ValueError, "master quartz"):
            read_master_quartz_effects(path)

    def test_fishing_journal_does_not_turn_reference_rows_into_inventory_items(self):
        rows = [(b"QSFish", pack("<HB", fish_id, 1) + b"Fish\0" + bytes(102) + b"Description\0")
                for fish_id in range(27)]
        rows.append((b"QSFish", pack("<H", 48) + b"\x01Record\0"))
        path = self.write("t_notefish.tbl", table((b"QSFish",), rows))
        self.assertEqual(read_fishing_notebook(path),
                         {f"fish:{fish_id}": ("Fish", "Description") for fish_id in range(24)})
