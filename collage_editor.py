"""collage_editor.py — Photo Collage Editor dialog for the Snipping Tool.

Provides a full-featured Toplevel dialog that lets the user assemble multiple
images into a composite collage using preset layout templates, then hand the
finished PIL Image back to the main CanvasEditor for annotation and export.
"""

import os
import tkinter as tk
from tkinter import filedialog, colorchooser, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageOps

# ---------------------------------------------------------------------------
# Layout templates — each entry is a list of (nx, ny, nw, nh) normalized rects
# where 0.0 is the left/top and 1.0 is the full width/height of the canvas.
# ---------------------------------------------------------------------------
TEMPLATES = {
    "2 x 1":    [(0.0, 0.0, 0.5, 1.0), (0.5, 0.0, 0.5, 1.0)],
    "1 x 2":    [(0.0, 0.0, 1.0, 0.5), (0.0, 0.5, 1.0, 0.5)],
    "2 x 2":    [
        (0.0, 0.0, 0.5, 0.5), (0.5, 0.0, 0.5, 0.5),
        (0.0, 0.5, 0.5, 0.5), (0.5, 0.5, 0.5, 0.5),
    ],
    "3 x 1":    [(i / 3, 0.0, 1 / 3, 1.0) for i in range(3)],
    "1 x 3":    [(0.0, i / 3, 1.0, 1 / 3) for i in range(3)],
    "3 x 2":    [(j / 3, i / 2, 1 / 3, 0.5) for i in range(2) for j in range(3)],
    "2 x 3":    [(j / 2, i / 3, 0.5, 1 / 3) for i in range(3) for j in range(2)],
    "Focus L":  [
        (0.0, 0.0, 0.60, 1.0),
        (0.60, 0.0, 0.40, 0.5),
        (0.60, 0.5, 0.40, 0.5),
    ],
    "Focus R":  [
        (0.0, 0.0, 0.40, 0.5),
        (0.0, 0.5, 0.40, 0.5),
        (0.40, 0.0, 0.60, 1.0),
    ],
}

DEFAULT_OUT_W = 1920
DEFAULT_OUT_H = 1080


# ---------------------------------------------------------------------------
# CollageCell
# ---------------------------------------------------------------------------
class CollageCell:
    """Holds the state for one image slot in the collage."""

    def __init__(self, nx, ny, nw, nh):
        self.nx = float(nx)
        self.ny = float(ny)
        self.nw = float(nw)
        self.nh = float(nh)
        self.image = None          # PIL Image or None
        self.fit = "cover"         # "cover" | "contain" | "stretch"
        self.rotation = 0          # 0 | 90 | 180 | 270
        self.flip_h = False
        self.flip_v = False
        self.pan_x = 0.5           # 0.0 (Left) to 1.0 (Right), default 0.5 (Center)
        self.pan_y = 0.0           # 0.0 (Top) to 1.0 (Bottom), default 0.0 (Top -> URL bar visible by default!)

    def pixel_rect(self, out_w, out_h, gap):
        """Compute the inset pixel rect (x1, y1, x2, y2) for this cell."""
        half = gap // 2
        x1 = round(self.nx * out_w) + half
        y1 = round(self.ny * out_h) + half
        x2 = round((self.nx + self.nw) * out_w) - half
        y2 = round((self.ny + self.nh) * out_h) - half
        return x1, y1, max(x1 + 1, x2), max(y1 + 1, y2)

    def render_into(self, canvas_img, out_w, out_h, gap):
        """Paste this cell's rendered content into canvas_img at the correct position."""
        x1, y1, x2, y2 = self.pixel_rect(out_w, out_h, gap)
        cw, ch = x2 - x1, y2 - y1
        if cw <= 0 or ch <= 0:
            return

        if self.image is None:
            # Draw empty-cell placeholder: grey tile with crosshairs and plus icon
            placeholder = Image.new("RGBA", (cw, ch), (185, 190, 200, 255))
            d = ImageDraw.Draw(placeholder)
            d.line([(0, 0), (cw - 1, ch - 1)], fill=(160, 165, 175, 200), width=2)
            d.line([(cw - 1, 0), (0, ch - 1)], fill=(160, 165, 175, 200), width=2)
            d.rectangle([0, 0, cw - 1, ch - 1], outline=(140, 145, 155), width=2)
            icon_r = min(cw // 2, ch // 2, 28)
            cx_i, cy_i = cw // 2, ch // 2
            d.line([(cx_i - icon_r, cy_i), (cx_i + icon_r, cy_i)], fill=(90, 95, 110), width=3)
            d.line([(cx_i, cy_i - icon_r), (cx_i, cy_i + icon_r)], fill=(90, 95, 110), width=3)
            if cw > 120 and ch > 60:
                try:
                    from PIL import ImageFont
                    fnt_path = os.path.join("C:\\Windows\\Fonts", "segoeui.ttf")
                    fnt = ImageFont.truetype(fnt_path, 13) if os.path.exists(fnt_path) else ImageFont.load_default()
                    label = "Click to add image"
                    bbox = d.textbbox((0, 0), label, font=fnt)
                    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    d.text((cx_i - tw // 2, cy_i + icon_r + 8), label, fill=(90, 95, 110), font=fnt)
                except Exception:
                    pass
            canvas_img.paste(placeholder, (x1, y1), placeholder)
            return

        img = self.image.convert("RGBA")
        if self.rotation:
            img = img.rotate(-self.rotation, expand=True)
        if self.flip_h:
            img = ImageOps.mirror(img)
        if self.flip_v:
            img = ImageOps.flip(img)

        iw, ih = img.size
        if iw == 0 or ih == 0:
            return

        if self.fit == "stretch":
            img = img.resize((cw, ch), Image.LANCZOS)
            canvas_img.paste(img, (x1, y1), img)

        elif self.fit == "contain":
            scale = min(cw / iw, ch / ih)
            nw_i = max(1, int(iw * scale))
            nh_i = max(1, int(ih * scale))
            img = img.resize((nw_i, nh_i), Image.LANCZOS)
            extra_w = max(0, cw - nw_i)
            extra_h = max(0, ch - nh_i)
            px = x1 + int(extra_w * self.pan_x)
            py = y1 + int(extra_h * self.pan_y)
            canvas_img.paste(img, (px, py), img)

        else:  # cover (default)
            scale = max(cw / iw, ch / ih)
            nw_i = max(1, int(iw * scale))
            nh_i = max(1, int(ih * scale))
            img = img.resize((nw_i, nh_i), Image.LANCZOS)
            extra_w = max(0, nw_i - cw)
            extra_h = max(0, nh_i - ch)
            crop_x = int(extra_w * self.pan_x)
            crop_y = int(extra_h * self.pan_y)
            img = img.crop((crop_x, crop_y, crop_x + cw, crop_y + ch))
            canvas_img.paste(img, (x1, y1), img)


# ---------------------------------------------------------------------------
# CollageEditorDialog
# ---------------------------------------------------------------------------
class CollageEditorDialog(tk.Toplevel):
    """Full-featured photo collage editor dialog.

    Parameters
    ----------
    parent:
        The parent Tk window.
    theme_colors:
        Dict with keys: bg_color, panel_bg, accent_color, btn_bg,
        border_color, text_color, text_muted, canvas_bg, theme_name.
    initial_image:
        Optional PIL Image to pre-load into the first cell.
    result_callback:
        Called with the finished PIL Image when user clicks 'Add to Editor'.
    root_window:
        The root tk.Tk instance. Required to hide/restore both windows during
        in-dialog screen captures.
    """

    def __init__(self, parent, theme_colors, initial_image=None,
                 result_callback=None, root_window=None):
        super().__init__(parent)
        self.title("Photo Collage Editor")
        self.geometry("1160x720")
        self.minsize(900, 580)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self.tc = theme_colors
        self.configure(bg=self.tc["bg_color"])
        self.initial_image = initial_image
        self.result_callback = result_callback
        # Root Tk window needed for CaptureOverlay (which calls root.withdraw/deiconify)
        self._root_window = root_window if root_window is not None else parent

        # Runtime state
        self.cells = []
        self.selected_idx = None
        self.current_template = "1 x 2"    # default: two rows stacked vertically
        self.bg_color_val = "#EFEFEF" if self.tc.get("theme_name") == "light" else "#18191A"
        self.gap_var = tk.IntVar(value=8)
        self.out_w_var = tk.IntVar(value=DEFAULT_OUT_W)
        self.out_h_var = tk.IntVar(value=DEFAULT_OUT_H)

        self._preview_photo = None
        self._preview_scale = 1.0
        self._preview_ox = 0
        self._preview_oy = 0
        self._preview_ow = DEFAULT_OUT_W
        self._preview_oh = DEFAULT_OUT_H

        # Drag state
        self._drag_idx = None
        self._drag_start_x = 0.0
        self._drag_start_y = 0.0
        self._drag_orig_nx = 0.0
        self._drag_orig_ny = 0.0

        self._build_ui()
        self.after(60, lambda: self.apply_template("1 x 2"))
        self.lift()
        self.focus_set()

    # =========================================================================
    # UI CONSTRUCTION
    # =========================================================================

    def _build_ui(self):
        tc = self.tc

        # Title bar
        title_bar = tk.Frame(self, bg=tc["panel_bg"], height=46)
        title_bar.pack(fill=tk.X, side=tk.TOP)
        title_bar.pack_propagate(False)

        tk.Label(
            title_bar, text="  Photo Collage Editor",
            bg=tc["panel_bg"], fg=tc["text_color"],
            font=("Segoe UI", 11, "bold"), padx=18,
        ).pack(side=tk.LEFT, pady=10)

        tk.Label(
            title_bar,
            text="Choose a layout  |  Click empty cells to add photos  |  Adjust options  |  Export",
            bg=tc["panel_bg"], fg=tc["text_muted"],
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, pady=10)

        tk.Frame(self, bg=tc["border_color"], height=1).pack(fill=tk.X)

        # Body: left sidebar | center | right sidebar
        body = tk.Frame(self, bg=tc["bg_color"])
        body.pack(fill=tk.BOTH, expand=True)

        self._build_left_sidebar(body)
        self._build_right_sidebar(body)
        self._build_center(body)

        # Bottom bar
        tk.Frame(self, bg=tc["border_color"], height=1).pack(fill=tk.X)
        self._build_bottom_bar()

    def _build_left_sidebar(self, parent):
        tc = self.tc
        sidebar = tk.Frame(parent, bg=tc["panel_bg"], width=198)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Frame(sidebar, bg=tc["border_color"], width=1).pack(side=tk.RIGHT, fill=tk.Y)

        inner = tk.Frame(sidebar, bg=tc["panel_bg"])
        inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        # Layouts section
        self._section_lbl(inner, "LAYOUTS")
        self.template_btns = {}
        for name in TEMPLATES:
            btn = tk.Button(
                inner, text=name,
                bg=tc["btn_bg"], fg=tc["text_color"],
                activebackground=tc["accent_color"], activeforeground="#FFFFFF",
                bd=0, relief="flat", padx=10, pady=5,
                font=("Segoe UI", 9), anchor="w",
                command=lambda n=name: self.apply_template(n),
            )
            btn.pack(fill=tk.X, pady=1)
            self.template_btns[name] = btn

        # Background section
        self._divider(inner)
        self._section_lbl(inner, "BACKGROUND")
        bg_row = tk.Frame(inner, bg=tc["panel_bg"])
        bg_row.pack(fill=tk.X, pady=(2, 4))
        self.bg_swatch = tk.Label(
            bg_row, bg=self.bg_color_val, width=3, height=1, relief="solid", bd=1,
        )
        self.bg_swatch.pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(
            bg_row, text="Choose...",
            bg=tc["btn_bg"], fg=tc["text_color"],
            activebackground=tc["btn_bg"], activeforeground=tc["text_color"],
            bd=0, relief="flat", padx=8, pady=3, font=("Segoe UI", 9),
            command=self._pick_bg_color,
        ).pack(side=tk.LEFT)

        # Gap section
        self._divider(inner)
        self._section_lbl(inner, "GAP BETWEEN CELLS (px)")
        self.gap_label = tk.Label(
            inner, text=f"{self.gap_var.get()} px",
            bg=tc["panel_bg"], fg=tc["text_muted"], font=("Segoe UI", 8),
        )
        self.gap_label.pack(anchor="e")
        tk.Scale(
            inner, from_=0, to=40, orient=tk.HORIZONTAL,
            variable=self.gap_var, bg=tc["panel_bg"], fg=tc["text_color"],
            troughcolor=tc["btn_bg"], highlightthickness=0, bd=0,
            showvalue=False,
            command=self._on_gap_change,
        ).pack(fill=tk.X, pady=(0, 4))

        # Output size section
        self._divider(inner)
        self._section_lbl(inner, "OUTPUT SIZE (px)")
        size_row = tk.Frame(inner, bg=tc["panel_bg"])
        size_row.pack(fill=tk.X, pady=2)
        field_bg = "#FFFFFF" if tc.get("theme_name") == "light" else "#3A3C3E"

        tk.Label(size_row, text="W:", bg=tc["panel_bg"], fg=tc["text_muted"],
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        we = tk.Entry(size_row, textvariable=self.out_w_var, width=6, bd=0,
                      bg=field_bg, fg=tc["text_color"], font=("Segoe UI", 9),
                      highlightthickness=1, highlightbackground=tc["border_color"],
                      highlightcolor=tc["accent_color"])
        we.pack(side=tk.LEFT, padx=(2, 8), ipady=2)
        we.bind("<Return>", lambda e: self._render_preview())
        we.bind("<FocusOut>", lambda e: self._render_preview())

        tk.Label(size_row, text="H:", bg=tc["panel_bg"], fg=tc["text_muted"],
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        he = tk.Entry(size_row, textvariable=self.out_h_var, width=6, bd=0,
                      bg=field_bg, fg=tc["text_color"], font=("Segoe UI", 9),
                      highlightthickness=1, highlightbackground=tc["border_color"],
                      highlightcolor=tc["accent_color"])
        he.pack(side=tk.LEFT, padx=2, ipady=2)
        he.bind("<Return>", lambda e: self._render_preview())
        he.bind("<FocusOut>", lambda e: self._render_preview())

    def _build_center(self, parent):
        tc = self.tc
        center = tk.Frame(parent, bg=tc["bg_color"])
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Use grid layout so scrollbars can share the same cell space as the canvas
        canvas_outer = tk.Frame(center, bg=tc["canvas_bg"], bd=0)
        canvas_outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        canvas_outer.grid_rowconfigure(0, weight=1)
        canvas_outer.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            canvas_outer, bg=tc["canvas_bg"],
            highlightthickness=0, cursor="hand2",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # Vertical scrollbar
        v_scroll = tk.Scrollbar(
            canvas_outer, orient=tk.VERTICAL, command=self.canvas.yview,
            bg=tc["btn_bg"], troughcolor=tc["panel_bg"],
            relief="flat", bd=0, width=12,
        )
        v_scroll.grid(row=0, column=1, sticky="ns")

        # Horizontal scrollbar
        h_scroll = tk.Scrollbar(
            canvas_outer, orient=tk.HORIZONTAL, command=self.canvas.xview,
            bg=tc["btn_bg"], troughcolor=tc["panel_bg"],
            relief="flat", bd=0, width=12,
        )
        h_scroll.grid(row=1, column=0, sticky="ew")

        self.canvas.configure(
            xscrollcommand=h_scroll.set,
            yscrollcommand=v_scroll.set,
        )

        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Configure>", lambda e: self._render_preview())
        # Unified mouse wheel scrolling (handles Shift+MouseWheel for horizontal panning on Windows)
        self.canvas.bind("<MouseWheel>", self._on_canvas_mousewheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_canvas_mousewheel)

        self.status_lbl = tk.Label(
            center,
            text="Click empty cell: add image   |   Drag filled cell: pan image inside cell   |   Shift+Wheel: scroll H",
            bg=tc["bg_color"], fg=tc["text_muted"],
            font=("Segoe UI", 8, "italic"), pady=3,
        )
        self.status_lbl.pack(fill=tk.X, padx=10)

    def _build_right_sidebar(self, parent):
        tc = self.tc
        sidebar = tk.Frame(parent, bg=tc["panel_bg"], width=185)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Frame(sidebar, bg=tc["border_color"], width=1).pack(side=tk.LEFT, fill=tk.Y)

        inner = tk.Frame(sidebar, bg=tc["panel_bg"])
        inner.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Fixed header — always visible
        header = tk.Frame(inner, bg=tc["panel_bg"])
        header.pack(fill=tk.X, padx=12, pady=(12, 0))
        self._section_lbl(header, "CELL OPTIONS")

        self.lbl_hint = tk.Label(
            header, text="Select a cell\nto see options",
            bg=tc["panel_bg"], fg=tc["text_muted"],
            font=("Segoe UI", 9, "italic"), wraplength=145, justify="center",
        )
        self.lbl_hint.pack(pady=16)

        # Scrollable area for cell options
        # Uses a Canvas + Scrollbar so options never clip when the window is short
        # NOTE: not packed here — _update_cell_panel shows/hides it on selection change
        self._opts_scroll_container = tk.Frame(inner, bg=tc["panel_bg"])
        self._opts_scroll_container.grid_rowconfigure(0, weight=1)
        self._opts_scroll_container.grid_columnconfigure(0, weight=1)

        opts_canvas = tk.Canvas(
            self._opts_scroll_container, bg=tc["panel_bg"],
            highlightthickness=0, bd=0,
        )
        opts_canvas.grid(row=0, column=0, sticky="nsew")

        opts_v_scroll = tk.Scrollbar(
            self._opts_scroll_container, orient=tk.VERTICAL,
            command=opts_canvas.yview,
            bg=tc["btn_bg"], troughcolor=tc["panel_bg"],
            relief="flat", bd=0, width=10,
        )
        opts_v_scroll.grid(row=0, column=1, sticky="ns")

        opts_h_scroll = tk.Scrollbar(
            self._opts_scroll_container, orient=tk.HORIZONTAL,
            command=opts_canvas.xview,
            bg=tc["btn_bg"], troughcolor=tc["panel_bg"],
            relief="flat", bd=0, width=10,
        )
        opts_h_scroll.grid(row=1, column=0, sticky="ew")

        opts_canvas.configure(
            xscrollcommand=opts_h_scroll.set,
            yscrollcommand=opts_v_scroll.set,
        )

        # The actual options live in this inner frame placed on the canvas
        self.cell_opts = tk.Frame(opts_canvas, bg=tc["panel_bg"])
        self._opts_window_id = opts_canvas.create_window(
            (0, 0), window=self.cell_opts, anchor="nw"
        )

        def _on_opts_configure(event):
            opts_canvas.configure(scrollregion=opts_canvas.bbox("all"))
            # Keep frame width in sync with canvas width
            opts_canvas.itemconfig(self._opts_window_id, width=event.width)

        opts_canvas.bind("<Configure>", _on_opts_configure)

        # Mouse-wheel scrolling inside the options panel
        def _opts_scroll(event):
            opts_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        opts_canvas.bind("<MouseWheel>", _opts_scroll)
        self.cell_opts.bind("<MouseWheel>", _opts_scroll)

        # Fit mode
        self._mini_section(self.cell_opts, "FIT MODE")
        self.fit_var = tk.StringVar(value="cover")
        for val, lbl in [("cover", "Cover (fill cell)"),
                         ("contain", "Contain (letterbox)"),
                         ("stretch", "Stretch (distort)")]:
            tk.Radiobutton(
                self.cell_opts, text=lbl,
                variable=self.fit_var, value=val,
                bg=tc["panel_bg"], fg=tc["text_color"],
                selectcolor=tc["btn_bg"], activebackground=tc["panel_bg"],
                font=("Segoe UI", 9),
                command=self._on_cell_opt_changed,
            ).pack(anchor="w", padx=12)

        self._thin_divider_padded(self.cell_opts)

        # Image Pan / Crop Position
        self._mini_section(self.cell_opts, "VERTICAL PAN / CROP")
        self.pan_y_var = tk.DoubleVar(value=0.0)
        self.pan_y_lbl = tk.Label(
            self.cell_opts, text="Top (0%)",
            bg=tc["panel_bg"], fg=tc["text_muted"], font=("Segoe UI", 8),
        )
        self.pan_y_lbl.pack(anchor="e", padx=12)

        scale_y = tk.Scale(
            self.cell_opts, from_=0.0, to=1.0, resolution=0.01,
            orient=tk.HORIZONTAL, variable=self.pan_y_var,
            bg=tc["panel_bg"], fg=tc["text_color"],
            troughcolor=tc["btn_bg"], highlightthickness=0, bd=0,
            showvalue=False, command=self._on_pan_slider_changed,
        )
        scale_y.pack(fill=tk.X, padx=12, pady=(0, 2))

        v_preset_frame = tk.Frame(self.cell_opts, bg=tc["panel_bg"])
        v_preset_frame.pack(fill=tk.X, padx=12, pady=(0, 4))
        for p_lbl, p_val in [("Top", 0.0), ("Center", 0.5), ("Bottom", 1.0)]:
            tk.Button(
                v_preset_frame, text=p_lbl,
                bg=tc["btn_bg"], fg=tc["text_color"],
                activebackground=tc["accent_color"], activeforeground="#FFFFFF",
                bd=0, relief="flat", padx=6, pady=2, font=("Segoe UI", 8),
                command=lambda v=p_val: self._set_cell_pan_y(v),
            ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        self._thin_divider_padded(self.cell_opts)

        self._mini_section(self.cell_opts, "HORIZONTAL PAN / CROP")
        self.pan_x_var = tk.DoubleVar(value=0.5)
        self.pan_x_lbl = tk.Label(
            self.cell_opts, text="Center (50%)",
            bg=tc["panel_bg"], fg=tc["text_muted"], font=("Segoe UI", 8),
        )
        self.pan_x_lbl.pack(anchor="e", padx=12)

        scale_x = tk.Scale(
            self.cell_opts, from_=0.0, to=1.0, resolution=0.01,
            orient=tk.HORIZONTAL, variable=self.pan_x_var,
            bg=tc["panel_bg"], fg=tc["text_color"],
            troughcolor=tc["btn_bg"], highlightthickness=0, bd=0,
            showvalue=False, command=self._on_pan_slider_changed,
        )
        scale_x.pack(fill=tk.X, padx=12, pady=(0, 2))

        h_preset_frame = tk.Frame(self.cell_opts, bg=tc["panel_bg"])
        h_preset_frame.pack(fill=tk.X, padx=12, pady=(0, 4))
        for p_lbl, p_val in [("Left", 0.0), ("Center", 0.5), ("Right", 1.0)]:
            tk.Button(
                h_preset_frame, text=p_lbl,
                bg=tc["btn_bg"], fg=tc["text_color"],
                activebackground=tc["accent_color"], activeforeground="#FFFFFF",
                bd=0, relief="flat", padx=6, pady=2, font=("Segoe UI", 8),
                command=lambda v=p_val: self._set_cell_pan_x(v),
            ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        self._thin_divider_padded(self.cell_opts)

        # Rotation
        self._mini_section(self.cell_opts, "ROTATION")
        self.rot_var = tk.StringVar(value="0")
        for val, lbl in [("0", "0 deg"), ("90", "90 deg"), ("180", "180 deg"), ("270", "270 deg")]:
            tk.Radiobutton(
                self.cell_opts, text=lbl,
                variable=self.rot_var, value=val,
                bg=tc["panel_bg"], fg=tc["text_color"],
                selectcolor=tc["btn_bg"], activebackground=tc["panel_bg"],
                font=("Segoe UI", 9),
                command=self._on_cell_opt_changed,
            ).pack(anchor="w", padx=12)

        self._thin_divider_padded(self.cell_opts)

        # Flip
        self._mini_section(self.cell_opts, "FLIP")
        self.flip_h_var = tk.BooleanVar(value=False)
        self.flip_v_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self.cell_opts, text="Flip Horizontal",
            variable=self.flip_h_var,
            bg=tc["panel_bg"], fg=tc["text_color"],
            selectcolor=tc["btn_bg"], activebackground=tc["panel_bg"],
            font=("Segoe UI", 9),
            command=self._on_cell_opt_changed,
        ).pack(anchor="w", padx=12)
        tk.Checkbutton(
            self.cell_opts, text="Flip Vertical",
            variable=self.flip_v_var,
            bg=tc["panel_bg"], fg=tc["text_color"],
            selectcolor=tc["btn_bg"], activebackground=tc["panel_bg"],
            font=("Segoe UI", 9),
            command=self._on_cell_opt_changed,
        ).pack(anchor="w", padx=12)

        self._thin_divider_padded(self.cell_opts)

        tk.Button(
            self.cell_opts, text="Replace Image",
            bg=tc["btn_bg"], fg=tc["text_color"],
            activebackground=tc["btn_bg"], activeforeground=tc["text_color"],
            bd=0, relief="flat", padx=8, pady=5,
            font=("Segoe UI", 9), anchor="w",
            command=self._replace_cell_image,
        ).pack(fill=tk.X, padx=12, pady=2)
        tk.Button(
            self.cell_opts, text="Clear Image",
            bg=tc["btn_bg"], fg="#E05555",
            activebackground=tc["btn_bg"], activeforeground="#E05555",
            bd=0, relief="flat", padx=8, pady=5,
            font=("Segoe UI", 9), anchor="w",
            command=self._clear_cell_image,
        ).pack(fill=tk.X, padx=12, pady=2)

    def _build_bottom_bar(self):
        tc = self.tc
        bar = tk.Frame(self, bg=tc["panel_bg"], height=54)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)

        inner = tk.Frame(bar, bg=tc["panel_bg"])
        inner.pack(fill=tk.BOTH, expand=True, padx=16)

        self.info_lbl = tk.Label(
            inner, text="0 / 0 cells filled",
            bg=tc["panel_bg"], fg=tc["text_muted"],
            font=("Segoe UI", 9, "italic"),
        )
        self.info_lbl.pack(side=tk.LEFT, pady=14)

        tk.Button(
            inner, text="Cancel", command=self.destroy,
            bg=tc["btn_bg"], fg=tc["text_color"],
            activebackground=tc["btn_bg"], activeforeground=tc["text_color"],
            bd=0, relief="flat", padx=14, pady=6, font=("Segoe UI", 9, "bold"),
        ).pack(side=tk.RIGHT, padx=(4, 0), pady=10)

        tk.Button(
            inner, text="Save As...", command=self._save_as,
            bg=tc["btn_bg"], fg=tc["text_color"],
            activebackground=tc["btn_bg"], activeforeground=tc["text_color"],
            bd=0, relief="flat", padx=14, pady=6, font=("Segoe UI", 9, "bold"),
        ).pack(side=tk.RIGHT, padx=4, pady=10)

        tk.Button(
            inner, text="Add to Editor", command=self._add_to_editor,
            bg=tc["accent_color"], fg="#FFFFFF",
            activebackground="#1D4FD8", activeforeground="#FFFFFF",
            bd=0, relief="flat", padx=14, pady=6, font=("Segoe UI", 9, "bold"),
        ).pack(side=tk.RIGHT, padx=4, pady=10)

    # =========================================================================
    # SMALL UI HELPERS
    # =========================================================================

    def _section_lbl(self, parent, text):
        tk.Label(
            parent, text=text,
            bg=self.tc["panel_bg"], fg=self.tc["text_muted"],
            font=("Segoe UI", 7, "bold"), anchor="w",
        ).pack(fill=tk.X, pady=(8, 2))

    def _mini_section(self, parent, text):
        tk.Label(
            parent, text=text,
            bg=self.tc["panel_bg"], fg=self.tc["text_muted"],
            font=("Segoe UI", 7, "bold"), anchor="w",
        ).pack(fill=tk.X, pady=(6, 1))

    def _divider(self, parent):
        tk.Frame(parent, bg=self.tc["border_color"], height=1).pack(fill=tk.X, pady=6)

    def _thin_divider(self, parent):
        tk.Frame(parent, bg=self.tc["border_color"], height=1).pack(fill=tk.X, pady=4)

    def _thin_divider_padded(self, parent):
        """Thin divider with horizontal padding, used inside the scrollable cell options."""
        tk.Frame(parent, bg=self.tc["border_color"], height=1).pack(fill=tk.X, padx=12, pady=4)

    def _highlight_template(self, active):
        tc = self.tc
        for name, btn in self.template_btns.items():
            if name == active:
                btn.configure(bg=tc["accent_color"], fg="#FFFFFF")
            else:
                btn.configure(bg=tc["btn_bg"], fg=tc["text_color"])

    # =========================================================================
    # TEMPLATE / CELL MANAGEMENT
    # =========================================================================

    def apply_template(self, name):
        """Rebuild cell list from the chosen template, preserving existing images."""
        rects = TEMPLATES.get(name, TEMPLATES["2 x 1"])
        old_images = [c.image for c in self.cells if c.image is not None]

        self.cells = [CollageCell(nx, ny, nw, nh) for nx, ny, nw, nh in rects]

        # Redistribute previously loaded images
        for i, img in enumerate(old_images):
            if i < len(self.cells):
                self.cells[i].image = img

        # Pre-load initial snip into first empty slot
        if self.initial_image is not None:
            for cell in self.cells:
                if cell.image is None:
                    cell.image = self.initial_image
                    self.initial_image = None
                    break

        self.current_template = name
        self.selected_idx = None
        self._highlight_template(name)
        self._update_cell_panel()
        self._render_preview()

    # =========================================================================
    # PREVIEW RENDERING
    # =========================================================================

    def _safe_out_dims(self):
        try:
            ow = max(100, self.out_w_var.get())
            oh = max(100, self.out_h_var.get())
        except Exception:
            ow, oh = DEFAULT_OUT_W, DEFAULT_OUT_H
        return ow, oh

    def _compute_preview_layout(self):
        """Return (scale, ox, oy, preview_w, preview_h) to fit collage in canvas."""
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        ow, oh = self._safe_out_dims()
        margin = 0.93
        scale = min(cw / ow, ch / oh) * margin
        scale = max(0.01, scale)
        pw = int(ow * scale)
        ph = int(oh * scale)
        ox = (cw - pw) // 2
        oy = (ch - ph) // 2
        return scale, ox, oy, pw, ph

    def _render_preview(self, *_):
        """Re-render the collage composite and refresh the canvas widget."""
        ow, oh = self._safe_out_dims()
        gap = self.gap_var.get()

        bg_rgba = self._hex_to_rgba(self.bg_color_val)
        canvas_img = Image.new("RGBA", (ow, oh), bg_rgba)
        for cell in self.cells:
            cell.render_into(canvas_img, ow, oh, gap)

        # Draw selection highlight
        if self.selected_idx is not None and self.selected_idx < len(self.cells):
            sel = self.cells[self.selected_idx]
            rx1, ry1, rx2, ry2 = sel.pixel_rect(ow, oh, gap)
            d = ImageDraw.Draw(canvas_img)
            for offset in range(4, 0, -1):
                alpha = 60 + offset * 30
                d.rectangle(
                    [rx1 - offset, ry1 - offset, rx2 + offset, ry2 + offset],
                    outline=(59, 130, 246, alpha),
                )
            d.rectangle([rx1, ry1, rx2, ry2], outline="#FFFFFF", width=2)
            # Corner tabs
            tab = 14
            blue = (59, 130, 246, 255)
            for cx_t, cy_t in [(rx1, ry1), (rx2, ry1), (rx1, ry2), (rx2, ry2)]:
                sx = 1 if cx_t == rx1 else -1
                sy = 1 if cy_t == ry1 else -1
                d.line([(cx_t, cy_t), (cx_t + sx * tab, cy_t)], fill=blue, width=3)
                d.line([(cx_t, cy_t), (cx_t, cy_t + sy * tab)], fill=blue, width=3)

        # Scale to preview
        scale, ox, oy, pw, ph = self._compute_preview_layout()
        self._preview_scale = scale
        self._preview_ox = ox
        self._preview_oy = oy
        self._preview_ow = ow
        self._preview_oh = oh

        preview = canvas_img.resize((pw, ph), Image.LANCZOS)
        self._preview_photo = ImageTk.PhotoImage(preview)

        self.canvas.delete("all")
        self._draw_checker(ox, oy, pw, ph)
        self.canvas.create_image(ox, oy, anchor="nw", image=self._preview_photo)

        # Update scroll region so H+V scrollbars reflect the true content extents
        margin = max(ox, 20)
        scroll_w = max(pw + ox * 2, self.canvas.winfo_width())
        scroll_h = max(ph + oy * 2, self.canvas.winfo_height())
        self.canvas.configure(scrollregion=(0, 0, scroll_w, scroll_h))

        filled = sum(1 for c in self.cells if c.image is not None)
        total = len(self.cells)
        self.info_lbl.config(text=f"{filled} / {total} cells filled")

    def _draw_checker(self, ox, oy, pw, ph):
        """Draw a subtle checkerboard behind the preview area."""
        csize = 8
        c1 = "#D8D8D8" if self.tc.get("theme_name") == "light" else "#2A2A2A"
        c2 = "#C8C8C8" if self.tc.get("theme_name") == "light" else "#242424"
        for row in range(0, ph, csize):
            for col in range(0, pw, csize):
                color = c1 if (row // csize + col // csize) % 2 == 0 else c2
                self.canvas.create_rectangle(
                    ox + col, oy + row,
                    min(ox + col + csize, ox + pw),
                    min(oy + row + csize, oy + ph),
                    fill=color, outline="",
                )

    # =========================================================================
    # CANVAS INTERACTION
    # =========================================================================

    def _canvas_to_img(self, cx, cy):
        """Convert canvas pixel coordinates to collage image coordinates."""
        scale = self._preview_scale if self._preview_scale else 1.0
        return (cx - self._preview_ox) / scale, (cy - self._preview_oy) / scale

    def _cell_at(self, ix, iy):
        """Return index of the cell at image coords (ix, iy), or None."""
        ow, oh = self._safe_out_dims()
        gap = self.gap_var.get()
        for i, cell in enumerate(self.cells):
            x1, y1, x2, y2 = cell.pixel_rect(ow, oh, gap)
            if x1 <= ix <= x2 and y1 <= iy <= y2:
                return i
        return None

    def _on_canvas_press(self, event):
        # Translate canvas coords (affected by scroll) to image coords
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        ix, iy = self._canvas_to_img(cx, cy)
        idx = self._cell_at(ix, iy)
        if idx is None:
            return

        self._drag_idx = idx
        self._drag_start_x = ix
        self._drag_start_y = iy
        cell = self.cells[idx]
        self._drag_orig_nx = cell.nx
        self._drag_orig_ny = cell.ny
        self._drag_pan_start_x = cell.pan_x
        self._drag_pan_start_y = cell.pan_y

        if cell.image is None:
            # Empty cell — show action popup (capture / screenshot / browse)
            self.selected_idx = idx
            self._update_cell_panel()
            self._render_preview()
            self.after(60, lambda i=idx, e=event: self._show_cell_action_menu(i, e))
        else:
            # Filled cell — select it and prepare drag-pan
            self.selected_idx = idx
            self._update_cell_panel()
            self._render_preview()

    def _on_canvas_drag(self, event):
        if self._drag_idx is None:
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        ix, iy = self._canvas_to_img(cx, cy)
        ow, oh = self._safe_out_dims()
        cell = self.cells[self._drag_idx]

        # If dragging a filled cell, pan the image inside the cell dynamically!
        if cell.image is not None:
            dcx = ix - self._drag_start_x
            dcy = iy - self._drag_start_y
            gap = self.gap_var.get()
            rx1, ry1, rx2, ry2 = cell.pixel_rect(ow, oh, gap)
            cw, ch = max(1, rx2 - rx1), max(1, ry2 - ry1)

            # Source image scaled size
            img = cell.image
            if cell.rotation:
                img = img.rotate(-cell.rotation, expand=True)
            iw, ih = img.size
            if iw > 0 and ih > 0:
                if cell.fit == "contain":
                    scale = min(cw / iw, ch / ih)
                    nw_i, nh_i = int(iw * scale), int(ih * scale)
                    extra_w = max(1, cw - nw_i)
                    extra_h = max(1, ch - nh_i)
                    cell.pan_x = max(0.0, min(1.0, self._drag_pan_start_x + dcx / extra_w))
                    cell.pan_y = max(0.0, min(1.0, self._drag_pan_start_y + dcy / extra_h))
                else:  # cover
                    scale = max(cw / iw, ch / ih)
                    nw_i, nh_i = int(iw * scale), int(ih * scale)
                    extra_w = max(1, nw_i - cw)
                    extra_h = max(1, nh_i - ch)
                    cell.pan_x = max(0.0, min(1.0, self._drag_pan_start_x - dcx / extra_w))
                    cell.pan_y = max(0.0, min(1.0, self._drag_pan_start_y - dcy / extra_h))

                self.pan_x_var.set(cell.pan_x)
                self.pan_y_var.set(cell.pan_y)
                self._update_pan_labels()
                self._render_preview()
            return

        # If template is Focus layout and cell is empty, allow freeform box movement
        dx = (ix - self._drag_start_x) / ow
        dy = (iy - self._drag_start_y) / oh
        new_nx = max(0.0, min(1.0 - cell.nw, self._drag_orig_nx + dx))
        new_ny = max(0.0, min(1.0 - cell.nh, self._drag_orig_ny + dy))
        if self.current_template in ("Focus L", "Focus R"):
            cell.nx = new_nx
            cell.ny = new_ny
            self._render_preview()

    def _on_canvas_release(self, event):
        self._drag_idx = None

    def _on_canvas_mousewheel(self, event):
        """Unified mousewheel handler for canvas that works cleanly on Windows."""
        delta = int(-1 * (event.delta / 120)) if event.delta else 0
        if not delta:
            return
        # Check Shift modifier
        is_shift = bool(getattr(event, "state", 0) & 0x0001) or "Shift" in str(getattr(event, "type", ""))
        if is_shift:
            self.canvas.xview_scroll(delta, "units")
        else:
            self.canvas.yview_scroll(delta, "units")

    # =========================================================================
    # CELL ACTION MENU
    # =========================================================================

    def _show_cell_action_menu(self, idx, event):
        """Pop up a context menu with image-acquisition options for an empty cell."""
        menu = tk.Menu(self, tearoff=0,
                       bg=self.tc["panel_bg"], fg=self.tc["text_color"],
                       activebackground=self.tc["accent_color"],
                       activeforeground="#FFFFFF",
                       relief="flat", bd=1,
                       font=("Segoe UI", 9))
        menu.add_command(
            label="  Capture Region  ",
            command=lambda: self._capture_region_into(idx),
        )
        menu.add_command(
            label="  Full Screenshot  ",
            command=lambda: self._capture_screenshot_into(idx),
        )
        menu.add_separator()
        menu.add_command(
            label="  Browse File...  ",
            command=lambda: self._load_image_into(idx),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _capture_region_into(self, idx):
        """Hide both windows, trigger the CaptureOverlay, then restore and load result."""
        import time
        from capture import CaptureOverlay

        # Release grab so the overlay can receive mouse events
        self.grab_release()
        self.withdraw()
        # CaptureOverlay will call root_window.withdraw() internally — just let it

        def on_capture_done(image):
            """Callback fired by CaptureOverlay after user selects a region."""
            # root_window is already restored by CaptureOverlay.close()
            self.deiconify()
            self.grab_set()        # re-acquire the modal grab
            self.lift()
            self.focus_set()
            if image:
                self.cells[idx].image = image.convert("RGBA")
                self.selected_idx = idx
                self._update_cell_panel()
                self._render_preview()
                self._update_fill_info()

        # CaptureOverlay hides root_window, shows overlay, then restores root_window
        CaptureOverlay(
            self._root_window,
            mode="free",
            callback=on_capture_done,
        )

    def _capture_screenshot_into(self, idx):
        """Hide both windows, grab the full screen, then restore and load the image."""
        import time
        from PIL import ImageGrab

        self.grab_release()
        self.withdraw()
        self._root_window.withdraw()
        self._root_window.update()
        time.sleep(0.40)   # let windows disappear before grabbing

        try:
            image = ImageGrab.grab(all_screens=True)
        except Exception:
            image = ImageGrab.grab()

        self._root_window.deiconify()
        self._root_window.update()
        self.deiconify()
        self.grab_set()
        self.lift()
        self.focus_set()

        if image:
            self.cells[idx].image = image.convert("RGBA")
            self.selected_idx = idx
            self._update_cell_panel()
            self._render_preview()
            self._update_fill_info()

    # =========================================================================
    # IMAGE LOADING
    # =========================================================================

    def _load_image_into(self, idx):
        """Open file picker and load chosen image into cell[idx]."""
        path = filedialog.askopenfilename(
            parent=self,
            title=f"Add Image to Cell {idx + 1}",
            filetypes=[
                ("Image Files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp;*.tiff;*.tif"),
                ("All Files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
            self.cells[idx].image = img
        except Exception as e:
            messagebox.showerror("Image Error", f"Could not open image:\n{e}", parent=self)
            return
        self._render_preview()
        self._update_fill_info()

    def _replace_cell_image(self):
        if self.selected_idx is not None:
            self._load_image_into(self.selected_idx)

    def _clear_cell_image(self):
        if self.selected_idx is not None:
            self.cells[self.selected_idx].image = None
            self._update_cell_panel()
            self._render_preview()
            self._update_fill_info()

    def _update_fill_info(self):
        filled = sum(1 for c in self.cells if c.image is not None)
        self.info_lbl.config(text=f"{filled} / {len(self.cells)} cells filled")

    # =========================================================================
    # CELL OPTIONS PANEL
    # =========================================================================

    def _update_cell_panel(self):
        """Show or hide the cell options panel based on current selection."""
        if self.selected_idx is not None and self.selected_idx < len(self.cells):
            cell = self.cells[self.selected_idx]
            self.lbl_hint.pack_forget()
            # Show the scrollable container (it holds opts_canvas + scrollbars)
            self._opts_scroll_container.pack(fill=tk.BOTH, expand=True)
            self.fit_var.set(cell.fit)
            self.rot_var.set(str(cell.rotation))
            self.flip_h_var.set(cell.flip_h)
            self.flip_v_var.set(cell.flip_v)
            self.pan_y_var.set(cell.pan_y)
            self.pan_x_var.set(cell.pan_x)
            self._update_pan_labels()
        else:
            self._opts_scroll_container.pack_forget()
            self.lbl_hint.pack(pady=16)

    def _on_cell_opt_changed(self):
        if self.selected_idx is None or self.selected_idx >= len(self.cells):
            return
        cell = self.cells[self.selected_idx]
        cell.fit = self.fit_var.get()
        cell.rotation = int(self.rot_var.get())
        cell.flip_h = self.flip_h_var.get()
        cell.flip_v = self.flip_v_var.get()
        cell.pan_y = float(self.pan_y_var.get())
        cell.pan_x = float(self.pan_x_var.get())
        self._update_pan_labels()
        self._render_preview()

    def _on_pan_slider_changed(self, val):
        self._on_cell_opt_changed()

    def _set_cell_pan_y(self, val):
        self.pan_y_var.set(val)
        self._on_cell_opt_changed()

    def _set_cell_pan_x(self, val):
        self.pan_x_var.set(val)
        self._on_cell_opt_changed()

    def _update_pan_labels(self):
        py = self.pan_y_var.get()
        px = self.pan_x_var.get()
        if py == 0.0:
            y_txt = "Top (0%)"
        elif py == 0.5:
            y_txt = "Center (50%)"
        elif py == 1.0:
            y_txt = "Bottom (100%)"
        else:
            y_txt = f"{int(py * 100)}%"

        if px == 0.0:
            x_txt = "Left (0%)"
        elif px == 0.5:
            x_txt = "Center (50%)"
        elif px == 1.0:
            x_txt = "Right (100%)"
        else:
            x_txt = f"{int(px * 100)}%"

        if hasattr(self, "pan_y_lbl"):
            self.pan_y_lbl.config(text=y_txt)
        if hasattr(self, "pan_x_lbl"):
            self.pan_x_lbl.config(text=x_txt)

    # =========================================================================
    # BACKGROUND & GAP
    # =========================================================================

    def _pick_bg_color(self):
        result = colorchooser.askcolor(
            initialcolor=self.bg_color_val,
            title="Choose Collage Background Color",
            parent=self,
        )
        if result[1]:
            self.bg_color_val = result[1]
            self.bg_swatch.config(bg=result[1])
            self._render_preview()

    def _on_gap_change(self, val):
        self.gap_label.config(text=f"{int(float(val))} px")
        self._render_preview()

    # =========================================================================
    # OUTPUT
    # =========================================================================

    def _build_output_image(self):
        """Render and return the final full-resolution collage PIL Image."""
        ow, oh = self._safe_out_dims()
        gap = self.gap_var.get()
        bg_rgba = self._hex_to_rgba(self.bg_color_val)
        out = Image.new("RGBA", (ow, oh), bg_rgba)
        for cell in self.cells:
            cell.render_into(out, ow, oh, gap)
        return out

    def _add_to_editor(self):
        """Render the final collage and return it to the main canvas editor."""
        img = self._build_output_image()
        if img is None:
            return
        result = img.convert("RGB")
        self.destroy()
        if self.result_callback:
            self.result_callback(result)

    def _save_as(self):
        """Export the collage directly to a file chosen by the user."""
        img = self._build_output_image()
        if img is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save Collage As",
            defaultextension=".png",
            filetypes=[
                ("PNG Image", "*.png"),
                ("JPEG Image", "*.jpg;*.jpeg"),
                ("BMP Image", "*.bmp"),
            ],
        )
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext in (".jpg", ".jpeg", ".bmp"):
                img.convert("RGB").save(path)
            else:
                img.save(path, "PNG")
            messagebox.showinfo("Saved", f"Collage saved to:\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save collage:\n{e}", parent=self)

    # =========================================================================
    # UTILITIES
    # =========================================================================

    @staticmethod
    def _hex_to_rgba(hex_color):
        """Convert #RRGGBB string to (R, G, B, A) tuple."""
        h = hex_color.lstrip("#")
        if len(h) == 6:
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255
        return 240, 240, 240, 255
