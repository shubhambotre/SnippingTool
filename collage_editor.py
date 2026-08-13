import os
from PIL import Image, ImageDraw, ImageOps
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QPainter, QColor, QPixmap, QImage, QFont, QPen, QBrush
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QSlider, QFileDialog, QMessageBox, QFrame, QScrollArea, QWidget
)

def pil_to_qpixmap(pil_img):
    """Converts a PIL RGBA Image to a PySide6 QPixmap."""
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    data = pil_img.tobytes("raw", "RGBA")
    qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


TEMPLATES = {
    "2 x 1": [(0.0, 0.0, 0.5, 1.0), (0.5, 0.0, 0.5, 1.0)],
    "1 x 2": [(0.0, 0.0, 1.0, 0.5), (0.0, 0.5, 1.0, 0.5)],
    "2 x 2": [
        (0.0, 0.0, 0.5, 0.5), (0.5, 0.0, 0.5, 0.5),
        (0.0, 0.5, 0.5, 0.5), (0.5, 0.5, 0.5, 0.5),
    ],
    "3 x 1": [(i / 3.0, 0.0, 1 / 3.0, 1.0) for i in range(3)],
    "1 x 3": [(0.0, i / 3.0, 1.0, 1 / 3.0) for i in range(3)],
    "3 x 2": [(j / 3.0, i / 2.0, 1 / 3.0, 0.5) for i in range(2) for j in range(3)],
    "2 x 3": [(j / 2.0, i / 3.0, 0.5, 1 / 3.0) for i in range(3) for j in range(2)],
}

DEFAULT_OUT_W = 1920
DEFAULT_OUT_H = 1080


class CollageCell:
    def __init__(self, nx, ny, nw, nh):
        self.nx = float(nx)
        self.ny = float(ny)
        self.nw = float(nw)
        self.nh = float(nh)
        self.image = None
        self.fit = "cover"

    def pixel_rect(self, out_w, out_h, gap):
        half = gap // 2
        x1 = round(self.nx * out_w) + half
        y1 = round(self.ny * out_h) + half
        x2 = round((self.nx + self.nw) * out_w) - half
        y2 = round((self.ny + self.nh) * out_h) - half
        return x1, y1, max(x1 + 1, x2), max(y1 + 1, y2)

    def render_into(self, canvas_img, out_w, out_h, gap):
        x1, y1, x2, y2 = self.pixel_rect(out_w, out_h, gap)
        cw, ch = x2 - x1, y2 - y1
        if cw <= 0 or ch <= 0:
            return

        if self.image is None:
            placeholder = Image.new("RGBA", (cw, ch), (185, 190, 200, 255))
            d = ImageDraw.Draw(placeholder)
            d.line([(0, 0), (cw - 1, ch - 1)], fill=(160, 165, 175, 200), width=2)
            d.line([(cw - 1, 0), (0, ch - 1)], fill=(160, 165, 175, 200), width=2)
            d.rectangle([0, 0, cw - 1, ch - 1], outline=(140, 145, 155), width=2)
            canvas_img.paste(placeholder, (x1, y1), placeholder)
            return

        img = self.image.convert("RGBA")
        iw, ih = img.size
        if iw == 0 or ih == 0:
            return

        if self.fit == "stretch":
            img = img.resize((cw, ch), Image.LANCZOS)
        elif self.fit == "contain":
            scale = min(cw / iw, ch / ih)
            nw_i, nh_i = max(1, int(iw * scale)), max(1, int(ih * scale))
            img = img.resize((nw_i, nh_i), Image.LANCZOS)
            bg_tile = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            bg_tile.paste(img, ((cw - nw_i) // 2, (ch - nh_i) // 2))
            img = bg_tile
        else:  # cover
            scale = max(cw / iw, ch / ih)
            nw_i, nh_i = max(1, int(iw * scale)), max(1, int(ih * scale))
            img = img.resize((nw_i, nh_i), Image.LANCZOS)
            crop_x, crop_y = (nw_i - cw) // 2, (nh_i - ch) // 2
            img = img.crop((crop_x, crop_y, crop_x + cw, crop_y + ch))

        canvas_img.paste(img, (x1, y1), img)


class CollageEditorDialog(QDialog):
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

        self.resize(1000, 680)
        self.setup_ui()
        self.apply_template(self.current_template)

        if self.initial_image and self.cells:
            self.cells[0].image = self.initial_image
            self.update_preview()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Top Control Bar
        top_bar = QHBoxLayout()

        top_bar.addWidget(QLabel("Template:"))
        self.cb_template = QComboBox()
        self.cb_template.addItems(list(TEMPLATES.keys()))
        self.cb_template.currentTextChanged.connect(self.apply_template)
        top_bar.addWidget(self.cb_template)

        top_bar.addWidget(QLabel("Gap:"))
        self.slider_gap = QSlider(Qt.Orientation.Horizontal)
        self.slider_gap.setRange(0, 32)
        self.slider_gap.setValue(self.gap_val)
        self.slider_gap.valueChanged.connect(self.on_gap_changed)
        top_bar.addWidget(self.slider_gap)

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

        main_layout.addLayout(top_bar)

        # Center Preview Label
        self.lbl_preview = QLabel()
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setStyleSheet("background-color: #121212; border: 1px solid #333333;")
        self.lbl_preview.mousePressEvent = self.on_preview_clicked
        main_layout.addWidget(self.lbl_preview, 1)

        # Bottom Action Bar
        bottom_bar = QHBoxLayout()

        btn_add = QPushButton("📷 Load Image into Slot")
        btn_add.clicked.connect(self.load_image_into_selected)
        bottom_bar.addWidget(btn_add)

        btn_apply = QPushButton("✓ Add Collage to Workspace Editor")
        btn_apply.setStyleSheet("background-color: #005FB8; color: white; font-weight: bold; padding: 6px 14px;")
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

        self.update_preview()

    def on_gap_changed(self, val):
        self.gap_val = val
        self.update_preview()

    def on_size_changed(self):
        self.out_w_val = self.spin_w.value()
        self.out_h_val = self.spin_h.value()
        self.update_preview()

    def render_composite(self):
        w, h = self.out_w_val, self.out_h_val
        canvas = Image.new("RGBA", (w, h), QColor(self.bg_color_val).getRgb())
        for cell in self.cells:
            cell.render_into(canvas, w, h, self.gap_val)
        return canvas

    def update_preview(self):
        canvas = self.render_composite()
        pixmap = pil_to_qpixmap(canvas)

        # Scale preview to fit container
        avail_w = max(400, self.lbl_preview.width() - 10)
        avail_h = max(300, self.lbl_preview.height() - 10)
        scaled_pixmap = pixmap.scaled(QSize(avail_w, avail_h), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.lbl_preview.setPixmap(scaled_pixmap)

    def on_preview_clicked(self, event):
        if not self.cells or not self.lbl_preview.pixmap():
            self.load_image_into_selected(None)
            return

        pos = event.position().toPoint()
        pm = self.lbl_preview.pixmap()
        lbl_w, lbl_h = self.lbl_preview.width(), self.lbl_preview.height()
        pm_w, pm_h = pm.width(), pm.height()

        off_x = (lbl_w - pm_w) // 2
        off_y = (lbl_h - pm_h) // 2

        rel_x = pos.x() - off_x
        rel_y = pos.y() - off_y

        target_cell = None
        if 0 <= rel_x <= pm_w and 0 <= rel_y <= pm_h:
            nx = rel_x / float(pm_w)
            ny = rel_y / float(pm_h)
            for c in self.cells:
                if c.nx <= nx <= c.nx + c.nw and c.ny <= ny <= c.ny + c.nh:
                    target_cell = c
                    break

        self.load_image_into_selected(target_cell)

    def load_image_into_selected(self, target_cell=None):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Image for Collage Slot", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            try:
                img = Image.open(file_path).convert("RGBA")
                if not target_cell:
                    for c in self.cells:
                        if c.image is None:
                            target_cell = c
                            break
                    if not target_cell and self.cells:
                        target_cell = self.cells[0]

                if target_cell:
                    target_cell.image = img
                    self.update_preview()
            except Exception as e:
                QMessageBox.critical(self, "Image Error", f"Could not load image:\n{e}")

    def export_to_editor(self):
        canvas = self.render_composite()
        if self.result_callback:
            self.result_callback(canvas)
        self.accept()
