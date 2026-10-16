"""Small original stroke pictograms, rendered at the desktop's scale without dependencies."""

import base64
import math
import struct
import tkinter as tk
import zlib

from field_notes_studio.presentation.theme import INK


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
}


def _distance(x, y, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    fraction = max(0, min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - a[0] - fraction * dx, y - a[1] - fraction * dy)


def _png(name, color, size):
    segments = [(a, b) for path in GLYPHS[name] for a, b in zip(path, path[1:], strict=False)]
    rgb = bytes.fromhex(color.removeprefix("#"))
    rows = bytearray()
    scale = size / 18
    for y in range(size):
        rows.append(0)  # PNG scanline with no filter.
        for x in range(size):
            distance = min(
                _distance((x + 0.5) / scale - 1, (y + 0.5) / scale - 1, a, b) for a, b in segments
            )
            alpha = round(255 * max(0, min(1, (0.7 - distance) * scale + 0.5)))
            rows.extend(rgb + bytes([alpha]))

    def chunk(kind, data):
        return (
            struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!2I5B", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def icon(widget, name, color=INK):
    root = widget.winfo_toplevel()
    if not hasattr(root, "studio_icons"):
        root.studio_icons = {}
    size = max(16, round(18 * float(root.tk.call("tk", "scaling")) / (96 / 72)))
    key = name, color, size
    if key not in root.studio_icons:
        root.studio_icons[key] = tk.PhotoImage(
            master=root, data=base64.b64encode(_png(*key)), format="png"
        )
    return root.studio_icons[key]
