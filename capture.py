import sys
import time
import os
import ctypes
from PIL import Image, ImageGrab, ImageEnhance
from PySide6.QtCore import Qt, QRect, QPoint, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QPixmap, QImage, QCursor, QKeySequence, QBrush
from PySide6.QtWidgets import QWidget, QApplication, QMainWindow

def pil_to_qpixmap(pil_img):
    """Converts a PIL RGBA Image to a PySide6 QPixmap."""
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    data = pil_img.tobytes("raw", "RGBA")
    qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)

def qimage_to_pil(qimg):
    """Converts a PySide6 QImage to a PIL Image."""
    qimg = qimg.convertToFormat(QImage.Format.Format_RGBA8888)
    width = qimg.width()
    height = qimg.height()
    ptr = qimg.constBits()
    bpl = qimg.bytesPerLine()
    data = bytes(ptr)
    return Image.frombytes("RGBA", (width, height), data, "raw", "RGBA", bpl, 1)


class CaptureOverlay(QWidget):
    def __init__(self, main_window, mode="free", fixed_width=800, fixed_height=600, callback=None):
        super().__init__(None)
        self.main_window = main_window
        self.mode = mode
        self.fixed_width = fixed_width
        self.fixed_height = fixed_height
        self.callback = callback

        self.original_image = None
        self.darkened_image = None
        self.original_pixmap = None
        self.darkened_pixmap = None
        self.captured_image = None

        self.start_pos = None
        self.current_pos = None
        self.is_selecting = False

        self.hud_color = QColor("#00E5FF")
        self.hud_bg = QColor("#0E1013")

        # Hide main window completely and set opacity to 0.0 to prevent shadow artifacts
        if self.main_window:
            self.main_window.setWindowOpacity(0.0)
            self.main_window.hide()
        for _ in range(6):
            QApplication.processEvents()
            time.sleep(0.06)

        # Grab full desktop screenshot
        self.take_screenshot()

        # Configure window flags for frameless, topmost, fullscreen snip overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.BlankCursor)

        # Cover primary display geometry
        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
        elif self.original_pixmap:
            self.setGeometry(0, 0, self.original_pixmap.width(), self.original_pixmap.height())

        self.showFullScreen()
        self.activateWindow()
        self.raise_()
        self.setFocus()

    def take_screenshot(self):
        """Grabs full screen content using ImageGrab or Qt screen grab as fallback."""
        img = None
        try:
            img = ImageGrab.grab(all_screens=True)
        except Exception:
            try:
                img = ImageGrab.grab()
            except Exception:
                img = None

        if img:
            self.original_image = img
            self.original_pixmap = pil_to_qpixmap(self.original_image)
        else:
            pixmap = None
            try:
                screen = QApplication.primaryScreen()
                if screen:
                    pixmap = screen.grabWindow(0)
            except Exception:
                pixmap = None

            if pixmap and not pixmap.isNull():
                self.original_pixmap = pixmap
                self.original_image = qimage_to_pil(pixmap.toImage())
            else:
                # Emergency fallback: white canvas
                self.original_image = Image.new("RGBA", (1920, 1080), (255, 255, 255, 255))
                self.original_pixmap = pil_to_qpixmap(self.original_image)

        # Create darkened image for overlay background
        enhancer = ImageEnhance.Brightness(self.original_image)
        self.darkened_image = enhancer.enhance(0.4)
        self.darkened_pixmap = pil_to_qpixmap(self.darkened_image)

    def _get_scale_factors(self):
        sw = max(1, self.width())
        sh = max(1, self.height())
        scale_x = self.original_image.width / float(sw)
        scale_y = self.original_image.height / float(sh)
        return scale_x, scale_y

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Draw darkened full-screen background
        painter.drawPixmap(self.rect(), self.darkened_pixmap)

        mouse_pos = self.mapFromGlobal(QCursor.pos())
        cx, cy = mouse_pos.x(), mouse_pos.y()

        # Determine current selection bounding box
        crop_rect = None
        if self.mode == "fixed":
            w, h = self.fixed_width, self.fixed_height
            sw, sh = self.width(), self.height()
            x1 = max(0, min(cx - w // 2, sw - w))
            y1 = max(0, min(cy - h // 2, sh - h))
            crop_rect = QRect(x1, y1, w, h)
        elif self.start_pos and self.current_pos:
            x1 = min(self.start_pos.x(), self.current_pos.x())
            y1 = min(self.start_pos.y(), self.current_pos.y())
            x2 = max(self.start_pos.x(), self.current_pos.x())
            y2 = max(self.start_pos.y(), self.current_pos.y())
            crop_rect = QRect(x1, y1, max(1, x2 - x1), max(1, y2 - y1))

        # 2. Draw clear (un-darkened) original image section inside crop box
        if crop_rect and crop_rect.width() > 0 and crop_rect.height() > 0:
            scale_x, scale_y = self._get_scale_factors()
            src_x = int(round(crop_rect.x() * scale_x))
            src_y = int(round(crop_rect.y() * scale_y))
            src_w = int(round(crop_rect.width() * scale_x))
            src_h = int(round(crop_rect.height() * scale_y))
            src_rect = QRect(src_x, src_y, src_w, src_h)

            painter.drawPixmap(crop_rect, self.original_pixmap, src_rect)

            # Draw Crop HUD grid, border, and dimension tag
            self.draw_crop_hud(painter, crop_rect)

        # 3. Draw viewfinder crosshair and coordinate readout
        self.draw_hud_reticle(painter, cx, cy)

        # 4. Draw Top HUD Status Banner with Cancel button
        self.draw_top_bar(painter)

    def draw_hud_reticle(self, painter, cx, cy):
        """Draws viewfinder crosshair lines and coordinate pill near cursor."""
        pen = QPen(self.hud_color, 1.2)
        painter.setPen(pen)

        # Crosshair lines with center gap
        painter.drawLine(cx - 15, cy, cx - 4, cy)
        painter.drawLine(cx + 4, cy, cx + 15, cy)
        painter.drawLine(cx, cy - 15, cx, cy - 4)
        painter.drawLine(cx, cy + 4, cx, cy + 15)

        # Coordinate pill box
        coord_text = f"X:{cx:04d}\nY:{cy:04d}"
        font = QFont("Consolas", 8, QFont.Weight.Bold)
        painter.setFont(font)

        pill_rect = QRect(cx + 18, cy + 18, 56, 30)
        painter.setBrush(QBrush(self.hud_bg))
        painter.drawRoundedRect(pill_rect, 4, 4)
        painter.setPen(QPen(self.hud_color))
        painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, coord_text)

    def draw_crop_hud(self, painter, rect):
        """Draws dashed cyan border, rule-of-thirds grid, and dimension label."""
        x1, y1, w, h = rect.x(), rect.y(), rect.width(), rect.height()

        # Dashed border line
        border_pen = QPen(self.hud_color, 1.5, Qt.PenStyle.DashLine)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        # Rule of Thirds gridlines
        grid_pen = QPen(self.hud_color, 0.8, Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)

        dx = w / 3.0
        dy = h / 3.0
        painter.drawLine(int(round(x1 + dx)), y1, int(round(x1 + dx)), y1 + h)
        painter.drawLine(int(round(x1 + 2 * dx)), y1, int(round(x1 + 2 * dx)), y1 + h)
        painter.drawLine(x1, int(round(y1 + dy)), x1 + w, int(round(y1 + dy)))
        painter.drawLine(x1, int(round(y1 + 2 * dy)), x1 + w, int(round(y1 + 2 * dy)))

        # Dimension pill tag
        dim_text = f"{w} x {h} px"
        font = QFont("Consolas", 9, QFont.Weight.Bold)
        painter.setFont(font)

        tag_w = 110
        tag_h = 22
        tag_x = int(round(x1 + (w - tag_w) / 2.0))
        tag_y = y1 - 26 if y1 > 30 else y1 + h + 6

        tag_rect = QRect(tag_x, tag_y, tag_w, tag_h)
        painter.setPen(QPen(self.hud_color, 1))
        painter.setBrush(QBrush(self.hud_bg))
        painter.drawRoundedRect(tag_rect, 4, 4)

        painter.setPen(QPen(self.hud_color))
        painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, dim_text)

    def draw_top_bar(self, painter):
        """Draws top HUD banner with instructions and a clickable Cancel button."""
        screen_w = self.width()
        cx = screen_w // 2
        cy = 28

        pill_w = 480
        pill_h = 38
        x1 = cx - pill_w // 2
        y1 = cy - pill_h // 2

        container_rect = QRect(x1, y1, pill_w, pill_h)
        painter.setPen(QPen(self.hud_color, 1.5))
        painter.setBrush(QBrush(QColor("#0E1013")))
        painter.drawRoundedRect(container_rect, 6, 6)

        # Instructions text
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#FFFFFF")))
        text_rect = QRect(x1 + 16, y1, 350, pill_h)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "📷 CAPTURE MODE  •  Drag area to snip  •  Press ESC to exit")

        # Cancel button rect
        btn_w = 95
        btn_h = pill_h - 8
        btn_x = x1 + pill_w - btn_w - 6
        btn_y = y1 + 4
        self.cancel_btn_rect = QRect(btn_x, btn_y, btn_w, btn_h)

        mouse_pos = self.mapFromGlobal(QCursor.pos())
        is_hover = self.cancel_btn_rect.contains(mouse_pos)

        btn_bg = QColor("#B71C1C") if is_hover else QColor("#D32F2F")
        btn_border = QColor("#FFFFFF") if is_hover else QColor("#FF6B6B")

        painter.setPen(QPen(btn_border, 1))
        painter.setBrush(QBrush(btn_bg))
        painter.drawRoundedRect(self.cancel_btn_rect, 4, 4)

        painter.setPen(QPen(QColor("#FFFFFF")))
        painter.drawText(self.cancel_btn_rect, Qt.AlignmentFlag.AlignCenter, "✕ CANCEL")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()

            # Check if Cancel button in top HUD bar was clicked
            if hasattr(self, 'cancel_btn_rect') and self.cancel_btn_rect.contains(pos):
                self.cancel()
                return

            try:
                self.grabMouse()
            except Exception:
                pass

            if self.mode == "fixed":
                w, h = self.fixed_width, self.fixed_height
                sw, sh = self.width(), self.height()
                x1 = max(0, min(pos.x() - w // 2, sw - w))
                y1 = max(0, min(pos.y() - h // 2, sh - h))

                if self.original_image:
                    scale_x, scale_y = self._get_scale_factors()
                    ix1 = max(0, int(round(x1 * scale_x)))
                    iy1 = max(0, int(round(y1 * scale_y)))
                    iw = int(round(w * scale_x))
                    ih = int(round(h * scale_y))
                    ix2 = min(self.original_image.width, ix1 + iw)
                    iy2 = min(self.original_image.height, iy1 + ih)
                    self.captured_image = self.original_image.crop((ix1, iy1, ix2, iy2))

                self.close_overlay()
            else:
                self.start_pos = pos
                self.current_pos = pos
                self.is_selecting = True
                self.update()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()

        # Update cursor shape on Cancel button hover
        if hasattr(self, 'cancel_btn_rect') and self.cancel_btn_rect.contains(pos):
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.BlankCursor)

        if self.is_selecting:
            self.current_pos = pos

        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            try:
                self.releaseMouse()
            except Exception:
                pass

            if self.is_selecting:
                self.is_selecting = False
                if self.start_pos and self.current_pos and self.original_image:
                    x1 = min(self.start_pos.x(), self.current_pos.x())
                    y1 = min(self.start_pos.y(), self.current_pos.y())
                    x2 = max(self.start_pos.x(), self.current_pos.x())
                    y2 = max(self.start_pos.y(), self.current_pos.y())

                    scale_x, scale_y = self._get_scale_factors()
                    ix1 = max(0, int(round(x1 * scale_x)))
                    iy1 = max(0, int(round(y1 * scale_y)))
                    ix2 = min(self.original_image.width, int(round(x2 * scale_x)))
                    iy2 = min(self.original_image.height, int(round(y2 * scale_y)))

                    if (ix2 - ix1) > 2 and (iy2 - iy1) > 2:
                        self.captured_image = self.original_image.crop((ix1, iy1, ix2, iy2))

                self.close_overlay()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()

    def cancel(self):
        try:
            self.releaseMouse()
        except Exception:
            pass
        self.captured_image = None
        self.close_overlay()

    def close_overlay(self):
        try:
            self.releaseMouse()
        except Exception:
            pass
        self.close()
        if self.main_window:
            self.main_window.setWindowOpacity(1.0)
            self.main_window.show()
            self.main_window.activateWindow()
            self.main_window.raise_()

        if self.callback:
            self.callback(self.captured_image)

