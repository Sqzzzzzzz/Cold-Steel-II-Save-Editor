"""Cache original Cold Steel II icons and import them from a local PC installation."""

import argparse
from functools import cache, cached_property
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPainterPath, QPixmap, QTransform

from item_catalog import CatalogItem


ASSETS = Path(__file__).resolve().parent / "assets"
SECONDARY_TILE = 0x100
FISH_TILE_START = 0x180
BLADE_CARD_TILE = 0x198
SHINING_POM_TILE = 0x199
SHINING_POM_BAIT_ID = 25
YELLOW_ORB_TILE = 0x91
FISH_COUNT = 24
SECTION_ICONS = {
    "all": 0x95, "equipment": 0x100, "quartz": 0x50, "master": 0x32,
    "materials": 0x13F, "books": 0x13D, "key": 0x13D, "dlc": 0x141, "items": 0x13B,
}
HUD_TILES = {
    "search": 0x134, "clock": 0x5F, "all": 0x95, "favorites": 0xC8, "recent": 0x5F,
    "quartz": 0x50, "quartz_normal": 0x50, "quartz_master": 0x32,
    "weapon": 0x100, "armor": 0x132, "shoes": 0x133, "accessory": 0x134,
    "consumable": 0x13B, "food": 0x67, "ingredient": 0x13F, "recipe": 0x13D,
    "book": 0x13D, "costume": 0x135, "face": 0x136, "hair": 0x136,
    "decoration": 0x13E, "dlc_pack": 0x141, "fish": 0x6D, "fishing_gear": 0x140,
    "fish_book": 0x13D, "quest": SECTION_ICONS["key"], "material": 0x13F,
    "card": BLADE_CARD_TILE, "orbment": YELLOW_ORB_TILE,
}
MENU_ICON_CENTERS = {
    "inventory": (27, 155), "catalog": (27, 410), "game": (27, 474),
    "open": (193, 207), "save": (193, 146), "remove": (193, 266),
}
ITEM_TILES = {
    0x81: 0x13B, 0x82: SECTION_ICONS["key"], 0x83: 0x13D, 0xBD: 0x131,
    0xBE: 0x132, 0xBF: 0x133, 0xC0: 0x134, 0xC1: 0x135, 0xC2: 0x136,
    0xC3: 0x13D, 0xC4: YELLOW_ORB_TILE, 0xC5: 0x13E, 0xC6: 0x80, 0xD2: 0x13F,
    0xD3: 0x67, 0xD4: 0x68, 0xD5: 0x69, 0xD6: 0x6A, 0xD7: 0x6B,
    0xDD: 0x140, 0xDE: 0x6E,
}


class GameArt:
    def __init__(self):
        self.items = QPixmap(str(ASSETS / "item-atlas.png"))
        self.secondary = QPixmap(str(ASSETS / "secondary-atlas.png"))
        self.masters = QPixmap(str(ASSETS / "master-atlas.png"))
        self.menu = QPixmap(str(ASSETS / "menu-atlas.png"))
        self.tiles = {}
        self.tile_icons = {}
        self.menu_icons = {}

    @cached_property
    def fish(self):
        return QPixmap(str(ASSETS / "fish-art.png"))

    @cached_property
    def blade(self):
        return QPixmap(str(ASSETS / "blade-ii.png"))

    @cached_property
    def shining_pom(self):
        return QPixmap(str(ASSETS / "shining-pom.png"))

    def fish_picture(self, fish_id: int) -> QPixmap:
        return self.tile(FISH_TILE_START + fish_id if 0 <= fish_id < FISH_COUNT else 0x6D)

    def reference_tile(self, key: str) -> int:
        kind, _, number = key.partition(":")
        if kind == "fish":
            fish_id = int(number)
            return FISH_TILE_START + fish_id if 0 <= fish_id < FISH_COUNT else 0x6D
        return SECTION_ICONS["dlc"]

    def tile(self, index: int, master: bool = False) -> QPixmap:
        if not master and index == BLADE_CARD_TILE:
            return self.blade
        if not master and index == SHINING_POM_TILE:
            return self.shining_pom
        key = (index, master)
        if key not in self.tiles:
            if master:
                atlas, cell, columns = self.masters, 64, 8
            elif FISH_TILE_START <= index < FISH_TILE_START + FISH_COUNT:
                index -= FISH_TILE_START
                atlas, cell, columns = self.fish, 96, 6
            elif SECONDARY_TILE <= index < FISH_TILE_START:
                index -= SECONDARY_TILE
                atlas, cell, columns = self.secondary, 32, 16
            else:
                atlas, cell, columns = self.items, 32, 16
            rect = QRect(index % columns * cell, index // columns * cell, cell, cell)
            self.tiles[key] = atlas.copy(rect) if atlas.rect().contains(rect) else QPixmap()
        return self.tiles[key]

    def tile_icon(self, index: int, master: bool = False) -> QIcon:
        key = (index, master)
        if key not in self.tile_icons:
            picture = self.tile(index, master)
            icon = QIcon(picture)
            if not picture.isNull():
                icon.addPixmap(picture, QIcon.Mode.Selected)
            self.tile_icons[key] = icon
        return self.tile_icons[key]

    def section_icon(self, category: str) -> QIcon:
        return self.tile_icon(SECTION_ICONS.get(category, SECTION_ICONS["all"]))

    def menu_icon(self, action: str) -> QIcon:
        if action in self.menu_icons:
            return self.menu_icons[action]
        if self.menu.isNull() or action not in MENU_ICON_CENTERS:
            return QIcon()
        x, y = MENU_ICON_CENTERS[action]
        source = self.menu.copy(x - 20, y - 20, 40, 40)
        circle = QPixmap(source.size())
        circle.fill(Qt.GlobalColor.transparent)
        painter = QPainter(circle)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addEllipse(QRectF(circle.rect()).adjusted(1, 1, -1, -1))
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, source)
        painter.end()
        icon = self.menu_icons[action] = QIcon(circle)
        return icon

    def item_icon(self, item_id: int, item: CatalogItem) -> QIcon:
        return self.tile_icon(*self._item_tile(item_id, item))

    def item_picture(self, item_id: int, item: CatalogItem) -> QPixmap:
        return self.tile(*self._item_tile(item_id, item))

    def _item_tile(self, item_id: int, item: CatalogItem) -> tuple[int, bool]:
        if item_id == SHINING_POM_BAIT_ID and not self.shining_pom.isNull():
            return SHINING_POM_TILE, False
        if item_id == 173 and not self.blade.isNull():
            return BLADE_CARD_TILE, False
        if item_id in (50, 51, 52):
            return SECTION_ICONS["materials"], False
        if item_id in (155, 156, 157) or 250 <= item_id <= 258:
            return SECTION_ICONS["books"], False
        if 241 <= item_id <= 248:
            return 0x20 + item_id - 241, False
        code = item.icon_type
        if code == 0xC9:
            if 3200 <= item_id <= 3230 and not self.masters.isNull():
                return item_id - 3200, True
            if 1 <= item.element <= 7:
                return 0x30 + item.element - 1, False
        if code == 0xC8:
            if 1 <= item.element <= 7 and 0 <= item.rarity <= 2:
                return (0x40, 0x50, 0x60)[item.rarity] + item.element - 1, False
            if 10 <= item.element <= 14:
                return 0x75 + item.element - 10, False
            return SECTION_ICONS["quartz"], False
        if 0x8C <= code <= 0xA3:
            return SECONDARY_TILE + code - 0x8C, False
        return ITEM_TILES.get(code, SECTION_ICONS.get(item.category, SECTION_ICONS["all"])), False


@cache
def shared_game_art() -> GameArt:
    return GameArt()


def _read_rgba_texture(path: Path, width: int, height: int) -> QImage:
    data = path.read_bytes()
    length = width * height * 4
    if path.name.endswith(".dds.phyre"):
        packed = sum(max(1, width >> i) * max(1, height >> i) * 4
                     for i in range(max(width, height).bit_length()))
        marker, image_format = b"PTexture2D\0ARGB8\0", QImage.Format.Format_ARGB32
    else:
        packed = length
        marker, image_format = b"PTexture2D\0RGBA8\0", QImage.Format.Format_RGBA8888
    start = len(data) - packed
    if not data.startswith(b"RYHP") or not 0 < start < 8192 or marker not in data[:start]:
        raise ValueError(f"Unrecognized Cold Steel II texture: {path.name}")
    texture = QImage(data[start:start + length], width, height, width * 4, image_format)
    return texture.flipped(Qt.Orientation.Vertical)


def import_art(game: Path, senpatcher: Path) -> None:
    japanese = game / "data/asset/D3D11"
    english = game / "data/asset/D3D11_us"
    with TemporaryDirectory() as directory:
        root = Path(directory)
        def extract(package: Path) -> Path:
            extracted = root / package.stem
            extracted.mkdir()
            subprocess.run(
                [str(senpatcher.resolve()), "PKG.Extract", "-o", str(extracted), str(package)],
                check=True,
            )
            return extracted

        ASSETS.mkdir(exist_ok=True)
        system = extract(english / "I_SYSTEM.pkg")
        for original, output, width, height in (
            ("icons.dds.phyre", "item-atlas.png", 512, 512),
            ("icons2.dds.phyre", "secondary-atlas.png", 512, 256),
            ("orbment_mq.dds.phyre", "master-atlas.png", 512, 256),
            ("campmenu3.png.phyre", "menu-atlas.png", 1024, 512),
        ):
            picture = _read_rgba_texture(system / original, width, height)
            if not picture.save(str(ASSETS / output)):
                raise OSError(f"Could not write {output}.")
            if output == "item-atlas.png":
                cursor = picture.copy(457, 357, 19, 21)
                for direction, angle in (("up", -90), ("down", 90)):
                    filename = ASSETS / f"arrow-{direction}.png"
                    if not cursor.transformed(QTransform().rotate(angle)).save(str(filename)):
                        raise OSError(f"Could not write {filename.name}.")

        fish_dir = extract(english / "I_NOTE_FISH.pkg")
        fish = _read_rgba_texture(fish_dir / "note_fis.dds.phyre", 1024, 1024)
        atlas = QImage(576, 384, QImage.Format.Format_RGBA8888)
        atlas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(atlas)
        for i in range(FISH_COUNT):
            x, y = (8, 2 + i * 78) if i < 13 else (516, 2 + (i - 13) * 78)
            painter.drawImage(QPoint(i % 6 * 96 + 1, i // 6 * 96 + 10), fish, QRect(x, y, 93, 76))
        painter.end()
        if not atlas.save(str(ASSETS / "fish-art.png")):
            raise OSError("Could not write fish-art.png.")

        for package, original, output, width, height, crop in (
            ("I_MG002", "min002cd.png.phyre", "blade-ii.png", 512, 512, (4, 3, 120, 157)),
            ("I_NOTE_MON006", "note_mon006.dds.phyre", "shining-pom.png", 256, 256, (26, 22, 202, 209)),
            ("I_NOTE_ICONS", "note_ic_main.dds.phyre", "thors.png", 512, 512, (60, 15, 408, 484)),
        ):
            extracted = extract(japanese / f"{package}.pkg")
            picture = _read_rgba_texture(extracted / original, width, height).copy(*crop)
            if not picture.save(str(ASSETS / output)):
                raise OSError(f"Could not write {output}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", type=Path, help="Cold Steel II installation directory")
    parser.add_argument("senpatcher", type=Path, help="Path to the local SenPatcher.exe")
    args = parser.parse_args()
    import_art(args.game, args.senpatcher)
