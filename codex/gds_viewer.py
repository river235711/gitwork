#!/usr/bin/env python3
"""A small, dependency-free GDSII viewer.

Run:
    python3 gds_viewer.py [layout.gds]

The viewer reads GDSII directly and uses Tkinter for drawing. It supports
boundaries, boxes, paths, text, SREFs, and AREFs, including nested transforms.
"""

from __future__ import annotations

import colorsys
import gzip
import math
import os
import struct
import sys
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import filedialog, messagebox, ttk
from typing import Iterator


@dataclass
class Element:
    kind: str
    layer: int = 0
    dtype: int = 0
    points: list[tuple[int, int]] = field(default_factory=list)
    width: int = 0
    path_type: int = 0
    begin_ext: int = 0
    end_ext: int = 0
    text: str = ""
    target: str = ""
    angle: float = 0.0
    magnification: float = 1.0
    reflect_x: bool = False
    columns: int = 1
    rows: int = 1


@dataclass
class Cell:
    name: str
    elements: list[Element] = field(default_factory=list)


@dataclass
class Layout:
    name: str
    cells: dict[str, Cell]
    user_units_per_dbu: float
    meters_per_dbu: float


def _real8(data: bytes) -> float:
    if len(data) != 8:
        raise ValueError("Invalid GDS real8 value")
    sign = -1.0 if data[0] & 0x80 else 1.0
    exponent = data[0] & 0x7F
    fraction = int.from_bytes(data[1:], "big") / float(1 << 56)
    return sign * fraction * (16.0 ** (exponent - 64))


def _records(stream) -> Iterator[tuple[int, int, bytes]]:
    while True:
        record_start = stream.tell()
        header = stream.read(4)
        if not header:
            return
        if len(header) != 4:
            raise ValueError(f"Truncated GDS record header at byte {record_start}")
        if header == b"\0\0\0\0":
            # Some stream writers pad the file with zero bytes after ENDLIB.
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    return
                if any(chunk):
                    raise ValueError(
                        f"Unexpected data after zero padding at byte {record_start}"
                    )
        length, record_type, data_type = struct.unpack(">HBB", header)
        if length < 4:
            raise ValueError(
                f"Invalid GDS record length {length} at byte {record_start} "
                f"(record type 0x{record_type:02x})"
            )
        payload = stream.read(length - 4)
        if len(payload) != length - 4:
            raise ValueError(
                f"Truncated GDS record at byte {record_start}: "
                f"expected {length - 4} payload bytes, got {len(payload)}"
            )
        yield record_type, data_type, payload
        if record_type == 0x04:  # ENDLIB; ignore optional trailing block padding
            return


def _int2(payload: bytes) -> int:
    return struct.unpack(">h", payload[:2])[0] if len(payload) >= 2 else 0


def _int4(payload: bytes) -> int:
    return struct.unpack(">i", payload[:4])[0] if len(payload) >= 4 else 0


def _xy(payload: bytes) -> list[tuple[int, int]]:
    if len(payload) % 8:
        raise ValueError("Invalid XY record length")
    values = struct.unpack(f">{len(payload) // 4}i", payload) if payload else ()
    return list(zip(values[::2], values[1::2]))


def read_gds(path: str) -> Layout:
    opener = gzip.open if path.lower().endswith(".gz") else open
    cells: dict[str, Cell] = {}
    current_cell: Cell | None = None
    element: Element | None = None
    library_name = os.path.basename(path)
    units_user = 1.0
    units_meters = 1e-9

    element_types = {
        0x08: "boundary",
        0x09: "path",
        0x0A: "sref",
        0x0B: "aref",
        0x0C: "text",
        0x15: "node",
        0x2D: "box",
    }

    with opener(path, "rb") as stream:
        for record_type, _data_type, payload in _records(stream):
            if record_type == 0x02:  # LIBNAME
                library_name = payload.rstrip(b"\0").decode("ascii", "replace")
            elif record_type == 0x03 and len(payload) >= 16:  # UNITS
                units_user = _real8(payload[:8]) or 1.0
                units_meters = _real8(payload[8:16]) or 1e-9
            elif record_type == 0x05:  # BGNSTR
                current_cell = None
                element = None
            elif record_type == 0x06 and current_cell is None:  # STRNAME
                name = payload.rstrip(b"\0").decode("ascii", "replace") or "<unnamed>"
                current_cell = cells.setdefault(name, Cell(name))
            elif record_type in element_types and current_cell is not None:
                element = Element(element_types[record_type])
            elif record_type == 0x11 and current_cell is not None:  # ENDEL
                if element is not None:
                    current_cell.elements.append(element)
                element = None
            elif record_type == 0x07:  # ENDSTR
                current_cell = None
                element = None
            elif element is not None:
                if record_type == 0x0D:  # LAYER
                    element.layer = _int2(payload)
                elif record_type in (0x0E, 0x16, 0x2A, 0x2E):  # DATATYPE/TEXTTYPE/NODTYPE/BOXTYPE
                    element.dtype = _int2(payload)
                elif record_type == 0x0F:  # WIDTH
                    element.width = _int4(payload)
                elif record_type == 0x10:  # XY
                    element.points = _xy(payload)
                elif record_type == 0x12:  # SNAME
                    element.target = payload.rstrip(b"\0").decode("ascii", "replace")
                elif record_type == 0x13 and len(payload) >= 4:  # COLROW
                    element.columns, element.rows = struct.unpack(">hh", payload[:4])
                    element.columns = max(1, element.columns)
                    element.rows = max(1, element.rows)
                elif record_type == 0x1A and len(payload) >= 2:  # STRANS
                    element.reflect_x = bool(struct.unpack(">H", payload[:2])[0] & 0x8000)
                elif record_type == 0x1B and len(payload) >= 8:  # MAG
                    element.magnification = _real8(payload[:8]) or 1.0
                elif record_type == 0x1C and len(payload) >= 8:  # ANGLE
                    element.angle = _real8(payload[:8])
                elif record_type == 0x21:  # PATHTYPE
                    element.path_type = _int2(payload)
                elif record_type == 0x30:  # BGNEXTN
                    element.begin_ext = _int4(payload)
                elif record_type == 0x31:  # ENDEXTN
                    element.end_ext = _int4(payload)
                elif record_type == 0x19:  # STRING
                    element.text = payload.rstrip(b"\0").decode("ascii", "replace")

    if not cells:
        raise ValueError("No structures were found in this GDS file")
    return Layout(library_name, cells, units_user, units_meters)


# Affine transform: x'=a*x+b*y+tx, y'=c*x+d*y+ty
Transform = tuple[float, float, float, float, float, float]
IDENTITY: Transform = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
def _compose(parent: Transform, local: Transform) -> Transform:
    a, b, c, d, tx, ty = parent
    e, f, g, h, ux, uy = local
    return (
        a * e + b * g,
        a * f + b * h,
        c * e + d * g,
        c * f + d * h,
        a * ux + b * uy + tx,
        c * ux + d * uy + ty,
    )


def _apply(transform: Transform, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, tx, ty = transform
    return a * x + b * y + tx, c * x + d * y + ty


def _reference_transform(element: Element, x: float, y: float) -> Transform:
    angle = math.radians(element.angle)
    mag = element.magnification
    cosine, sine = math.cos(angle) * mag, math.sin(angle) * mag
    if element.reflect_x:
        return cosine, sine, sine, -cosine, x, y
    return cosine, -sine, sine, cosine, x, y


class GDSViewer:
    def __init__(self, root: tk.Tk, initial_file: str | None = None):
        self.root = root
        self.root.title("GDS Viewer")
        self.root.geometry("1450x900")
        self.root.minsize(1100, 650)

        self.layout: Layout | None = None
        self.file_path = ""
        self.cell_name = ""
        self.descend_hierarchy = False
        self.visible_layers: set[tuple[int, int]] = set()
        self.bounds: tuple[float, float, float, float] | None = None
        self.world_center = (0.0, 0.0)
        self.scale = 1.0
        self.shape_count = 0
        self.truncated = False
        self._shapes: list[tuple] = []
        self._pan_start: tuple[int, int, float, float] | None = None
        self._pan_last: tuple[int, int] | None = None
        self._zoom_box_start: tuple[int, int] | None = None
        self._zoom_box_item: int | None = None
        self._resize_after: str | None = None
        self._zoom_after: str | None = None
        self._layer_keys: list[tuple[int, int]] = []
        self._layer_colors_cache: dict[tuple[int, int], str] = {}
        self._layer_images: dict[tuple[int, int], tk.PhotoImage] = {}
        self._layer_filter = tk.StringVar()
        self.layer_summary: ttk.Label | None = None
        self._cell_iid_to_name: dict[str, str] = {}
        self._cell_name_to_iids: dict[str, list[str]] = {}
        self._cell_tree_ancestry: dict[str, tuple[str, ...]] = {}
        self._cell_tree_serial = 0

        self._build_ui()
        self.root.bind("<Control-o>", lambda _event: self.open_dialog())
        self.root.bind("<KeyPress-f>", self._fit_key)
        self.root.bind("<KeyPress-F>", self._fit_key)
        self.root.bind("<plus>", lambda _event: self._zoom_center(1.15))
        self.root.bind("<minus>", lambda _event: self._zoom_center(1 / 1.15))

        if initial_file:
            self.root.after(100, lambda: self.load_file(initial_file))

    def _build_ui(self) -> None:
        menubar = tk.Menu(self.root)
        menu_commands = {
            "File": [("Open GDS…", self.open_dialog), ("Fit View", self.fit_view), ("Exit", self.root.destroy)],
            "View": [
                ("Fit", self.fit_view),
                ("Current Cell Only (Ctrl+F)", lambda: self._set_hierarchy_mode(False)),
                ("Descend Hierarchy (Shift+F)", lambda: self._set_hierarchy_mode(True)),
                ("Zoom In", lambda: self._zoom_center(1.15)),
                ("Zoom Out", lambda: self._zoom_center(1 / 1.15)),
            ],
            "Create": [],
            "Edit": [],
            "Hierarchy": [],
            "Query": [],
            "Tools": [],
            "Verify": [],
            "Options": [],
            "Help": [],
            "Ext": [],
        }
        for title, commands in menu_commands.items():
            menu = tk.Menu(menubar, tearoff=False)
            for label, command in commands:
                menu.add_command(label=label, command=command)
            if not commands:
                menu.add_command(label="Not available in this viewer yet", state="disabled")
            menubar.add_cascade(label=title, menu=menu)
        self.root.configure(menu=menubar)

        toolbar = ttk.Frame(self.root, padding=(5, 3))
        toolbar.pack(side=tk.TOP, fill=tk.X)
        for glyph, hint, command in (
            ("Open", "Open GDS", self.open_dialog),
            ("Fit", "Fit layout", self.fit_view),
            ("□", "Select mode", None),
            ("＋", "Zoom in", lambda: self._zoom_center(1.15)),
            ("－", "Zoom out", lambda: self._zoom_center(1 / 1.15)),
            ("↔", "Pan with left mouse button", self._activate_pan),
            ("⌖", "Center view", self.fit_view),
        ):
            button = ttk.Button(toolbar, text=glyph, width=4, command=command or (lambda: None))
            if command is None:
                button.state(["disabled"])
            button.pack(side=tk.LEFT, padx=(0, 2))
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        self.file_label = ttk.Label(toolbar, text="No GDS loaded", width=42, anchor=tk.W)
        self.file_label.pack(side=tk.LEFT, padx=3)

        controls = ttk.Frame(self.root, padding=(6, 3))
        controls.pack(side=tk.TOP, fill=tk.X)
        self.layout_button = tk.Button(
            controls, text="0:Layouts(0)", bg="#92ff73", relief=tk.RAISED,
            padx=5, pady=1, command=self.open_dialog,
        )
        self.layout_button.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(controls, text="Level:").pack(side=tk.LEFT)
        self.level_var = tk.IntVar(value=0)
        ttk.Spinbox(controls, from_=0, to=64, width=4, textvariable=self.level_var).pack(side=tk.LEFT, padx=(3, 8))
        ttk.Label(controls, text="Detail:").pack(side=tk.LEFT)
        self.detail_combo = ttk.Combobox(controls, values=("Normal", "Fine", "Coarse"), state="readonly", width=8)
        self.detail_combo.set("Normal")
        self.detail_combo.pack(side=tk.LEFT, padx=(3, 8))
        ttk.Label(controls, text="Cell:").pack(side=tk.LEFT)
        self.cell_var = tk.StringVar()
        self.cell_combo = ttk.Combobox(controls, textvariable=self.cell_var, state="readonly", width=28)
        self.cell_combo.pack(side=tk.LEFT, padx=5)
        self.cell_combo.bind("<<ComboboxSelected>>", self._choose_cell)

        body = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)
        side = ttk.Frame(body, padding=(5, 4), width=292)
        body.add(side, weight=0)
        self._build_layer_panel(side)

        canvas_shell = tk.Frame(body, background="#343434", padx=8, pady=6)
        body.add(canvas_shell, weight=1)
        self.canvas = tk.Canvas(canvas_shell, background="#050505", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        footer = ttk.Frame(self.root, padding=(5, 2))
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        self.status = tk.StringVar(value="Select  |  Drag to pan  |  Wheel to zoom")
        ttk.Label(
            footer,
            text="F: Fit  |  Ctrl+F: Current Cell  |  Shift+F: Descend  |  Right drag: Zoom box",
            anchor=tk.W,
        ).pack(side=tk.LEFT, padx=(3, 18))
        ttk.Label(footer, textvariable=self.status, anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(footer, text="Snap 0.001 um", anchor=tk.E).pack(side=tk.RIGHT, padx=4)

        self.canvas.bind("<ButtonPress-1>", self._pan_begin)
        self.canvas.bind("<B1-Motion>", self._pan_move)
        self.canvas.bind("<ButtonRelease-1>", self._pan_end)
        self.canvas.bind("<ButtonPress-3>", self._zoom_box_begin)
        self.canvas.bind("<B3-Motion>", self._zoom_box_move)
        self.canvas.bind("<ButtonRelease-3>", self._zoom_box_end)
        self.canvas.bind("<MouseWheel>", self._wheel_zoom)
        self.canvas.bind("<Button-4>", lambda event: self._zoom_at(event.x, event.y, 1.15))
        self.canvas.bind("<Button-5>", lambda event: self._zoom_at(event.x, event.y, 1 / 1.15))
        self.canvas.bind("<Motion>", self._show_coordinates)
        self.canvas.bind("<Configure>", self._on_resize)

    def _build_layer_panel(self, side: ttk.Frame) -> None:
        ttk.Label(side, text="Layer", anchor=tk.W).pack(fill=tk.X, pady=(0, 2))
        self.layer_summary = ttk.Label(side, text="—    [drawing]    @0", anchor=tk.W)
        self.layer_summary.pack(fill=tk.X, pady=(0, 3))
        actions = ttk.Frame(side)
        actions.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(actions, text="AV", width=4, command=self._show_all_layers).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(actions, text="NV", width=4, command=self._hide_all_layers).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(actions, text="AS", width=4, state="disabled").pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(actions, text="NS", width=4, state="disabled").pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(actions, text="AT", width=4, state="disabled").pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(actions, text="NT", width=4, state="disabled").pack(side=tk.LEFT)
        flags = ttk.Frame(side)
        flags.pack(fill=tk.X, pady=(0, 3))
        ttk.Checkbutton(flags, text="Num", state="disabled").pack(side=tk.LEFT)
        ttk.Checkbutton(flags, text="Inst", state="disabled").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Checkbutton(flags, text="Top label only", state="disabled").pack(side=tk.LEFT, padx=(8, 0))

        tabs = ttk.Notebook(side)
        tabs.pack(fill=tk.BOTH, expand=True)
        layers_tab = ttk.Frame(tabs, padding=3)
        cells_tab = ttk.Frame(tabs, padding=3)
        tabs.add(layers_tab, text="Layers")
        tabs.add(cells_tab, text="Cells")
        group_row = ttk.Frame(layers_tab)
        group_row.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(group_row, text="Group:").pack(side=tk.LEFT)
        self.group_combo = ttk.Combobox(group_row, values=("Layers in layout",), state="readonly")
        self.group_combo.set("Layers in layout")
        self.group_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        search_row = ttk.Frame(layers_tab)
        search_row.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(search_row, text="Search:").pack(side=tk.LEFT)
        search_entry = ttk.Entry(search_row, textvariable=self._layer_filter)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        self._layer_filter.trace_add("write", lambda *_args: self._refresh_layer_rows())
        self.layer_tree = ttk.Treeview(
            layers_tab,
            columns=("layer", "datatype", "vis", "sel", "top"),
            show="tree headings",
            height=20,
        )
        self.layer_tree.heading("#0", text="")
        self.layer_tree.heading("vis", text="V")
        self.layer_tree.heading("sel", text="S")
        self.layer_tree.heading("top", text="T")
        self.layer_tree.heading("layer", text="Layer")
        self.layer_tree.heading("datatype", text="Datatype")
        self.layer_tree.column("#0", width=24, stretch=False, anchor=tk.CENTER)
        self.layer_tree.column("layer", width=48, stretch=True, anchor=tk.CENTER)
        self.layer_tree.column("datatype", width=62, stretch=True, anchor=tk.CENTER)
        for column in ("vis", "sel", "top"):
            self.layer_tree.column(column, width=24, stretch=False, anchor=tk.CENTER)
        layer_scroll = ttk.Scrollbar(layers_tab, orient=tk.VERTICAL, command=self.layer_tree.yview)
        self.layer_tree.configure(yscrollcommand=layer_scroll.set)
        self.layer_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        layer_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.layer_tree.bind("<ButtonRelease-1>", self._toggle_layer)

        self.cell_tree = ttk.Treeview(cells_tab, columns=("instances",), show="tree headings")
        self.cell_tree.heading("#0", text="Cells")
        self.cell_tree.heading("instances", text="Refs")
        self.cell_tree.column("#0", anchor=tk.W, width=215, stretch=True)
        self.cell_tree.column("instances", anchor=tk.CENTER, width=42, stretch=False)
        cell_scroll = ttk.Scrollbar(cells_tab, orient=tk.VERTICAL, command=self.cell_tree.yview)
        self.cell_tree.configure(yscrollcommand=cell_scroll.set)
        self.cell_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cell_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.cell_tree.bind("<Double-1>", self._choose_cell_from_tree)
        self.cell_tree.bind("<<TreeviewOpen>>", self._expand_cell_tree)

    def _refresh_layer_rows(self) -> None:
        if not hasattr(self, "layer_tree"):
            return
        for item in self.layer_tree.get_children():
            self.layer_tree.delete(item)
        query = self._layer_filter.get().strip().lower()
        for layer, dtype in self._layer_keys:
            label = f"{layer} {dtype}"
            if query and query not in label.lower():
                continue
            key = (layer, dtype)
            self.layer_tree.insert(
                "", tk.END, iid=f"{layer}:{dtype}", image=self._layer_images.get(key),
                values=(str(layer), str(dtype), "×" if key in self.visible_layers else "", "", ""),
            )
        if self.layer_summary is not None:
            if self._layer_keys:
                layer, dtype = self._layer_keys[0]
                self.layer_summary.configure(text=f"Layer {layer}    Datatype {dtype}    @0")
            else:
                self.layer_summary.configure(text="—    [drawing]    @0")

    def _show_all_layers(self) -> None:
        self.visible_layers = set(self._layer_keys)
        self._refresh_layer_rows()
        self.redraw()

    def _hide_all_layers(self) -> None:
        self.visible_layers.clear()
        self._refresh_layer_rows()
        self.redraw()

    def _choose_cell_from_tree(self, _event=None) -> None:
        selected = self.cell_tree.selection()
        if selected and selected[0] in self._cell_iid_to_name:
            self.cell_var.set(self._cell_iid_to_name[selected[0]])
            self._choose_cell()

    def open_dialog(self) -> None:
        path = filedialog.askopenfilename(
            title="Open GDSII layout",
            filetypes=[
                ("GDSII files", "*.gds *.gdsii *.gds2 *.stream *.gds.gz"),
                ("All files", "*"),
            ],
        )
        if path:
            self.load_file(path)

    def load_file(self, path: str) -> None:
        try:
            layout = read_gds(path)
        except Exception as exc:
            messagebox.showerror("Cannot open GDS", str(exc), parent=self.root)
            return

        self.layout = layout
        self.file_path = path
        referenced: set[str] = set()
        for cell in layout.cells.values():
            for element in cell.elements:
                if element.kind in ("sref", "aref") and element.target:
                    referenced.add(element.target)
        top_cells = sorted(name for name in layout.cells if name not in referenced)
        choices = top_cells or sorted(layout.cells)
        self.cell_combo["values"] = sorted(layout.cells)
        self.file_label.configure(text=os.path.basename(path))
        self.layout_button.configure(text="0:Layouts(1)")
        self.cell_name = choices[0]
        self.cell_var.set(self.cell_name)
        self.root.title(f"GDS Viewer - {os.path.basename(path)} -- Cell={self.cell_name}")
        self._populate_cell_tree()
        self._prepare_view()
        self._populate_layers()
        self.fit_view()

    def _walk_shapes(self) -> Iterator[tuple[str, int, int, tuple, str, float]]:
        if self.layout is None:
            return
        layout = self.layout
        self.truncated = False

        def walk(
            name: str,
            transform: Transform,
            stack: tuple[str, ...],
            depth: int,
        ) -> Iterator[tuple[str, int, int, tuple, str, float]]:
            if depth > 64:
                self.truncated = True
                return
            if name in stack:
                return
            cell = layout.cells.get(name)
            if cell is None:
                return
            next_stack = stack + (name,)
            for element in cell.elements:
                if element.kind in ("boundary", "box", "path", "node"):
                    if not element.points:
                        continue
                    points = tuple(
                        (px * layout.user_units_per_dbu, py * layout.user_units_per_dbu)
                        for px, py in (_apply(transform, x, y) for x, y in element.points)
                    )
                    a, _b, c, _d, _tx, _ty = transform
                    width_scale = math.hypot(a, c)
                    width = abs(element.width) * layout.user_units_per_dbu * width_scale
                    yield (
                        element.kind,
                        element.layer,
                        element.dtype,
                        points,
                        "",
                        width,
                    )
                elif element.kind == "text":
                    if not element.points:
                        continue
                    x, y = _apply(transform, *element.points[0])
                    yield (
                        "text",
                        element.layer,
                        element.dtype,
                        ((x * layout.user_units_per_dbu, y * layout.user_units_per_dbu),),
                        element.text,
                        0.0,
                    )
                elif self.descend_hierarchy and element.kind in ("sref", "aref") and element.target in layout.cells:
                    origins = element.points[:3]
                    if not origins:
                        continue
                    origin = origins[0]
                    if element.kind == "aref" and len(origins) >= 3:
                        cols = max(1, element.columns)
                        rows = max(1, element.rows)
                        col_dx = (origins[1][0] - origin[0]) / cols
                        col_dy = (origins[1][1] - origin[1]) / cols
                        row_dx = (origins[2][0] - origin[0]) / rows
                        row_dy = (origins[2][1] - origin[1]) / rows
                    else:
                        cols = rows = 1
                        col_dx = col_dy = row_dx = row_dy = 0.0
                    for row in range(rows):
                        for col in range(cols):
                            x = origin[0] + col * col_dx + row * row_dx
                            y = origin[1] + col * col_dy + row * row_dy
                            local = _reference_transform(element, x, y)
                            yield from walk(
                                element.target,
                                _compose(transform, local),
                                next_stack,
                                depth + 1,
                            )
        yield from walk(self.cell_name, IDENTITY, (), 0)

    def _prepare_view(self) -> None:
        min_x = min_y = math.inf
        max_x = max_y = -math.inf
        layer_keys = self._collect_hierarchy_layers(self.cell_name)
        self._shapes = []
        for kind, layer, dtype, points, label, path_width in self._walk_shapes():
            xs, ys = zip(*points)
            box = (min(xs), min(ys), max(xs), max(ys))
            self._shapes.append((kind, layer, dtype, points, label, path_width, box))
            min_x, min_y = min(min_x, box[0]), min(min_y, box[1])
            max_x, max_y = max(max_x, box[2]), max(max_y, box[3])
        self.shape_count = len(self._shapes)
        self._layer_keys = sorted(layer_keys)
        self.visible_layers = layer_keys
        self.bounds = None if not self._shapes else (min_x, min_y, max_x, max_y)

    def _collect_hierarchy_layers(self, root_name: str) -> set[tuple[int, int]]:
        if self.layout is None:
            return set()
        layers: set[tuple[int, int]] = set()
        visited: set[str] = set()
        pending = [root_name]
        geometry_kinds = {"boundary", "box", "path", "text", "node"}
        while pending:
            name = pending.pop()
            if name in visited:
                continue
            visited.add(name)
            cell = self.layout.cells.get(name)
            if cell is None:
                continue
            for element in cell.elements:
                if element.kind in geometry_kinds:
                    layers.add((element.layer, element.dtype))
                elif self.descend_hierarchy and element.kind in ("sref", "aref") and element.target:
                    pending.append(element.target)
        return layers

    def _cell_targets(self, cell_name: str) -> list[tuple[str, int]]:
        if self.layout is None or cell_name not in self.layout.cells:
            return []
        counts: dict[str, int] = {}
        for element in self.layout.cells[cell_name].elements:
            if element.kind not in ("sref", "aref") or element.target not in self.layout.cells:
                continue
            instances = max(1, element.columns) * max(1, element.rows) if element.kind == "aref" else 1
            counts[element.target] = counts.get(element.target, 0) + instances
        return sorted(counts.items())

    def _populate_cell_tree(self) -> None:
        for item in self.cell_tree.get_children():
            self.cell_tree.delete(item)
        self._cell_iid_to_name.clear()
        self._cell_name_to_iids.clear()
        self._cell_tree_ancestry.clear()
        referenced = {
            element.target
            for cell in self.layout.cells.values()
            for element in cell.elements
            if element.kind in ("sref", "aref") and element.target in self.layout.cells
        }
        roots = sorted(name for name in self.layout.cells if name not in referenced)
        if not roots:
            roots = sorted(self.layout.cells)
        for name in roots:
            iid = self._insert_cell_node("", name, 1, (name,))
            self._populate_cell_children(iid)
            self.cell_tree.item(iid, open=True)
        selected = self._cell_name_to_iids.get(self.cell_name, [])
        if selected:
            self.cell_tree.selection_set(selected[0])
            self.cell_tree.see(selected[0])

    def _insert_cell_node(
        self, parent: str, name: str, instances: int, ancestry: tuple[str, ...]
    ) -> str:
        self._cell_tree_serial += 1
        iid = f"cell-{self._cell_tree_serial}"
        self.cell_tree.insert(parent, tk.END, iid=iid, text=name, values=(instances,))
        self._cell_iid_to_name[iid] = name
        self._cell_name_to_iids.setdefault(name, []).append(iid)
        self._cell_tree_ancestry[iid] = ancestry
        if any(target not in ancestry for target, _count in self._cell_targets(name)):
            self._cell_tree_serial += 1
            placeholder = f"pending-{self._cell_tree_serial}"
            self.cell_tree.insert(iid, tk.END, iid=placeholder, text="", values=("",))
        return iid

    def _populate_cell_children(self, iid: str) -> None:
        name = self._cell_iid_to_name.get(iid)
        if name is None:
            return
        for child in self.cell_tree.get_children(iid):
            self.cell_tree.delete(child)
        ancestry = self._cell_tree_ancestry[iid]
        for target, count in self._cell_targets(name):
            if target in ancestry:
                continue
            self._insert_cell_node(iid, target, count, ancestry + (target,))

    def _expand_cell_tree(self, event=None) -> None:
        iid = self.cell_tree.focus()
        children = self.cell_tree.get_children(iid)
        if any(child.startswith("pending-") for child in children):
            self._populate_cell_children(iid)

    def _populate_layers(self) -> None:
        self._layer_images.clear()
        if self.layout is None:
            self._layer_keys = []
            self._layer_colors_cache = {}
            return
        self._layer_colors_cache = {
            key: self._color(index) for index, key in enumerate(self._layer_keys)
        }
        for layer, dtype in self._layer_keys:
            key = (layer, dtype)
            color = self._layer_colors_cache[key]
            swatch = tk.PhotoImage(master=self.root, width=12, height=12)
            swatch.put(color, to=(1, 1, 11, 11))
            self._layer_images[key] = swatch
        self._refresh_layer_rows()

    @staticmethod
    def _color(index: int) -> str:
        hue = (index * 0.618033988749895) % 1.0
        red, green, blue = colorsys.hsv_to_rgb(hue, 0.68, 1.0)
        return f"#{int(red * 255):02x}{int(green * 255):02x}{int(blue * 255):02x}"

    def _layer_colors(self) -> dict[tuple[int, int], str]:
        return self._layer_colors_cache

    def _toggle_layer(self, event) -> None:
        item = self.layer_tree.identify_row(event.y)
        if not item or ":" not in item:
            return
        layer, dtype = (int(part) for part in item.split(":"))
        key = (layer, dtype)
        if key in self.visible_layers:
            self.visible_layers.remove(key)
            self.layer_tree.set(item, "vis", "")
        else:
            self.visible_layers.add(key)
            self.layer_tree.set(item, "vis", "×")
        self.redraw()

    def _choose_cell(self, _event=None) -> None:
        selected = self.cell_var.get()
        if self.layout is None or selected not in self.layout.cells:
            return
        self.cell_name = selected
        tree_items = self._cell_name_to_iids.get(selected, [])
        if tree_items:
            self.cell_tree.selection_set(tree_items[0])
            self.cell_tree.see(tree_items[0])
        self._prepare_view()
        self._populate_layers()
        self.fit_view()

    def fit_view(self) -> None:
        if self.bounds is None:
            self.redraw()
            return
        self.root.update_idletasks()
        min_x, min_y, max_x, max_y = self.bounds
        width = max(1, self.canvas.winfo_width() - 40)
        height = max(1, self.canvas.winfo_height() - 40)
        span_x = max(max_x - min_x, 1e-12)
        span_y = max(max_y - min_y, 1e-12)
        self.scale = min(width / span_x, height / span_y)
        self.world_center = ((min_x + max_x) / 2, (min_y + max_y) / 2)
        self.redraw()

    def redraw(self) -> None:
        self.canvas.delete("all")
        if self.layout is None:
            return
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        center_x, center_y = self.world_center
        left = center_x - width / (2 * self.scale)
        right = center_x + width / (2 * self.scale)
        bottom = center_y - height / (2 * self.scale)
        top = center_y + height / (2 * self.scale)
        colors = self._layer_colors()
        for kind, layer, dtype, points, label, path_width, box in self._shapes:
            key = (layer, dtype)
            if key not in self.visible_layers:
                continue
            margin = 128 / self.scale
            if kind == "path":
                margin += path_width / 2
            elif kind == "text":
                margin += len(label) * 8 / self.scale
            if (
                box[2] + margin < left or box[0] - margin > right
                or box[3] + margin < bottom or box[1] - margin > top
            ):
                continue
            color = colors.get(key, "#ffffff")
            screen = [
                (
                    width / 2 + (x - center_x) * self.scale,
                    height / 2 - (y - center_y) * self.scale,
                )
                for x, y in points
            ]
            flat = [coordinate for point in screen for coordinate in point]
            if kind in ("boundary", "box") and len(screen) >= 3:
                self.canvas.create_polygon(flat, fill="", outline=color)
            elif kind == "path" and len(screen) >= 2:
                line_width = max(1.0, min(48.0, path_width * self.scale))
                self.canvas.create_line(
                    flat,
                    fill=color,
                    width=line_width,
                    capstyle=tk.ROUND,
                    joinstyle=tk.ROUND,
                )
            elif kind == "node":
                for sx, sy in screen:
                    self.canvas.create_rectangle(sx - 1, sy - 1, sx + 1, sy + 1, fill=color, outline=color)
            elif kind == "text" and label:
                self.canvas.create_text(
                    screen[0][0],
                    screen[0][1],
                    text=label,
                    fill=color,
                    anchor=tk.NW,
                    font=("TkDefaultFont", 8),
                )
        if self.truncated:
            note = "  |  hierarchy deeper than 64 levels was skipped"
        else:
            note = ""
        self.status.set(
            f"{os.path.basename(self.file_path)}  |  Cell: {self.cell_name}  |  "
            f"{self.shape_count:,} shapes  |  "
            f"{'Hierarchy descend' if self.descend_hierarchy else 'Current cell only'}  |  "
            f"scale {self.scale:.4g} px/user-unit{note}"
        )

    def _canvas_to_world(self, x: int, y: int) -> tuple[float, float]:
        width, height = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        center_x, center_y = self.world_center
        return (
            center_x + (x - width / 2) / self.scale,
            center_y - (y - height / 2) / self.scale,
        )

    def _show_coordinates(self, event) -> None:
        if self.layout is None:
            return
        x, y = self._canvas_to_world(event.x, event.y)
        self.root.title(
            f"GDS Viewer - {os.path.basename(self.file_path)} -- Cell={self.cell_name} - "
            f"X {x:.6g}, Y {y:.6g} user units"
        )

    def _zoom_at(self, x: int, y: int, factor: float) -> None:
        if self.layout is None:
            return
        anchor_x, anchor_y = self._canvas_to_world(x, y)
        old_scale = self.scale
        self.scale = min(max(old_scale * factor, 1e-12), 1e12)
        actual_factor = self.scale / old_scale
        width, height = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        self.world_center = (
            anchor_x - (x - width / 2) / self.scale,
            anchor_y + (y - height / 2) / self.scale,
        )
        # Scale the existing canvas items immediately; rebuild exact geometry
        # once the wheel settles instead of recreating up to 100k Tk items per tick.
        self.canvas.scale("all", x, y, actual_factor, actual_factor)
        if self._zoom_after is not None:
            self.root.after_cancel(self._zoom_after)
        self._zoom_after = self.root.after(110, self._finish_zoom)

    def _finish_zoom(self) -> None:
        self._zoom_after = None
        self.redraw()

    def _wheel_zoom(self, event) -> None:
        self._zoom_at(event.x, event.y, 1.15 if event.delta > 0 else 1 / 1.15)

    def _zoom_center(self, factor: float) -> None:
        self._zoom_at(self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2, factor)

    def _activate_pan(self) -> None:
        self.canvas.configure(cursor="fleur")

    def _fit_key(self, _event=None):
        focus = self.root.focus_get()
        if focus is not None and focus.winfo_class() in {
            "Entry", "TEntry", "TCombobox", "Spinbox", "TSpinbox", "Text",
        }:
            return
        state = getattr(_event, "state", 0)
        if state & 0x0001:
            self._set_hierarchy_mode(True)
        elif state & 0x0004:
            self._set_hierarchy_mode(False)
        else:
            self.fit_view()
        return "break"

    def _set_hierarchy_mode(self, enabled: bool) -> None:
        if self.descend_hierarchy == enabled:
            return
        self.descend_hierarchy = enabled
        if self.layout is not None:
            self._prepare_view()
            self._populate_layers()
            self.fit_view()
        else:
            self.status.set("Hierarchy descend" if enabled else "Current cell only")

    def _zoom_box_begin(self, event) -> None:
        self.canvas.focus_set()
        self._zoom_box_start = (event.x, event.y)
        self._zoom_box_item = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#ffff66", width=1, dash=(5, 3), fill="", tags=("zoom-box",),
        )

    def _zoom_box_move(self, event) -> None:
        if self._zoom_box_item is not None and self._zoom_box_start is not None:
            self.canvas.coords(self._zoom_box_item, *self._zoom_box_start, event.x, event.y)

    def _zoom_box_end(self, event) -> None:
        start = self._zoom_box_start
        item = self._zoom_box_item
        self._zoom_box_start = None
        self._zoom_box_item = None
        if item is not None:
            self.canvas.delete(item)
        if self.layout is None or start is None:
            return

        x0, y0 = start
        x1, y1 = event.x, event.y
        dx, dy = x1 - x0, y1 - y0
        box_width, box_height = abs(dx), abs(dy)
        if box_width < 12 or box_height < 12:
            return

        canvas_width = max(1, self.canvas.winfo_width())
        canvas_height = max(1, self.canvas.winfo_height())
        center_x = (x0 + x1) / 2
        center_y = (y0 + y1) / 2
        if dx > 0 and dy > 0:
            factor = min(canvas_width / box_width, canvas_height / box_height) * 0.95
        elif dx < 0 and dy < 0:
            factor = max(box_width / canvas_width, box_height / canvas_height) / 0.95
        else:
            self.status.set("Drag top-left to bottom-right to zoom in, or bottom-right to top-left to zoom out")
            return
        factor = min(max(factor, 0.1), 10.0)
        self._zoom_at(round(center_x), round(center_y), factor)

    def _pan_begin(self, event) -> None:
        self.canvas.focus_set()
        self._pan_start = (event.x, event.y, *self.world_center)
        self._pan_last = (event.x, event.y)

    def _pan_move(self, event) -> None:
        if self._pan_start is None:
            return
        start_x, start_y, center_x, center_y = self._pan_start
        self.world_center = (
            center_x - (event.x - start_x) / self.scale,
            center_y + (event.y - start_y) / self.scale,
        )
        if self._pan_last is not None:
            self.canvas.move("all", event.x - self._pan_last[0], event.y - self._pan_last[1])
        self._pan_last = (event.x, event.y)

    def _pan_end(self, _event) -> None:
        moved = self._pan_start is not None and self._pan_last != self._pan_start[:2]
        self._pan_start = None
        self._pan_last = None
        if moved:
            self.redraw()

    def _on_resize(self, _event) -> None:
        if self.layout is not None and self.root.winfo_exists():
            if self._resize_after is not None:
                self.root.after_cancel(self._resize_after)
            self._resize_after = self.root.after(100, self._redraw_after_resize)

    def _redraw_after_resize(self) -> None:
        self._resize_after = None
        self.redraw()


def main() -> None:
    root = tk.Tk()
    initial_file = sys.argv[1] if len(sys.argv) > 1 else None
    GDSViewer(root, initial_file)
    root.mainloop()


if __name__ == "__main__":
    main()
