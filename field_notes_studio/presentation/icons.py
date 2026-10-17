"""Small original stroke pictograms, rendered at the desktop's scale without dependencies.

Colours are palette roles ("INK", "MUTED", ...) or literal hex values. Role-coloured
images are redrawn in place when the appearance changes, so every widget showing
one follows Light and Night without being rebuilt.
"""

import base64
import math
import struct
import tkinter as tk
import zlib
from functools import cache

from field_notes_studio.presentation import theme


def arc(x, y, radius, start=0, end=math.tau):
    return tuple(
        (
            x + radius * math.cos(start + (end - start) * i / 24),
            y + radius * math.sin(start + (end - start) * i / 24),
        )
        for i in range(25)
    )


GLYPHS = {
    "produce": (
        ((2, 6), (2, 10)),
        ((5, 3), (5, 13)),
        ((8, 1), (8, 15)),
        ((11, 4), (11, 12)),
        ((14, 6), (14, 10)),
    ),
    "audio": (
        arc(8, 8, 5, math.pi, math.tau),
        ((3, 8), (3, 13), (5, 13), (5, 9)),
        ((13, 8), (13, 13), (11, 13), (11, 9)),
    ),
    "pending": (arc(8, 8, 4),),
    "batch": (
        ((5, 1), (14, 1), (14, 11)),
        ((3, 3), (12, 3), (12, 13)),
        ((1, 5), (10, 5), (10, 15), (1, 15), (1, 5)),
        ((3, 10), (5, 12), (8, 8)),
    ),
    "health": (
        ((1, 8), (4, 8), (6, 3), (9, 13), (11, 8), (15, 8)),
        ((2, 2), (2, 1), (14, 1), (14, 2)),
        ((2, 14), (2, 15), (14, 15), (14, 14)),
    ),
    "video": (((2, 4), (11, 4), (11, 12), (2, 12), (2, 4)), ((11, 6), (15, 4), (15, 12), (11, 10))),
    "captions": (
        ((1, 3), (15, 3), (15, 13), (1, 13), (1, 3)),
        ((4, 7), (7, 7)),
        ((10, 7), (12, 7)),
        ((4, 10), (12, 10)),
    ),
    "transcript": (((4, 2), (13, 2)), ((4, 6), (13, 6)), ((4, 10), (13, 10)), ((4, 14), (10, 14))),
    "review": (arc(8, 8, 7), ((4, 8), (7, 11), (12, 5))),
    "check": (((3, 8), (6, 11), (13, 4)),),
    "package": (
        ((2, 4), (8, 1), (14, 4), (8, 7), (2, 4), (2, 12), (8, 15), (14, 12), (14, 4)),
        ((8, 7), (8, 15)),
    ),
    "external": (
        ((7, 3), (2, 3), (2, 14), (13, 14), (13, 9)),
        ((9, 2), (14, 2), (14, 7)),
        ((7, 9), (14, 2)),
    ),
    "copy": (((5, 5), (14, 5), (14, 14), (5, 14), (5, 5)), ((10, 2), (2, 2), (2, 10))),
    "save": (
        ((2, 2), (12, 2), (14, 4), (14, 14), (2, 14), (2, 2)),
        ((5, 2), (5, 6), (11, 6), (11, 2)),
        ((5, 14), (5, 10), (11, 10), (11, 14)),
    ),
    "refresh": (arc(8, 8, 6, 0.2, 5.3), ((10, 1), (13, 3), (10, 5))),
    "folder": (((1, 4), (6, 4), (8, 6), (15, 6), (15, 13), (1, 13), (1, 4)),),
    "stop": (((3, 3), (13, 3), (13, 13), (3, 13), (3, 3)),),
    "history": (arc(8, 8, 7), ((8, 4), (8, 8), (11, 10))),
    "search": (arc(7, 7, 5), ((11, 11), (15, 15))),
    "queue": (
        ((2, 3), (14, 3)),
        ((2, 8), (14, 8)),
        ((2, 13), (9, 13)),
        ((11, 11), (14, 13), (11, 15)),
    ),
    "menu": (((2, 4), (14, 4)), ((2, 8), (14, 8)), ((2, 12), (14, 12))),
    "night": (arc(8, 8, 6, 1.1, 5.2), ((10.9, 2.6), (8.6, 5.2), (8.6, 10.8), (10.9, 13.4))),
    "more": (((3, 8), (3.5, 8)), ((8, 8), (8.5, 8)), ((13, 8), (13.5, 8))),
    "worker": (
        arc(8, 8, 3),
        ((8, 1), (8, 4)),
        ((8, 12), (8, 15)),
        ((1, 8), (4, 8)),
        ((12, 8), (15, 8)),
    ),
}


def _distance(x, y, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    fraction = max(0, min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - a[0] - fraction * dx, y - a[1] - fraction * dy)


@cache
def _mask(name, size):
    """Coverage of one glyph at one pixel size; colour is applied separately."""
    segments = [(a, b) for path in GLYPHS[name] for a, b in zip(path, path[1:], strict=False)]
    scale = size / 18
    alpha = bytearray()
    for y in range(size):
        for x in range(size):
            distance = min(
                _distance((x + 0.5) / scale - 1, (y + 0.5) / scale - 1, a, b) for a, b in segments
            )
            alpha.append(round(255 * max(0, min(1, (0.7 - distance) * scale + 0.5))))
    return bytes(alpha)


@cache
def _box(state, size):
    """RGBA-role coverage for a checkbox: (edge, fill, tick) alpha planes."""
    inset, radius = size * 0.1, size * 0.16
    width = max(1.0, size / 14)
    edge, fill, tick = bytearray(), bytearray(), bytearray()
    ticked = state.startswith("on")
    stroke = ((0.25, 0.52), (0.43, 0.7), (0.76, 0.32)) if ticked else ()
    lines = [
        ((a[0] * size, a[1] * size), (b[0] * size, b[1] * size))
        for a, b in zip(stroke, stroke[1:], strict=False)
    ]
    for y in range(size):
        for x in range(size):
            px, py = x + 0.5, y + 0.5
            # Signed distance to a rounded square.
            qx = abs(px - size / 2) - (size / 2 - inset - radius)
            qy = abs(py - size / 2) - (size / 2 - inset - radius)
            outside = math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - radius
            inside = max(0.0, min(1.0, 0.5 - outside))
            ring = max(0.0, min(1.0, 0.5 - abs(outside + width / 2) + width / 2))
            edge.append(round(255 * ring))
            fill.append(round(255 * inside))
            if lines:
                distance = min(_distance(px, py, a, b) for a, b in lines)
                tick.append(round(255 * max(0, min(1, size / 11 - distance + 0.5))))
            else:
                tick.append(0)
    return bytes(edge), bytes(fill), bytes(tick)


def _encode(size, pixels):
    rows = bytearray()
    for y in range(size):
        rows.append(0)  # PNG scanline with no filter.
        rows.extend(pixels[y * size * 4 : (y + 1) * size * 4])

    def chunk(kind, data):
        return (
            struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!2I5B", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows)))
        + chunk(b"IEND", b"")
    )


def _png(name, color, size):
    rgb = bytes.fromhex(theme.color(color).removeprefix("#"))
    pixels = bytearray()
    for alpha in _mask(name, size):
        pixels.extend(rgb + bytes([alpha]))
    return _encode(size, pixels)


INDICATOR = {
    # state: (edge, fill, tick) palette roles
    "off": ("EDGE", "SURFACE", None),
    "off-active": ("BRASS", "SURFACE", None),
    "off-disabled": ("LINE", "PAPER", None),
    "on": ("BRASS", "BRASS", "ACCENT_FG"),
    "on-disabled": ("LINE", "LINE", "DISABLED"),
}


def _indicator_png(state, size):
    edge, fill, tick = _box(state, size)
    roles = INDICATOR[state]
    colors = [
        bytes.fromhex(theme.color(role).removeprefix("#")) if role else b"\0\0\0" for role in roles
    ]
    pixels = bytearray()
    for index in range(size * size):
        # Composite: fill, then edge ring, then tick, each over the previous layer.
        red = green = blue = 0.0
        alpha = 0.0
        for layer, plane in ((colors[1], fill), (colors[0], edge), (colors[2], tick)):
            cover = plane[index] / 255
            if not cover:
                continue
            red = layer[0] * cover + red * (1 - cover)
            green = layer[1] * cover + green * (1 - cover)
            blue = layer[2] * cover + blue * (1 - cover)
            alpha = cover + alpha * (1 - cover)
        if alpha:
            red, green, blue = red / alpha, green / alpha, blue / alpha
        pixels.extend(bytes((round(red), round(green), round(blue), round(alpha * 255))))
    return _encode(size, pixels)


def _cache(widget):
    root = widget.winfo_toplevel()
    root = root.nametowidget(".")
    if not hasattr(root, "studio_icons"):
        root.studio_icons = {}
    return root


def _size(root, base):
    return max(base - 2, round(base * float(root.tk.call("tk", "scaling")) / (96 / 72)))


def icon(widget, name, color="INK"):
    root = _cache(widget)
    size = _size(root, 18)
    key = "glyph", name, color, size
    if key not in root.studio_icons:
        root.studio_icons[key] = tk.PhotoImage(
            master=root, data=base64.b64encode(_png(name, color, size)), format="png"
        )
    return root.studio_icons[key]


def indicator(widget, state):
    """A checkbox indicator image that scales with the desktop and follows the palette."""
    root = _cache(widget)
    size = _size(root, 16)
    key = "indicator", state, "", size
    if key not in root.studio_icons:
        root.studio_icons[key] = tk.PhotoImage(
            master=root, data=base64.b64encode(_indicator_png(state, size)), format="png"
        )
    return root.studio_icons[key]


def retheme(widget):
    """Redraw role-coloured images in place for the current palette."""
    root = _cache(widget)
    for (kind, name, color, size), image in root.studio_icons.items():
        if kind == "indicator":
            data = _indicator_png(name, size)
        elif not color.startswith("#"):
            data = _png(name, color, size)
        else:
            continue
        image.configure(data=base64.b64encode(data), format="png")
