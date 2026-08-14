import os
import time
from PIL import Image, ImageDraw, ImageOps, ImageFont
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QPainter, QColor, QPixmap, QImage, QFont, QPen, QBrush
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QSlider, QFileDialog, QMessageBox, QFrame, QScrollArea, QWidget,
    QCheckBox, QRadioButton, QButtonGroup, QColorDialog, QGroupBox, QSplitter
)

from capture import CaptureOverlay

def pil_to_qpixmap(pil_img):
    """Converts a PIL RGBA Image to a PySide6 QPixmap."""
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    data = pil_img.tobytes("raw", "RGBA")
    qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


# ---------------------------------------------------------------------------
# Layout templates — normalized cell bounding boxes (nx, ny, nw, nh)
# ---------------------------------------------------------------------------
TEMPLATES = {
    "2 x 1":    [(0.0, 0.0, 0.5, 1.0), (0.5, 0.0, 0.5, 1.0)],
    "1 x 2":    [(0.0, 0.0, 1.0, 0.5), (0.0, 0.5, 1.0, 0.5)],
    "2 x 2":    [
        (0.0, 0.0, 0.5, 0.5), (0.5, 0.0, 0.5, 0.5),
        (0.0, 0.5, 0.5, 0.5), (0.5, 0.5, 0.5, 0.5),
    ],
    "3 x 1":    [(i / 3.0, 0.0, 1 / 3.0, 1.0) for i in range(3)],
    "1 x 3":    [(0.0, i / 3.0, 1.0, 1 / 3.0) for i in range(3)],
    "3 x 2":    [(j / 3.0, i / 2.0, 1 / 3.0, 0.5) for i in range(2) for j in range(3)],
    "2 x 3":    [(j / 2.0, i / 3.0, 0.5, 1 / 3.0) for i in range(3) for j in range(2)],
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


class CollageCell:
    """Holds the transformation and image state for one cell slot in the collage."""

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
        self.pan_y = 0.0           # 0.0 (Top) to 1.0 (Bottom), default 0.0 (Top)

    def pixel_rect(self, out_w, out_h, gap):
        """Compute inset pixel rect (x1, y1, x2, y2) for this cell."""
        half = gap // 2
        x1 = round(self.nx * out_w) + half
        y1 = round(self.ny * out_h) + half
        x2 = round((self.nx + self.nw) * out_w) - half
        y2 = round((self.ny + self.nh) * out_h) - half
        return x1, y1, max(x1 + 1, x2), max(y1 + 1, y2)

    def render_into(self, canvas_img, out_w, out_h, gap, is_selected=False):
        """Paste cell contents into canvas_img at the computed position."""
        x1, y1, x2, y2 = self.pixel_rect(out_w, out_h, gap)
        cw, ch = x2 - x1, y2 - y1
        if cw <= 0 or ch <= 0:
            return

        if self.image is None:
            # Draw placeholder tile with diagonal lines, plus icon, and text hint
            placeholder = Image.new("RGBA", (cw, ch), (185, 190, 200, 255))
            d = ImageDraw.Draw(placeholder)
            d.line([(0, 0), (cw - 1, ch - 1)], fill=(160, 165, 175, 200), width=2)
            d.line([(cw - 1, 0), (0, ch - 1)], fill=(160, 165, 175, 200), width=2)
            d.rectangle([0, 0, cw - 1, ch - 1], outline=(140, 145, 155), width=2)

            icon_r = min(cw // 2, ch // 2, 24)
            cx_i, cy_i = cw // 2, ch // 2
            d.line([(cx_i - icon_r, cy_i), (cx_i + icon_r, cy_i)], fill=(80, 85, 100), width=3)
            d.line([(cx_i, cy_i - icon_r), (cx_i, cy_i + icon_r)], fill=(80, 85, 100), width=3)

            if cw > 100 and ch > 50:
                try:
                    fnt_path = os.path.join("C:\\Windows\\Fonts", "segoeui.ttf")
                    fnt = ImageFont.truetype(fnt_path, 13) if os.path.exists(fnt_path) else ImageFont.load_default()
                    label = "Click slot to add image"
                    bbox = d.textbbox((0, 0), label, font=fnt)
                    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    d.text((cx_i - tw // 2, cy_i + icon_r + 6), label, fill=(80, 85, 100), font=fnt)
                except Exception:
                    pass

            if is_selected:
                d.rectangle([0, 0, cw - 1, ch - 1], outline=(0, 229, 255), width=4)

            canvas_img.paste(placeholder, (x1, y1), placeholder)
            return

        # Prepare transformed copy of cell image
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

        if is_selected:
            d_sel = ImageDraw.Draw(canvas_img)
            d_sel.rectangle([x1, y1, x2 - 1, y2 - 1], outline=(0, 229, 255), width=4)


class CollageEditorDialog(QDialog):
    """Full PySide6 Photo Collage Editor Dialog with interactive cell customization."""

    def __init__(self, parent, theme_colors, initial_image=None, result_callback=None, root_window=None):
        super().__init__(parent)
        self.setWindowTitle("Photo Collage Editor")
        self.tc = theme_colors
        self.initial_image = initial_image
        self.result_callback = result_callback

        self.current_template = "1 x 2"
        self.gap_val = 8
        self.out_w_val = DEFAULT_OUT_W
        self.out_h_val = DEFAULT_OUT_H
        self.bg_color_val = "#18191A" if self.tc.get("theme_name") == "dark" else "#EFEFEF"

        self.cells = []
        self.selected_idx = None

        self.resize(1120, 720)
        self.setup_ui()
        self.apply_template(self.current_template)

        if self.initial_image and self.cells:
            self.cells[0].image = self.initial_image.copy()
            self.selected_idx = 0
            self.update_cell_panel()
            self.update_preview()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # -------------------------------------------------------------------
        # TOP CONFIGURATION BAR
        # -------------------------------------------------------------------
        top_bar = QHBoxLayout()

        top_bar.addWidget(QLabel("Template:"))
        self.cb_template = QComboBox()
        self.cb_template.addItems(list(TEMPLATES.keys()))
        self.cb_template.currentTextChanged.connect(self.apply_template)
        top_bar.addWidget(self.cb_template)

        top_bar.addWidget(QLabel("Gap:"))
        self.lbl_gap_val = QLabel(f"{self.gap_val} px")
        self.lbl_gap_val.setFixedWidth(40)
        self.slider_gap = QSlider(Qt.Orientation.Horizontal)
        self.slider_gap.setRange(0, 32)
        self.slider_gap.setValue(self.gap_val)
        self.slider_gap.valueChanged.connect(self.on_gap_changed)
        top_bar.addWidget(self.slider_gap)
        top_bar.addWidget(self.lbl_gap_val)

        top_bar.addWidget(QLabel("Width:"))
        self.spin_w = QSpinBox()
        self.spin_w.setRange(400, 3840)
        self.spin_w.setValue(self.out_w_val)
        self.spin_w.valueChanged.connect(self.on_size_changed)
        top_bar.addWidget(self.spin_w)

        top_bar.addWidget(QLabel("Height:"))
        self.spin_h = QSpinBox()
        self.spin_h.setRange(300, 2160)
        self.spin_h.setValue(self.out_h_val)
        self.spin_h.valueChanged.connect(self.on_size_changed)
        top_bar.addWidget(self.spin_h)

        top_bar.addWidget(QLabel("BG Color:"))
        self.btn_bg_color = QPushButton()
        self.btn_bg_color.setFixedSize(28, 24)
        self.btn_bg_color.setStyleSheet(f"background-color: {self.bg_color_val}; border: 1px solid #777777; border-radius: 4px;")
        self.btn_bg_color.clicked.connect(self.choose_bg_color)
        top_bar.addWidget(self.btn_bg_color)

        self.lbl_fill_info = QLabel("0 / 0 filled")
        self.lbl_fill_info.setStyleSheet("font-weight: bold; color: #00E5FF;")
        top_bar.addStretch()
        top_bar.addWidget(self.lbl_fill_info)

        main_layout.addLayout(top_bar)

        # -------------------------------------------------------------------
        # CENTER WORKSPACE (Preview + Cell Options Splitter)
        # -------------------------------------------------------------------
        workspace_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Interactive Preview Canvas Label
        self.lbl_preview = QLabel()
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setStyleSheet("background-color: #121212; border: 1px solid #333333; border-radius: 6px;")
        self.lbl_preview.mousePressEvent = self.on_preview_clicked
        workspace_splitter.addWidget(self.lbl_preview)

        # Right: Selected Cell Customization Side Panel
        self.panel_cell_opts = QGroupBox("Selected Cell Properties")
        self.panel_cell_opts.setFixedWidth(300)
        cell_layout = QVBoxLayout(self.panel_cell_opts)

        self.lbl_cell_hint = QLabel("Select a cell slot in the preview canvas to edit image positioning, rotation, mirror, or capture a screen area.")
        self.lbl_cell_hint.setWordWrap(True)
        self.lbl_cell_hint.setStyleSheet("color: #888888; font-style: italic;")
        cell_layout.addWidget(self.lbl_cell_hint)

        self.opts_container = QWidget()
        opts_layout = QVBoxLayout(self.opts_container)
        opts_layout.setContentsMargins(0, 0, 0, 0)
        opts_layout.setSpacing(10)

        # 1. Slot Image Actions
        act_box = QGroupBox("Image Source")
        act_layout = QVBoxLayout(act_box)
        
        btn_load = QPushButton("📁 Load File into Slot")
        btn_load.clicked.connect(self.load_image_for_selected)
        act_layout.addWidget(btn_load)

        btn_snip = QPushButton("✂️ Snip Screen Region into Slot")
        btn_snip.clicked.connect(self.snip_into_selected)
        act_layout.addWidget(btn_snip)

        h_act = QHBoxLayout()
        btn_replace = QPushButton("🔄 Replace")
        btn_replace.clicked.connect(self.load_image_for_selected)
        h_act.addWidget(btn_replace)

        btn_clear = QPushButton("🗑️ Clear Slot")
        btn_clear.clicked.connect(self.clear_selected_slot)
        h_act.addWidget(btn_clear)
        act_layout.addLayout(h_act)

        opts_layout.addWidget(act_box)

        # 2. Fit Mode & Orientation
        orient_box = QGroupBox("Fit & Orientation")
        orient_layout = QVBoxLayout(orient_box)

        fit_layout = QHBoxLayout()
        fit_layout.addWidget(QLabel("Fit Mode:"))
        self.cb_fit = QComboBox()
        self.cb_fit.addItems(["cover", "contain", "stretch"])
        self.cb_fit.currentTextChanged.connect(self.on_cell_property_changed)
        fit_layout.addWidget(self.cb_fit)
        orient_layout.addLayout(fit_layout)

        rot_layout = QHBoxLayout()
        rot_layout.addWidget(QLabel("Rotation:"))
        self.cb_rot = QComboBox()
        self.cb_rot.addItems(["0°", "90°", "180°", "270°"])
        self.cb_rot.currentTextChanged.connect(self.on_cell_property_changed)
        rot_layout.addWidget(self.cb_rot)
        orient_layout.addLayout(rot_layout)

        self.chk_flip_h = QCheckBox("Flip Horizontal (Mirror)")
        self.chk_flip_h.stateChanged.connect(self.on_cell_property_changed)
        orient_layout.addWidget(self.chk_flip_h)

        self.chk_flip_v = QCheckBox("Flip Vertical")
        self.chk_flip_v.stateChanged.connect(self.on_cell_property_changed)
        orient_layout.addWidget(self.chk_flip_v)

        opts_layout.addWidget(orient_box)

        # 3. Panning & Positioning Sliders
        pan_box = QGroupBox("Image Panning / Alignment")
        pan_layout = QVBoxLayout(pan_box)

        # Pan X
        pan_x_hdr = QHBoxLayout()
        pan_x_hdr.addWidget(QLabel("Pan X:"))
        self.lbl_pan_x_val = QLabel("Center (50%)")
        self.lbl_pan_x_val.setStyleSheet("font-weight: bold;")
        pan_x_hdr.addWidget(self.lbl_pan_x_val)
        pan_layout.addLayout(pan_x_hdr)

        self.slider_pan_x = QSlider(Qt.Orientation.Horizontal)
        self.slider_pan_x.setRange(0, 100)
        self.slider_pan_x.setValue(50)
        self.slider_pan_x.valueChanged.connect(self.on_cell_property_changed)
        pan_layout.addWidget(self.slider_pan_x)

        # Quick X Presets
        x_presets = QHBoxLayout()
        btn_px_l = QPushButton("Left")
        btn_px_l.clicked.connect(lambda: self.slider_pan_x.setValue(0))
        x_presets.addWidget(btn_px_l)
        btn_px_c = QPushButton("Center")
        btn_px_c.clicked.connect(lambda: self.slider_pan_x.setValue(50))
        x_presets.addWidget(btn_px_c)
        btn_px_r = QPushButton("Right")
        btn_px_r.clicked.connect(lambda: self.slider_pan_x.setValue(100))
        x_presets.addWidget(btn_px_r)
        pan_layout.addLayout(x_presets)

        # Pan Y
        pan_y_hdr = QHBoxLayout()
        pan_y_hdr.addWidget(QLabel("Pan Y:"))
        self.lbl_pan_y_val = QLabel("Top (0%)")
        self.lbl_pan_y_val.setStyleSheet("font-weight: bold;")
        pan_y_hdr.addWidget(self.lbl_pan_y_val)
        pan_layout.addLayout(pan_y_hdr)

        self.slider_pan_y = QSlider(Qt.Orientation.Horizontal)
        self.slider_pan_y.setRange(0, 100)
        self.slider_pan_y.setValue(0)
        self.slider_pan_y.valueChanged.connect(self.on_cell_property_changed)
        pan_layout.addWidget(self.slider_pan_y)

        # Quick Y Presets
        y_presets = QHBoxLayout()
        btn_py_t = QPushButton("Top")
        btn_py_t.clicked.connect(lambda: self.slider_pan_y.setValue(0))
        y_presets.addWidget(btn_py_t)
        btn_py_c = QPushButton("Center")
        btn_py_c.clicked.connect(lambda: self.slider_pan_y.setValue(50))
        y_presets.addWidget(btn_py_c)
        btn_py_b = QPushButton("Bottom")
        btn_py_b.clicked.connect(lambda: self.slider_pan_y.setValue(100))
        y_presets.addWidget(btn_py_b)
        pan_layout.addLayout(y_presets)

        opts_layout.addWidget(pan_box)
        cell_layout.addWidget(self.opts_container)
        self.opts_container.hide()

        workspace_splitter.addWidget(self.panel_cell_opts)
        workspace_splitter.setStretchFactor(0, 3)
        workspace_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(workspace_splitter, 1)

        # -------------------------------------------------------------------
        # BOTTOM ACTION BAR
        # -------------------------------------------------------------------
        bottom_bar = QHBoxLayout()

        btn_save_as = QPushButton("💾 Export Collage File...")
        btn_save_as.clicked.connect(self.save_as_file)
        bottom_bar.addWidget(btn_save_as)

        bottom_bar.addStretch()

        btn_apply = QPushButton("✓ Add Collage to Workspace Editor")
        btn_apply.setStyleSheet("background-color: #005FB8; color: white; font-weight: bold; padding: 6px 16px;")
        btn_apply.clicked.connect(self.export_to_editor)
        bottom_bar.addWidget(btn_apply)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        bottom_bar.addWidget(btn_cancel)

        main_layout.addLayout(bottom_bar)

    def apply_template(self, name):
        self.current_template = name
        rects = TEMPLATES.get(name, TEMPLATES["1 x 2"])
        old_imgs = [c.image for c in self.cells]

        self.cells = [CollageCell(nx, ny, nw, nh) for nx, ny, nw, nh in rects]
        for i, img in enumerate(old_imgs):
            if i < len(self.cells):
                self.cells[i].image = img

        if self.selected_idx is not None and self.selected_idx >= len(self.cells):
            self.selected_idx = 0 if self.cells else None

        self.update_cell_panel()
        self.update_preview()

    def choose_bg_color(self):
        col = QColorDialog.getColor(QColor(self.bg_color_val), self, "Choose Background Color")
        if col.isValid():
            self.bg_color_val = col.name()
            self.btn_bg_color.setStyleSheet(f"background-color: {self.bg_color_val}; border: 1px solid #777777; border-radius: 4px;")
            self.update_preview()

    def on_gap_changed(self, val):
        self.gap_val = val
        self.lbl_gap_val.setText(f"{val} px")
        self.update_preview()

    def on_size_changed(self):
        self.out_w_val = self.spin_w.value()
        self.out_h_val = self.spin_h.value()
        self.update_preview()

    def render_composite(self):
        w, h = self.out_w_val, self.out_h_val
        canvas = Image.new("RGBA", (w, h), QColor(self.bg_color_val).getRgb())
        for idx, cell in enumerate(self.cells):
            is_sel = (idx == self.selected_idx)
            cell.render_into(canvas, w, h, self.gap_val, is_selected=is_sel)
        return canvas

    def update_preview(self):
        canvas = self.render_composite()
        pixmap = pil_to_qpixmap(canvas)

        avail_w = max(300, self.lbl_preview.width() - 10)
        avail_h = max(200, self.lbl_preview.height() - 10)
        scaled_pixmap = pixmap.scaled(QSize(avail_w, avail_h), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.lbl_preview.setPixmap(scaled_pixmap)

        filled = sum(1 for c in self.cells if c.image is not None)
        self.lbl_fill_info.setText(f"{filled} / {len(self.cells)} filled")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_preview()

    def on_preview_clicked(self, event):
        if not self.cells or not self.lbl_preview.pixmap():
            return

        pos = event.position().toPoint()
        pm = self.lbl_preview.pixmap()
        lbl_w, lbl_h = self.lbl_preview.width(), self.lbl_preview.height()
        pm_w, pm_h = pm.width(), pm.height()

        off_x = (lbl_w - pm_w) // 2
        off_y = (lbl_h - pm_h) // 2

        rel_x = pos.x() - off_x
        rel_y = pos.y() - off_y

        if 0 <= rel_x <= pm_w and 0 <= rel_y <= pm_h:
            nx = rel_x / float(pm_w)
            ny = rel_y / float(pm_h)
            found = False
            for idx, c in enumerate(self.cells):
                if c.nx <= nx <= c.nx + c.nw and c.ny <= ny <= c.ny + c.nh:
                    self.selected_idx = idx
                    found = True
                    break
            if not found:
                self.selected_idx = None
        else:
            self.selected_idx = None

        self.update_cell_panel()
        self.update_preview()

    def update_cell_panel(self):
        if self.selected_idx is not None and self.selected_idx < len(self.cells):
            cell = self.cells[self.selected_idx]
            self.lbl_cell_hint.hide()
            self.opts_container.show()

            self.cb_fit.blockSignals(True)
            self.cb_rot.blockSignals(True)
            self.chk_flip_h.blockSignals(True)
            self.chk_flip_v.blockSignals(True)
            self.slider_pan_x.blockSignals(True)
            self.slider_pan_y.blockSignals(True)

            self.cb_fit.setCurrentText(cell.fit)
            self.cb_rot.setCurrentText(f"{cell.rotation}°")
            self.chk_flip_h.setChecked(cell.flip_h)
            self.chk_flip_v.setChecked(cell.flip_v)
            self.slider_pan_x.setValue(int(cell.pan_x * 100))
            self.slider_pan_y.setValue(int(cell.pan_y * 100))

            self.cb_fit.blockSignals(False)
            self.cb_rot.blockSignals(False)
            self.chk_flip_h.blockSignals(False)
            self.chk_flip_v.blockSignals(False)
            self.slider_pan_x.blockSignals(False)
            self.slider_pan_y.blockSignals(False)

            self.update_pan_readout_labels()
        else:
            self.opts_container.hide()
            self.lbl_cell_hint.show()

    def on_cell_property_changed(self):
        if self.selected_idx is None or self.selected_idx >= len(self.cells):
            return

        cell = self.cells[self.selected_idx]
        cell.fit = self.cb_fit.currentText()
        rot_str = self.cb_rot.currentText().replace("°", "")
        cell.rotation = int(rot_str)
        cell.flip_h = self.chk_flip_h.isChecked()
        cell.flip_v = self.chk_flip_v.isChecked()
        cell.pan_x = self.slider_pan_x.value() / 100.0
        cell.pan_y = self.slider_pan_y.value() / 100.0

        self.update_pan_readout_labels()
        self.update_preview()

    def update_pan_readout_labels(self):
        px = self.slider_pan_x.value()
        py = self.slider_pan_y.value()

        if px == 0:
            self.lbl_pan_x_val.setText("Left (0%)")
        elif px == 50:
            self.lbl_pan_x_val.setText("Center (50%)")
        elif px == 100:
            self.lbl_pan_x_val.setText("Right (100%)")
        else:
            self.lbl_pan_x_val.setText(f"{px}%")

        if py == 0:
            self.lbl_pan_y_val.setText("Top (0%)")
        elif py == 50:
            self.lbl_pan_y_val.setText("Center (50%)")
        elif py == 100:
            self.lbl_pan_y_val.setText("Bottom (100%)")
        else:
            self.lbl_pan_y_val.setText(f"{py}%")

    def load_image_for_selected(self):
        target_idx = self.selected_idx
        if target_idx is None:
            # Pick first empty cell or cell 0
            for i, c in enumerate(self.cells):
                if c.image is None:
                    target_idx = i
                    break
            if target_idx is None and self.cells:
                target_idx = 0

        if target_idx is None:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, f"Add Image to Cell {target_idx + 1}", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.tiff);;All Files (*.*)"
        )

        if file_path:
            try:
                img = Image.open(file_path).convert("RGBA")
                self.cells[target_idx].image = img
                self.selected_idx = target_idx
                self.update_cell_panel()
                self.update_preview()
            except Exception as e:
                QMessageBox.critical(self, "Image Error", f"Could not open image:\n{e}")

    def snip_into_selected(self):
        """Hides the dialog, runs screen capture overlay, then pastes captured snip into slot."""
        target_idx = self.selected_idx if self.selected_idx is not None else 0
        if target_idx >= len(self.cells):
            return

        self.hide()
        if self.parent():
            self.parent().hide()

        def on_snip_done(pil_image):
            if self.parent():
                self.parent().show()
            self.show()
            self.activateWindow()
            self.raise_()

            if pil_image:
                self.cells[target_idx].image = pil_image.convert("RGBA")
                self.selected_idx = target_idx
                self.update_cell_panel()
                self.update_preview()

        # Launch CaptureOverlay
        self.overlay = CaptureOverlay(self.parent(), mode="free", callback=on_snip_done)

    def clear_selected_slot(self):
        if self.selected_idx is not None and self.selected_idx < len(self.cells):
            self.cells[self.selected_idx].image = None
            self.update_cell_panel()
            self.update_preview()

    def export_to_editor(self):
        canvas = self.render_composite()
        if self.result_callback:
            self.result_callback(canvas)
        self.accept()

    def save_as_file(self):
        canvas = self.render_composite()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Collage As",
            os.path.join(os.path.expanduser("~"), "Pictures", f"Collage_{time.strftime('%Y%m%d_%H%M%S')}.png"),
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;BMP Image (*.bmp)"
        )

        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            try:
                if ext in (".jpg", ".jpeg"):
                    canvas.convert("RGB").save(file_path, "JPEG")
                elif ext == ".bmp":
                    canvas.convert("RGB").save(file_path, "BMP")
                else:
                    canvas.save(file_path, "PNG")
                QMessageBox.information(self, "Collage Saved", f"Saved collage to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save collage:\n{e}")
