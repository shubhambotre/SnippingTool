import math
import os
import copy
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QObject
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPixmap, QImage,
    QPainterPath, QTransform, QKeySequence, QFontMetrics
)
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsPathItem, QGraphicsRectItem, QGraphicsEllipseItem,
    QGraphicsTextItem, QGraphicsLineItem, QGraphicsItemGroup, QGraphicsItem
)

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


def make_arrow_path(start, end, head_len=14, angle_deg=25):
    """Generates a QPainterPath for a vector arrow with arrowhead polygon."""
    path = QPainterPath()
    path.moveTo(start)
    path.lineTo(end)

    dx = end.x() - start.x()
    dy = end.y() - start.y()
    length = math.hypot(dx, dy)
    if length > 2:
        angle = math.atan2(dy, dx)
        rad1 = angle + math.radians(180 - angle_deg)
        rad2 = angle - math.radians(180 - angle_deg)

        p1 = QPointF(end.x() + head_len * math.cos(rad1), end.y() + head_len * math.sin(rad1))
        p2 = QPointF(end.x() + head_len * math.cos(rad2), end.y() + head_len * math.sin(rad2))

        arrow_head = QPainterPath()
        arrow_head.moveTo(end)
        arrow_head.lineTo(p1)
        arrow_head.lineTo(p2)
        arrow_head.closeSubpath()
        path.addPath(arrow_head)

    return path


class CanvasEditor(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform |
            QPainter.RenderHint.TextAntialiasing
        )

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        # Image containers
        self.base_image = None
        self.bg_pixmap_item = None

        # State
        self.tool = "pencil"
        self.color = "#FF3B30"
        self.thickness = 3
        self.fill_mode = "hollow"
        self.font_size = 14
        self.font_family = "Arial"
        self.zoom_factor = 1.0

        # Drawing state
        self.start_point = None
        self.current_item = None
        self.pencil_path = None

        # Crop state
        self.crop_item = None
        self.is_cropping = False

        # Element history stack for Undo/Redo
        self.history = []
        self.redo_stack = []

        # Callbacks
        self.on_draw_callback = None
        self.cursor_callback = None
        self.on_crop_complete_callback = None
        self.on_tool_change_callback = None

        # Dark grid background
        self.setBackgroundBrush(QBrush(QColor("#1E1E1E")))

    def set_image(self, pil_image):
        """Loads a PIL image into the canvas scene."""
        self.base_image = pil_image.copy()
        self.scene.clear()
        self.history.clear()
        self.redo_stack.clear()
        self.zoom_factor = 1.0
        self.resetTransform()

        pixmap = pil_to_qpixmap(self.base_image)
        self.bg_pixmap_item = self.scene.addPixmap(pixmap)
        self.bg_pixmap_item.setZValue(-100)

        self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())

        if self.on_crop_complete_callback:
            self.on_crop_complete_callback(pixmap.width(), pixmap.height())

    def set_tool(self, tool_name):
        if self.tool == tool_name:
            return
        self.tool = tool_name
        self.set_interactive_mode()

    def set_color(self, color_hex):
        self.color = color_hex
        self.update_selected_item_style()

    def set_thickness(self, thickness):
        self.thickness = thickness
        self.update_selected_item_style()

    def set_fill_mode(self, mode):
        self.fill_mode = mode
        self.update_selected_item_style()

    def set_font_size(self, size):
        self.font_size = size
        self.update_selected_item_style()

    def set_font_family(self, family):
        self.font_family = family
        self.update_selected_item_style()

    def set_interactive_mode(self):
        """Configures item selection and drag flags based on current tool."""
        is_select = (self.tool == "select")
        for item in self.scene.items():
            if item != self.bg_pixmap_item and item != self.crop_item:
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, is_select)
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, is_select)

    def update_selected_item_style(self):
        """Applies tool styling (color, stroke, font) to currently selected items."""
        if self.tool != "select":
            return

        for item in self.scene.selectedItems():
            pen_color = QColor(self.color)
            pen = QPen(pen_color, self.thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

            if isinstance(item, QGraphicsPathItem):
                item.setPen(pen)
            elif isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
                item.setPen(pen)
                if self.fill_mode == "filled":
                    item.setBrush(QBrush(pen_color))
                else:
                    item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            elif isinstance(item, QGraphicsTextItem):
                item.setDefaultTextColor(pen_color)
                font = QFont(self.font_family, self.font_size)
                font.setBold(True)
                item.setFont(font)

    def mousePressEvent(self, event):
        if not self.bg_pixmap_item:
            super().mousePressEvent(event)
            return

        scene_pos = self.mapToScene(event.position().toPoint())

        if event.button() == Qt.MouseButton.LeftButton:
            if self.tool == "select":
                super().mousePressEvent(event)
                return

            self.start_point = scene_pos
            pen_color = QColor(self.color)

            if self.tool == "highlighter":
                # Translucent yellow/color highlighter pen
                pen_color.setAlpha(100)
                pen = QPen(pen_color, 18, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                self.pencil_path = QPainterPath(scene_pos)
                self.current_item = self.scene.addPath(self.pencil_path, pen)

            elif self.tool == "pencil":
                pen = QPen(pen_color, self.thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                self.pencil_path = QPainterPath(scene_pos)
                self.current_item = self.scene.addPath(self.pencil_path, pen)

            elif self.tool == "line":
                pen = QPen(pen_color, self.thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                self.current_item = self.scene.addLine(scene_pos.x(), scene_pos.y(), scene_pos.x(), scene_pos.y(), pen)

            elif self.tool == "arrow":
                pen = QPen(pen_color, self.thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                path = make_arrow_path(scene_pos, scene_pos, head_len=max(10, self.thickness * 3.5))
                fill_brush = QBrush(pen_color)
                self.current_item = self.scene.addPath(path, pen, fill_brush)

            elif self.tool == "rectangle":
                pen = QPen(pen_color, self.thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin)
                fill_brush = QBrush(pen_color) if self.fill_mode == "filled" else QBrush(Qt.BrushStyle.NoBrush)
                self.current_item = self.scene.addRect(QRectF(scene_pos, scene_pos), pen, fill_brush)

            elif self.tool == "circle":
                pen = QPen(pen_color, self.thickness, Qt.PenStyle.SolidLine)
                fill_brush = QBrush(pen_color) if self.fill_mode == "filled" else QBrush(Qt.BrushStyle.NoBrush)
                self.current_item = self.scene.addEllipse(QRectF(scene_pos, scene_pos), pen, fill_brush)

            elif self.tool == "text":
                text_item = QGraphicsTextItem("Double click to edit")
                font = QFont(self.font_family, self.font_size)
                font.setBold(True)
                text_item.setFont(font)
                text_item.setDefaultTextColor(pen_color)
                text_item.setPos(scene_pos)
                text_item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
                is_select = (self.tool == "select")
                text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, is_select)
                text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, is_select)
                self.scene.addItem(text_item)
                self.history.append(text_item)
                self.redo_stack.clear()
                if self.on_draw_callback:
                    self.on_draw_callback()

            elif self.tool == "eraser":
                item_at_pos = self.scene.itemAt(scene_pos, QTransform())
                if item_at_pos and item_at_pos != self.bg_pixmap_item:
                    self.scene.removeItem(item_at_pos)
                    if item_at_pos in self.history:
                        self.history.remove(item_at_pos)

            elif self.tool == "crop":
                pen = QPen(QColor("#00E5FF"), 1.5, Qt.PenStyle.DashLine)
                self.current_item = self.scene.addRect(QRectF(scene_pos, scene_pos), pen)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        scene_pos = self.mapToScene(event.position().toPoint())

        if self.cursor_callback:
            self.cursor_callback(int(scene_pos.x()), int(scene_pos.y()))

        if self.tool == "eraser" and (event.buttons() & Qt.MouseButton.LeftButton):
            item_at_pos = self.scene.itemAt(scene_pos, QTransform())
            if item_at_pos and item_at_pos != self.bg_pixmap_item:
                self.scene.removeItem(item_at_pos)
                if item_at_pos in self.history:
                    self.history.remove(item_at_pos)

        if self.start_point and self.current_item:
            if self.tool in ("pencil", "highlighter"):
                self.pencil_path.lineTo(scene_pos)
                self.current_item.setPath(self.pencil_path)

            elif self.tool == "line":
                self.current_item.setLine(self.start_point.x(), self.start_point.y(), scene_pos.x(), scene_pos.y())

            elif self.tool == "arrow":
                path = make_arrow_path(self.start_point, scene_pos, head_len=max(10, self.thickness * 3.5))
                self.current_item.setPath(path)

            elif self.tool == "rectangle":
                rect = QRectF(self.start_point, scene_pos).normalized()
                self.current_item.setRect(rect)

            elif self.tool == "circle":
                rect = QRectF(self.start_point, scene_pos).normalized()
                self.current_item.setRect(rect)

            elif self.tool == "crop":
                rect = QRectF(self.start_point, scene_pos).normalized()
                self.current_item.setRect(rect)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.start_point:
            if self.tool == "crop" and self.current_item:
                crop_rect = self.current_item.rect().toRect()
                self.scene.removeItem(self.current_item)
                self.current_item = None
                self.start_point = None

                if crop_rect.width() > 10 and crop_rect.height() > 10:
                    self.apply_crop(crop_rect)
                    self.set_tool("select")
                    if self.on_tool_change_callback:
                        self.on_tool_change_callback("select")
            else:
                if self.current_item:
                    is_select = (self.tool == "select")
                    self.current_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, is_select)
                    self.current_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, is_select)
                    self.history.append(self.current_item)
                    self.redo_stack.clear()
                    if self.on_draw_callback:
                        self.on_draw_callback()
                self.current_item = None
                self.start_point = None

        super().mouseReleaseEvent(event)

    def apply_crop(self, crop_rect):
        """Crops the base image and bakes annotations."""
        if not self.base_image:
            return

        baked = self.get_baked_image()
        x1 = max(0, crop_rect.x())
        y1 = max(0, crop_rect.y())
        x2 = min(baked.width, crop_rect.x() + crop_rect.width())
        y2 = min(baked.height, crop_rect.y() + crop_rect.height())

        if x2 - x1 > 5 and y2 - y1 > 5:
            cropped = baked.crop((x1, y1, x2, y2))
            self.set_image(cropped)

    def wheelEvent(self, event):
        """Handles canvas zoom with Ctrl+Wheel or element scaling in Select mode."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            angle = event.angleDelta().y()
            factor = 1.15 if angle > 0 else 0.85
            new_zoom = self.zoom_factor * factor
            if 0.25 <= new_zoom <= 3.0:
                self.zoom_factor = new_zoom
                self.scale(factor, factor)
        elif self.tool == "select" and self.scene.selectedItems():
            angle = event.angleDelta().y()
            scale_delta = 1.1 if angle > 0 else 0.9
            for item in self.scene.selectedItems():
                item.setScale(item.scale() * scale_delta)

    def keyPressEvent(self, event):
        """Handles keyboard nudging (+/- scaling, Arrow key nudging)."""
        selected = self.scene.selectedItems()
        if not selected:
            super().keyPressEvent(event)
            return

        step = 5 if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) else 1

        if event.key() == Qt.Key.Key_Left:
            for item in selected:
                item.moveBy(-step, 0)
        elif event.key() == Qt.Key.Key_Right:
            for item in selected:
                item.moveBy(step, 0)
        elif event.key() == Qt.Key.Key_Up:
            for item in selected:
                item.moveBy(0, -step)
        elif event.key() == Qt.Key.Key_Down:
            for item in selected:
                item.moveBy(0, step)
        elif event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            for item in selected:
                item.setScale(item.scale() * 1.1)
        elif event.key() in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
            for item in selected:
                item.setScale(item.scale() * 0.9)
        else:
            super().keyPressEvent(event)

    def undo(self):
        if self.history:
            last_item = self.history.pop()
            self.scene.removeItem(last_item)
            self.redo_stack.append(last_item)
            if self.on_draw_callback:
                self.on_draw_callback()

    def redo(self):
        if self.redo_stack:
            item = self.redo_stack.pop()
            self.scene.addItem(item)
            self.history.append(item)
            if self.on_draw_callback:
                self.on_draw_callback()

    def clear_canvas(self):
        """Resets all vector annotations."""
        for item in list(self.history):
            self.scene.removeItem(item)
        self.history.clear()
        self.redo_stack.clear()
        if self.on_draw_callback:
            self.on_draw_callback()

    def get_baked_image(self):
        """Renders base screenshot plus all vector scene items onto a full-res PIL Image."""
        if not self.base_image:
            return Image.new("RGBA", (800, 600), (255, 255, 255, 255))

        w, h = self.base_image.width, self.base_image.height
        target_img = QImage(w, h, QImage.Format.Format_RGBA8888)
        target_img.fill(Qt.GlobalColor.transparent)

        self.scene.clearSelection()

        painter = QPainter(target_img)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform |
            QPainter.RenderHint.TextAntialiasing
        )

        self.scene.render(painter, QRectF(0, 0, w, h), QRectF(0, 0, w, h))
        painter.end()

        return qimage_to_pil(target_img)

