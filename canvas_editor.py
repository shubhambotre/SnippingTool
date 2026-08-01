import tkinter as tk
from tkinter import ttk
import math
import os
import copy
from PIL import Image, ImageDraw, ImageTk, ImageFont

# Cap undo history so long editing sessions (heavy pencil strokes) don't grow memory unboundedly.
HISTORY_LIMIT = 500

def get_pillow_font(family, size=None):
    """Loads the requested font family and size from Windows Fonts, or falls back to Arial Bold."""
    if size is None:
        size = family
        family = "Arial"
        
    font_map = {
        "Arial": ["arialbd.ttf", "arial.ttf"],
        "Times New Roman": ["timesbd.ttf", "times.ttf"],
        "Courier New": ["courbd.ttf", "cour.ttf"],
        "Georgia": ["georgiab.ttf", "georgia.ttf"],
        "Segoe UI": ["segoeuib.ttf", "segoeui.ttf"],
        "Verdana": ["verdanab.ttf", "verdana.ttf"],
        "Impact": ["impact.ttf"]
    }
    
    filenames = font_map.get(family, ["arialbd.ttf", "arial.ttf"])
    for fname in filenames:
        path = os.path.join("C:\\Windows\\Fonts", fname)
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

class CanvasEditor(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        # Grid layout for Canvas + Scrollbars
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Light theme background for canvas container workspace
        self.canvas = tk.Canvas(self, bg="#EAEAEA", highlightthickness=0, bd=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        
        self.v_scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        
        self.h_scrollbar = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        self.canvas.config(xscrollcommand=self.h_scrollbar.set, yscrollcommand=self.v_scrollbar.set)
        
        # Image containers
        self.base_image = None
        self.current_display_image = None
        self.bg_image_tk = None
        self.bg_image_id = None
        
        # State
        self.tool = "pencil"
        self.color = "#FF3B30"
        self.thickness = 3
        self.fill_mode = "hollow"
        self.font_size = 14
        self.font_family = "Arial"
        self.zoom_factor = 1.0  # Dynamic zoom level
        
        # History
        self.history = []
        self.redo_stack = []

        # Cached dot-grid background: (size, dark) -> PhotoImage, regenerated only on change
        self._grid_cache = None

        # Cached baked image (full-res, annotations applied) + display PhotoImage.
        # _baked_revision is bumped whenever annotations change so _baked() only recomputes when needed.
        self._baked_cache = None   # (revision, image)
        self._baked_revision = 0
        self._display_zoom = None  # zoom used to build _display_photo
        self._display_rev = None   # revision used to build _display_photo
        self._display_photo = None

        # Select-drag overlay state: while dragging an element we render the rest of the
        # image once and only redraw the moving element on top, avoiding a full re-bake per move.
        self._drag_exclude = None
        self._drag_base_ready = False
        self._drag_overlay_id = None

        # Crop confirmation state (#2). Drawing a crop box enters "pending" mode where the
        # region is shown, adjustable, and only applied when the user clicks Crop.
        self.crop_rect = None            # (x1, y1, x2, y2) in image coords
        self.crop_pending = False
        self._crop_buttons_frame = None
        self._crop_btn_window_id = None

        # Select & Move state (supports text and all shapes)
        self.selected_index = None
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.active_handle = None
        self.drag_start_action = None
        self.active_text_saver = None
        
        # Drawing helpers
        self.start_x = None
        self.start_y = None
        self.preview_id = None
        self.temp_pencil_ids = []
        self.pencil_points = []
        
        # Callbacks
        self.on_draw_callback = None
        self.cursor_callback = None
        self.on_crop_complete_callback = None
        self.on_tool_change_callback = None
        
        # Bind mouse events
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        
        # Keyboard nudge bindings (must have focus)
        self.canvas.bind("<Left>", lambda e: self.nudge_selected(-1, 0))
        self.canvas.bind("<Right>", lambda e: self.nudge_selected(1, 0))
        self.canvas.bind("<Up>", lambda e: self.nudge_selected(0, -1))
        self.canvas.bind("<Down>", lambda e: self.nudge_selected(0, 1))
        
        # Shift+Arrows nudge by 5px
        self.canvas.bind("<Shift-Left>", lambda e: self.nudge_selected(-5, 0))
        self.canvas.bind("<Shift-Right>", lambda e: self.nudge_selected(5, 0))
        self.canvas.bind("<Shift-Up>", lambda e: self.nudge_selected(0, -5))
        self.canvas.bind("<Shift-Down>", lambda e: self.nudge_selected(0, 5))
        
        # Keyboard scale size bindings (+ and - keys)
        self.canvas.bind("<plus>", lambda e: self.scale_selected(1.1))
        self.canvas.bind("<KP_Add>", lambda e: self.scale_selected(1.1))
        self.canvas.bind("<equal>", lambda e: self.scale_selected(1.1))
        
        self.canvas.bind("<minus>", lambda e: self.scale_selected(0.9))
        self.canvas.bind("<KP_Subtract>", lambda e: self.scale_selected(0.9))
        
        # Bind Mouse Scroll Wheel (Windows/macOS & Linux bindings)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", self.on_linux_scroll_up)
        self.canvas.bind("<Button-5>", self.on_linux_scroll_down)
        
        self.canvas.bind("<Configure>", lambda e: self.redraw())

    def set_image(self, pil_image):
        self.base_image = pil_image.convert("RGBA")
        self.history.clear()
        self.redo_stack.clear()
        self.selected_index = None
        self.zoom_factor = 1.0  # Reset zoom on new capture
        self._mark_dirty()
        self.redraw()
        self.update_scrollregion()

    def _mark_dirty(self):
        """Invalidates the baked-image cache so the next redraw recomputes annotations."""
        self._baked_revision += 1

    def set_tool(self, tool):
        self.save_active_text()
        self.tool = tool
        self.selected_index = None
        self.active_handle = None
        self.drag_start_action = None
        if tool != "crop":
            self._reset_crop_state()
        self.redraw()
        
        if tool == "eraser":
            self.canvas.config(cursor="hand2")
        elif tool == "crop":
            self.canvas.config(cursor="sizing")
        elif tool == "text":
            self.canvas.config(cursor="xterm")
        elif tool == "select":
            self.canvas.config(cursor="arrow")
        else:
            self.canvas.config(cursor="pencil")

    def set_color(self, color):
        self.color = color
        # Dynamic modification for selected element
        if self.tool == "select" and self.selected_index is not None:
            if self.selected_index < len(self.history):
                self.history[self.selected_index]["color"] = color
                self._mark_dirty()
                self.redraw()
                if self.on_draw_callback:
                    self.on_draw_callback()

    def set_thickness(self, thickness):
        self.thickness = thickness
        # Dynamic modification for selected element
        if self.tool == "select" and self.selected_index is not None:
            if self.selected_index < len(self.history):
                action = self.history[self.selected_index]
                if "thickness" in action:
                    action["thickness"] = thickness
                    self._mark_dirty()
                    self.redraw()
                    if self.on_draw_callback:
                        self.on_draw_callback()

    def set_fill_mode(self, mode):
        self.fill_mode = mode
        # Dynamic modification for selected element
        if self.tool == "select" and self.selected_index is not None:
            if self.selected_index < len(self.history):
                action = self.history[self.selected_index]
                if "fill" in action:
                    action["fill"] = mode
                    self._mark_dirty()
                    self.redraw()
                    if self.on_draw_callback:
                        self.on_draw_callback()

    def set_font_size(self, size):
        self.font_size = size
        # Dynamic modification for selected element
        if self.tool == "select" and self.selected_index is not None:
            if self.selected_index < len(self.history):
                action = self.history[self.selected_index]
                if "font_size" in action:
                    action["font_size"] = size
                    self._mark_dirty()
                    self.redraw()
                    if self.on_draw_callback:
                        self.on_draw_callback()

    def set_font_family(self, family):
        self.font_family = family
        # Dynamic modification for selected element
        if self.tool == "select" and self.selected_index is not None:
            if self.selected_index < len(self.history):
                action = self.history[self.selected_index]
                if action["type"] == "text":
                    action["font_family"] = family
                    self._mark_dirty()
                    self.redraw()
                    if self.on_draw_callback:
                        self.on_draw_callback()

    def zoom_in(self):
        presets = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
        higher = [p for p in presets if p > self.zoom_factor]
        if higher:
            self.zoom_factor = higher[0]
            self.redraw()
            self.update_scrollregion()
            if self.on_draw_callback:
                self.on_draw_callback()
            
    def zoom_out(self):
        presets = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
        lower = [p for p in presets if p < self.zoom_factor]
        if lower:
            self.zoom_factor = lower[-1]
            self.redraw()
            self.update_scrollregion()
            if self.on_draw_callback:
                self.on_draw_callback()
                
    def update_scrollregion(self):
        if self.base_image:
            w = int(self.base_image.width * self.zoom_factor)
            h = int(self.base_image.height * self.zoom_factor)
            self.canvas.config(scrollregion=(0, 0, w, h))

    def _push_history(self, action):
        """Appends an action to the undo history, trimming the oldest entries past the limit."""
        self.history.append(action)
        if len(self.history) > HISTORY_LIMIT:
            del self.history[:len(self.history) - HISTORY_LIMIT]

    def undo(self):
        if self.history:
            self.selected_index = None
            action = self.history.pop()
            self.redo_stack.append(action)
            self._mark_dirty()
            self.redraw()
            if self.on_draw_callback:
                self.on_draw_callback()

    def redo(self):
        if self.redo_stack:
            self.selected_index = None
            action = self.redo_stack.pop()
            self.history.append(action)
            self._mark_dirty()
            self.redraw()
            if self.on_draw_callback:
                self.on_draw_callback()

    def clear_annotations(self):
        self.save_active_text()
        if self.history:
            self.selected_index = None
            self.history.clear()
            self.redo_stack.clear()
            self._mark_dirty()
            self.redraw()
            if self.on_draw_callback:
                self.on_draw_callback()

    def get_handles(self, action):
        t = action["type"]
        if t in ("rectangle", "circle"):
            x1, y1, x2, y2 = action["coords"]
            rx1, ry1 = min(x1, x2), min(y1, y2)
            rx2, ry2 = max(x1, x2), max(y1, y2)
            cxm, cym = (rx1 + rx2) / 2, (ry1 + ry2) / 2
            # 8-point handles: 4 corners + 4 edge midpoints for full resize control (#5)
            return [
                ("TL", rx1, ry1), ("T", cxm, ry1), ("TR", rx2, ry1),
                ("R", rx2, cym), ("BR", rx2, ry2), ("B", cxm, ry2),
                ("BL", rx1, ry2), ("L", rx1, cym),
            ]
        elif t in ("line", "arrow"):
            x1, y1, x2, y2 = action["coords"]
            return [
                ("E1", x1, y1),
                ("E2", x2, y2)
            ]
        elif t == "text":
            x, y = action["coords"]
            font_size = action["font_size"]
            text_w = len(action["text"]) * (font_size * 0.6)
            text_h = font_size
            cxm = x + text_w / 2
            cym = y + text_h / 2
            return [
                ("TL", x, y), ("T", cxm, y), ("TR", x + text_w, y),
                ("R", x + text_w, cym), ("BR", x + text_w, y + text_h), ("B", cxm, y + text_h),
                ("BL", x, y + text_h), ("L", x, cym)
            ]
        elif t in ("pencil", "highlighter"):
            pts = action["points"]
            xs = [pt[0] for pt in pts]
            ys = [pt[1] for pt in pts]
            bx1, by1 = min(xs), min(ys)
            bx2, by2 = max(xs), max(ys)
            return [
                ("TL", bx1, by1),
                ("TR", bx2, by1),
                ("BL", bx1, by2),
                ("BR", bx2, by2)
            ]
        return []

    def on_mouse_move(self, event):
        if self.cursor_callback:
            cx = int(self.canvas.canvasx(event.x) / self.zoom_factor)
            cy = int(self.canvas.canvasy(event.y) / self.zoom_factor)
            if self.base_image:
                w, h = self.base_image.size
                cx = max(0, min(cx, w - 1))
                cy = max(0, min(cy, h - 1))
            self.cursor_callback(cx, cy)

        if self.tool == "select" and self.selected_index is not None:
            if self.selected_index < len(self.history):
                action = self.history[self.selected_index]
                handles = self.get_handles(action)
                mx = self.canvas.canvasx(event.x)
                my = self.canvas.canvasy(event.y)
                
                hovered_handle = None
                for name, hx, hy in handles:
                    hx_s = hx * self.zoom_factor
                    hy_s = hy * self.zoom_factor
                    if math.sqrt((mx - hx_s)**2 + (my - hy_s)**2) < 8:
                        hovered_handle = name
                        break
                        
                if hovered_handle:
                    if hovered_handle in ("TL", "BR"):
                        self.canvas.config(cursor="size_nw_se")
                    elif hovered_handle in ("TR", "BL"):
                        self.canvas.config(cursor="size_ne_sw")
                    elif hovered_handle in ("T", "B"):
                        self.canvas.config(cursor="size_ns")
                    elif hovered_handle in ("L", "R"):
                        self.canvas.config(cursor="size_we")
                    elif hovered_handle in ("E1", "E2"):
                        self.canvas.config(cursor="crosshair")
                else:
                    self.canvas.config(cursor="arrow")

    def on_press(self, event):
        if not self.base_image:
            return
            
        self.save_active_text()
            
        self.start_x = int(self.canvas.canvasx(event.x) / self.zoom_factor)
        self.start_y = int(self.canvas.canvasy(event.y) / self.zoom_factor)
        
        # Focus canvas so keypress events register
        self.canvas.focus_set()
        
        self.active_handle = None
        self.drag_start_action = None

        # Crop: adjust / move an existing pending crop region, or start a new selection (#2)
        if self.tool == "crop" and self.crop_pending and self.crop_rect:
            x1, y1, x2, y2 = self.crop_rect
            mx = self.canvas.canvasx(event.x)
            my = self.canvas.canvasy(event.y)
            z = self.zoom_factor
            hit = None
            for name, hx, hy in self._crop_handles():
                if math.sqrt((mx - hx * z) ** 2 + (my - hy * z) ** 2) < 8:
                    hit = name
                    break
            if hit is not None:
                self.active_handle = hit
                self.drag_start_action = list(self.crop_rect)
                self.last_mouse_x = self.start_x
                self.last_mouse_y = self.start_y
                return
            if x1 <= self.start_x <= x2 and y1 <= self.start_y <= y2:
                self.active_handle = "MOVE"
                self.drag_start_action = list(self.crop_rect)
                self.last_mouse_x = self.start_x
                self.last_mouse_y = self.start_y
                return
            # Clicked outside the pending region -> abandon it and start a fresh selection
            self._reset_crop_state()

        if self.tool == "select" and self.selected_index is not None:
            action = self.history[self.selected_index]
            handles = self.get_handles(action)
            mx = self.canvas.canvasx(event.x)
            my = self.canvas.canvasy(event.y)
            
            for name, hx, hy in handles:
                hx_s = hx * self.zoom_factor
                hy_s = hy * self.zoom_factor
                if math.sqrt((mx - hx_s)**2 + (my - hy_s)**2) < 8:
                    self.active_handle = name
                    self.drag_start_action = copy.deepcopy(action)
                    self.last_mouse_x = self.start_x
                    self.last_mouse_y = self.start_y
                    return
        
        if self.tool == "select":
            self.selected_index = None
            click_radius = 12
            
            for idx in range(len(self.history) - 1, -1, -1):
                action = self.history[idx]
                t = action["type"]
                intersect = False
                
                if t in ("pencil", "highlighter"):
                    for pt in action["points"]:
                        if math.sqrt((pt[0]-self.start_x)**2 + (pt[1]-self.start_y)**2) < click_radius:
                            intersect = True
                            break
                elif t in ("line", "arrow"):
                    x1, y1, x2, y2 = action["coords"]
                    min_x, max_x = min(x1, x2), max(x1, x2)
                    min_y, max_y = min(y1, y2), max(y1, y2)
                    if min_x - 10 <= self.start_x <= max_x + 10 and min_y - 10 <= self.start_y <= max_y + 10:
                        dx, dy = x2 - x1, y2 - y1
                        len_sq = dx*dx + dy*dy
                        if len_sq > 0:
                            proj = max(0, min(1, ((self.start_x - x1)*dx + (self.start_y - y1)*dy) / len_sq))
                            px = x1 + proj * dx
                            py = y1 + proj * dy
                            if math.sqrt((self.start_x-px)**2 + (self.start_y-py)**2) < click_radius:
                                intersect = True
                elif t in ("rectangle", "circle"):
                    x1, y1, x2, y2 = action["coords"]
                    min_x, max_x = min(x1, x2), max(x1, x2)
                    min_y, max_y = min(y1, y2), max(y1, y2)
                    if min_x - click_radius <= self.start_x <= max_x + click_radius and min_y - click_radius <= self.start_y <= max_y + click_radius:
                        intersect = True
                elif t == "text":
                    x, y = action["coords"]
                    text_h = action["font_size"]
                    text_w = len(action["text"]) * (action["font_size"] * 0.6)
                    if x - 10 <= self.start_x <= x + text_w + 10 and y - 10 <= self.start_y <= y + text_h + 10:
                        intersect = True
                        
                if intersect:
                    self.selected_index = idx
                    self.last_mouse_x = self.start_x
                    self.last_mouse_y = self.start_y
                    break
            self.redraw()
            
        elif self.tool == "eraser":
            self.erase_at(self.start_x, self.start_y)
            
        elif self.tool in ("pencil", "highlighter"):
            self.pencil_points = [(self.start_x, self.start_y)]
            self.temp_pencil_ids = []
            
        elif self.tool == "text":
            # Check if user clicked on an existing text block to edit it
            editing_index = -1
            for idx in range(len(self.history) - 1, -1, -1):
                action = self.history[idx]
                if action["type"] == "text":
                    ax, ay = action["coords"]
                    text_h = action["font_size"]
                    text_w = len(action["text"]) * (action["font_size"] * 0.6)
                    
                    if ax - 10 <= self.start_x <= ax + text_w + 10 and ay - 10 <= self.start_y <= ay + text_h + 10:
                        editing_index = idx
                        break
            
            if editing_index != -1:
                action = self.history.pop(editing_index)
                ax, ay = action["coords"]
                self.redraw()
                # Preserve the annotation's own style so editing the text doesn't reset its size/family
                self.create_text_input(
                    ax, ay, prefill=action["text"], index=editing_index,
                    font_size=action.get("font_size", self.font_size),
                    font_family=action.get("font_family", self.font_family),
                )
            else:
                self.create_text_input(self.start_x, self.start_y)

    def on_drag(self, event):
        if self.start_x is None or self.start_y is None:
            return
            
        cx = int(self.canvas.canvasx(event.x) / self.zoom_factor)
        cy = int(self.canvas.canvasy(event.y) / self.zoom_factor)
        
        if self.cursor_callback:
            self.cursor_callback(cx, cy)
            
        if self.tool == "select":
            if self.selected_index is not None:
                if self.active_handle is not None and self.drag_start_action is not None:
                    # Perform resize logic
                    action = self.history[self.selected_index]
                    t = action["type"]
                    
                    if t in ("rectangle", "circle"):
                        ox1, oy1, ox2, oy2 = self.drag_start_action["coords"]
                        rx1, ry1 = min(ox1, ox2), min(oy1, oy2)
                        rx2, ry2 = max(ox1, ox2), max(oy1, oy2)
                        dx = cx - self.start_x
                        dy = cy - self.start_y
                        nrx1, nry1, nrx2, nry2 = rx1, ry1, rx2, ry2
                        h = self.active_handle
                        if h == "TL": nrx1 += dx; nry1 += dy
                        elif h == "T": nry1 += dy
                        elif h == "TR": nrx2 += dx; nry1 += dy
                        elif h == "R": nrx2 += dx
                        elif h == "BR": nrx2 += dx; nry2 += dy
                        elif h == "B": nry2 += dy
                        elif h == "BL": nrx1 += dx; nry2 += dy
                        elif h == "L": nrx1 += dx
                        # Normalize so the shape stays valid as any corner/edge is dragged
                        action["coords"] = (min(nrx1, nrx2), min(nry1, nry2), max(nrx1, nrx2), max(nry1, nry2))

                    elif t in ("line", "arrow"):
                        ox1, oy1, ox2, oy2 = self.drag_start_action["coords"]
                        if self.active_handle == "E1":
                            action["coords"] = (ox1 + (cx - self.start_x), oy1 + (cy - self.start_y), ox2, oy2)
                        elif self.active_handle == "E2":
                            action["coords"] = (ox1, oy1, ox2 + (cx - self.start_x), oy2 + (cy - self.start_y))
                            
                    elif t == "text":
                        ox, oy = self.drag_start_action["coords"]
                        ofs = self.drag_start_action["font_size"]
                        otext = self.drag_start_action["text"]
                        otext_w = len(otext) * (ofs * 0.6)
                        otext_h = ofs
                        
                        if self.active_handle in ("BR", "R", "B"):
                            if self.active_handle == "R":
                                current_w = cx - ox
                                scale = current_w / otext_w if otext_w > 0 else 1.0
                            elif self.active_handle == "B":
                                current_h = cy - oy
                                scale = current_h / otext_h if otext_h > 0 else 1.0
                            else: # BR
                                current_w = cx - ox
                                current_h = cy - oy
                                scale_w = current_w / otext_w if otext_w > 0 else 1.0
                                scale_h = current_h / otext_h if otext_h > 0 else 1.0
                                scale = max(scale_w, scale_h)
                            scale = max(0.1, scale)
                            action["font_size"] = max(6, min(120, int(round(ofs * scale))))
                        elif self.active_handle in ("BL", "L"):
                            if self.active_handle == "L":
                                current_w = (ox + otext_w) - cx
                                scale = current_w / otext_w if otext_w > 0 else 1.0
                            else: # BL
                                current_w = (ox + otext_w) - cx
                                current_h = cy - oy
                                scale_w = current_w / otext_w if otext_w > 0 else 1.0
                                scale_h = current_h / otext_h if otext_h > 0 else 1.0
                                scale = max(scale_w, scale_h)
                            scale = max(0.1, scale)
                            action["font_size"] = max(6, min(120, int(round(ofs * scale))))
                            new_text_w = len(otext) * (action["font_size"] * 0.6)
                            action["coords"] = (ox + otext_w - new_text_w, oy)
                        elif self.active_handle in ("TR", "T"):
                            if self.active_handle == "T":
                                current_h = (oy + otext_h) - cy
                                scale = current_h / otext_h if otext_h > 0 else 1.0
                            else: # TR
                                current_w = cx - ox
                                current_h = (oy + otext_h) - cy
                                scale_w = current_w / otext_w if otext_w > 0 else 1.0
                                scale_h = current_h / otext_h if otext_h > 0 else 1.0
                                scale = max(scale_w, scale_h)
                            scale = max(0.1, scale)
                            action["font_size"] = max(6, min(120, int(round(ofs * scale))))
                            new_text_h = action["font_size"]
                            action["coords"] = (ox, oy + otext_h - new_text_h)
                        elif self.active_handle == "TL":
                            current_w = (ox + otext_w) - cx
                            current_h = (oy + otext_h) - cy
                            scale_w = current_w / otext_w if otext_w > 0 else 1.0
                            scale_h = current_h / otext_h if otext_h > 0 else 1.0
                            scale = max(0.1, max(scale_w, scale_h))
                            action["font_size"] = max(6, min(120, int(round(ofs * scale))))
                            new_text_w = len(otext) * (action["font_size"] * 0.6)
                            new_text_h = action["font_size"]
                            action["coords"] = (ox + otext_w - new_text_w, oy + otext_h - new_text_h)
                            
                    elif t in ("pencil", "highlighter"):
                        opts = self.drag_start_action["points"]
                        oxs = [p[0] for p in opts]
                        oys = [p[1] for p in opts]
                        obx1, oby1 = min(oxs), min(oys)
                        obx2, oby2 = max(oxs), max(oys)
                        ow = obx2 - obx1
                        oh = oby2 - oby1
                        
                        nbx1, nby1, nbx2, nby2 = obx1, oby1, obx2, oby2
                        if self.active_handle == "TL":
                            nbx1 = obx1 + (cx - self.start_x)
                            nby1 = oby1 + (cy - self.start_y)
                        elif self.active_handle == "TR":
                            nbx2 = obx2 + (cx - self.start_x)
                            nby1 = oby1 + (cy - self.start_y)
                        elif self.active_handle == "BL":
                            nbx1 = obx1 + (cx - self.start_x)
                            nby2 = oby2 + (cy - self.start_y)
                        elif self.active_handle == "BR":
                            nbx2 = obx2 + (cx - self.start_x)
                            nby2 = oby2 + (cy - self.start_y)
                            
                        nw = nbx2 - nbx1
                        nh = nby2 - nby1
                        if ow > 0 and oh > 0:
                            action["points"] = [
                                (nbx1 + (p[0] - obx1) * (nw / ow), nby1 + (p[1] - oby1) * (nh / oh))
                                for p in opts
                            ]

                    self._redraw_select_drag()
                else:
                    dx = cx - self.last_mouse_x
                    dy = cy - self.last_mouse_y
                    self.last_mouse_x = cx
                    self.last_mouse_y = cy
                    
                    # Apply translation to selected action
                    action = self.history[self.selected_index]
                    t = action["type"]
                    if t == "text":
                        ax, ay = action["coords"]
                        action["coords"] = (ax + dx, ay + dy)
                    elif t in ("pencil", "highlighter"):
                        action["points"] = [(p[0] + dx, p[1] + dy) for p in action["points"]]
                    elif t in ("line", "arrow", "rectangle", "circle"):
                        x1, y1, x2, y2 = action["coords"]
                        action["coords"] = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)

                    self._redraw_select_drag()

        elif self.tool == "eraser":
            self.erase_at(cx, cy)
            
        elif self.tool in ("pencil", "highlighter"):
            color = "#FFCC00" if self.tool == "highlighter" else self.color
            # Must match the baked width in get_edited_image so preview == exported stroke
            thickness = 18 if self.tool == "highlighter" else self.thickness
            
            x_prev, y_prev = self.pencil_points[-1]
            seg_id = self.canvas.create_line(
                x_prev * self.zoom_factor, y_prev * self.zoom_factor, 
                cx * self.zoom_factor, cy * self.zoom_factor,
                fill=color, width=int(round(thickness * self.zoom_factor)),
                capstyle=tk.ROUND, joinstyle=tk.ROUND,
                tags="preview"
            )
            self.temp_pencil_ids.append(seg_id)
            self.pencil_points.append((cx, cy))
            
        elif self.tool == "line":
            if self.preview_id:
                self.canvas.delete(self.preview_id)
            self.preview_id = self.canvas.create_line(
                self.start_x * self.zoom_factor, self.start_y * self.zoom_factor, 
                cx * self.zoom_factor, cy * self.zoom_factor,
                fill=self.color, width=int(round(self.thickness * self.zoom_factor)),
                tags="preview"
            )
            
        elif self.tool == "arrow":
            if self.preview_id:
                self.canvas.delete(self.preview_id)
            self.preview_id = self.canvas.create_line(
                self.start_x * self.zoom_factor, self.start_y * self.zoom_factor, 
                cx * self.zoom_factor, cy * self.zoom_factor,
                fill=self.color, width=int(round(self.thickness * self.zoom_factor)),
                arrow=tk.LAST, arrowshape=(12 * self.zoom_factor, 14 * self.zoom_factor, 4 * self.zoom_factor),
                tags="preview"
            )
            
        elif self.tool == "rectangle":
            if self.preview_id:
                self.canvas.delete(self.preview_id)
            fill_col = self.color if self.fill_mode == "filled" else ""
            self.preview_id = self.canvas.create_rectangle(
                self.start_x * self.zoom_factor, self.start_y * self.zoom_factor, 
                cx * self.zoom_factor, cy * self.zoom_factor,
                outline=self.color, width=int(round(self.thickness * self.zoom_factor)),
                fill=fill_col, tags="preview"
            )
            
        elif self.tool == "circle":
            if self.preview_id:
                self.canvas.delete(self.preview_id)
            fill_col = self.color if self.fill_mode == "filled" else ""
            self.preview_id = self.canvas.create_oval(
                self.start_x * self.zoom_factor, self.start_y * self.zoom_factor, 
                cx * self.zoom_factor, cy * self.zoom_factor,
                outline=self.color, width=int(round(self.thickness * self.zoom_factor)),
                fill=fill_col, tags="preview"
            )
            
        elif self.tool == "crop":
            # Adjust / move the pending crop region (#2)
            if self.crop_pending and self.active_handle:
                self._adjust_crop(cx, cy)
                return
            # Live preview while drawing a new selection (clamped to image bounds, #3)
            if self.preview_id:
                self.canvas.delete(self.preview_id)
            w_img, h_img = self.base_image.size
            px1 = max(0, min(self.start_x, w_img))
            py1 = max(0, min(self.start_y, h_img))
            px2 = max(0, min(cx, w_img))
            py2 = max(0, min(cy, h_img))
            self.preview_id = self.canvas.create_rectangle(
                min(px1, px2) * self.zoom_factor, min(py1, py2) * self.zoom_factor,
                max(px1, px2) * self.zoom_factor, max(py1, py2) * self.zoom_factor,
                outline="#005FB8", width=2, dash=(6, 4), tags="preview"
            )

    def on_release(self, event):
        if self.start_x is None or self.start_y is None:
            return
            
        cx = int(self.canvas.canvasx(event.x) / self.zoom_factor)
        cy = int(self.canvas.canvasy(event.y) / self.zoom_factor)
        
        # Delete previews
        if self.preview_id:
            self.canvas.delete(self.preview_id)
            self.preview_id = None
            
        for seg_id in self.temp_pencil_ids:
            self.canvas.delete(seg_id)
        self.temp_pencil_ids.clear()
        
        action = None
        if self.tool == "select":
            if self.selected_index is not None:
                # Finalize a move/resize: bake the dragged element back into the full render
                self._finish_select_drag()

        elif self.tool == "crop":
            # Enter "pending" crop mode: show the region, let the user adjust it, and wait
            # for the Crop button (#2). Do NOT crop immediately.
            w_img, h_img = self.base_image.size
            x1 = max(0, min(self.start_x, w_img))
            y1 = max(0, min(self.start_y, h_img))
            x2 = max(0, min(cx, w_img))
            y2 = max(0, min(cy, h_img))

            crop_x1 = min(x1, x2)
            crop_y1 = min(y1, y2)
            crop_x2 = max(x1, x2)
            crop_y2 = max(y1, y2)

            if (crop_x2 - crop_x1) > 10 and (crop_y2 - crop_y1) > 10:
                self.crop_rect = (crop_x1, crop_y1, crop_x2, crop_y2)
                self.crop_pending = True
                self._crop_buttons_frame = None
                self.redraw()

        elif self.tool in ("pencil", "highlighter"):
            if len(self.pencil_points) > 1:
                action = {
                    "type": self.tool,
                    "points": list(self.pencil_points),
                    "color": self.color,
                    "thickness": self.thickness
                }
        elif self.tool in ("line", "arrow", "rectangle", "circle"):
            if abs(self.start_x - cx) > 1 or abs(self.start_y - cy) > 1:
                action = {
                    "type": self.tool,
                    "coords": (self.start_x, self.start_y, cx, cy),
                    "color": self.color,
                    "thickness": self.thickness,
                    "fill": self.fill_mode
                }
                
        if action:
            self._push_history(action)
            self.redo_stack.clear()
            self._mark_dirty()

            # Automatically select a freshly drawn shape so resize/move handles appear
            # immediately, without an extra Select-tool click (#1).
            if self.tool in ("rectangle", "circle") and self.on_tool_change_callback:
                self.on_tool_change_callback("select")
                self.selected_index = len(self.history) - 1

            self.redraw()
            if self.on_draw_callback:
                self.on_draw_callback()

        self.active_handle = None
        self.drag_start_action = None
        self.start_x = None
        self.start_y = None

    def nudge_selected(self, dx, dy):
        """Keyboard shortcut handler to translate current selected action by dx, dy."""
        if self.tool == "select" and self.selected_index is not None:
            if self.selected_index < len(self.history):
                action = self.history[self.selected_index]
                t = action["type"]
                
                if t == "text":
                    ax, ay = action["coords"]
                    action["coords"] = (ax + dx, ay + dy)
                elif t in ("pencil", "highlighter"):
                    action["points"] = [(p[0] + dx, p[1] + dy) for p in action["points"]]
                elif t in ("line", "arrow", "rectangle", "circle"):
                    x1, y1, x2, y2 = action["coords"]
                    action["coords"] = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)

                self._mark_dirty()
                self.redraw()
                if self.on_draw_callback:
                    self.on_draw_callback()

    def scale_selected(self, factor):
        """Keyboard shortcut handler to scale the physical size of selected shape or text annotations."""
        if self.tool == "select" and self.selected_index is not None:
            if self.selected_index < len(self.history):
                action = self.history[self.selected_index]
                t = action["type"]
                
                if t == "text":
                    new_fs = max(6, min(120, int(round(action["font_size"] * factor))))
                    action["font_size"] = new_fs
                elif t in ("pencil", "highlighter"):
                    pts = action["points"]
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    cx = sum(xs) / len(xs)
                    cy = sum(ys) / len(ys)
                    action["points"] = [
                        (cx + (p[0] - cx) * factor, cy + (p[1] - cy) * factor)
                        for p in pts
                    ]
                elif t in ("line", "arrow", "rectangle", "circle"):
                    x1, y1, x2, y2 = action["coords"]
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2
                    action["coords"] = (
                        cx + (x1 - cx) * factor,
                        cy + (y1 - cy) * factor,
                        cx + (x2 - cx) * factor,
                        cy + (y2 - cy) * factor
                    )

                self._mark_dirty()
                self.redraw()
                if self.on_draw_callback:
                    self.on_draw_callback()

    def on_mouse_wheel(self, event):
        """Mouse Scroll Wheel handler. Scales the selected element, or zooms canvas if Ctrl is held."""
        # Check if Ctrl key is held down (mask is 0x0004)
        ctrl_held = (event.state & 0x0004) != 0
        
        if ctrl_held:
            # Control + Scroll = Canvas Zoom
            if event.delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            return "break"  # Consume event to prevent canvas scrolling
            
        if self.tool == "select" and self.selected_index is not None:
            # Scroll up = Scale Larger, Scroll down = Scale Smaller
            if event.delta > 0:
                self.scale_selected(1.1)
            else:
                self.scale_selected(0.9)
            return "break"  # Consume event to prevent canvas scrolling

    def on_linux_scroll_up(self, event):
        """Linux-specific scroll up handler."""
        ctrl_held = (event.state & 0x0004) != 0
        if ctrl_held:
            self.zoom_in()
            return "break"
        if self.tool == "select" and self.selected_index is not None:
            self.scale_selected(1.1)
            return "break"

    def on_linux_scroll_down(self, event):
        """Linux-specific scroll down handler."""
        ctrl_held = (event.state & 0x0004) != 0
        if ctrl_held:
            self.zoom_out()
            return "break"
        if self.tool == "select" and self.selected_index is not None:
            self.scale_selected(0.9)
            return "break"

    def erase_at(self, cx, cy):
        eraser_radius = 16
        modified = False
        
        for idx in range(len(self.history) - 1, -1, -1):
            action = self.history[idx]
            t = action["type"]
            intersect = False
            
            if t in ("pencil", "highlighter"):
                for pt in action["points"]:
                    if math.sqrt((pt[0]-cx)**2 + (pt[1]-cy)**2) < eraser_radius:
                        intersect = True
                        break
            elif t in ("line", "arrow"):
                x1, y1, x2, y2 = action["coords"]
                min_x, max_x = min(x1, x2), max(x1, x2)
                min_y, max_y = min(y1, y2), max(y1, y2)
                if min_x - 10 <= cx <= max_x + 10 and min_y - 10 <= cy <= max_y + 10:
                    dx, dy = x2 - x1, y2 - y1
                    len_sq = dx*dx + dy*dy
                    if len_sq > 0:
                        proj = max(0, min(1, ((cx - x1)*dx + (cy - y1)*dy) / len_sq))
                        px = x1 + proj * dx
                        py = y1 + proj * dy
                        if math.sqrt((cx-px)**2 + (cy-py)**2) < eraser_radius:
                            intersect = True
            elif t in ("rectangle", "circle"):
                x1, y1, x2, y2 = action["coords"]
                min_x, max_x = min(x1, x2), max(x1, x2)
                min_y, max_y = min(y1, y2), max(y1, y2)
                if min_x - eraser_radius <= cx <= max_x + eraser_radius and min_y - eraser_radius <= cy <= max_y + eraser_radius:
                    intersect = True
            elif t == "text":
                x, y = action["coords"]
                if math.sqrt((x-cx)**2 + (y-cy)**2) < 25:
                    intersect = True
                    
            if intersect:
                self.history.pop(idx)
                modified = True
                break

        if modified:
            self._mark_dirty()
            self.redraw()
            if self.on_draw_callback:
                self.on_draw_callback()

    def save_active_text(self):
        """Saves and closes the currently active text entry widget if one exists."""
        if getattr(self, "active_text_saver", None) is not None:
            saver = self.active_text_saver
            self.active_text_saver = None
            saver()

    def create_text_input(self, x, y, prefill="", index=None, font_size=None, font_family=None):
        """Spawns text entry box. Prefills and inserts at index if modifying."""
        if font_size is None:
            font_size = self.font_size
        if font_family is None:
            font_family = self.font_family

        self.save_active_text() # Save any previous active text input first

        entry_frame = tk.Frame(self.canvas, bg="#005FB8", bd=1)

        # Scale input font size to match canvas zoom levels dynamically
        scaled_font_size = int(round(font_size * self.zoom_factor))

        entry = tk.Entry(
            entry_frame, fg="#0E1013", bg="#FFFFFF",
            font=(font_family, scaled_font_size, "bold"), bd=0, width=25,
            highlightthickness=0, insertbackground="#005FB8",
            selectbackground="#E5E5E5", selectforeground="#0E1013"
        )
        entry.pack(padx=2, pady=2)

        if prefill:
            entry.insert(0, prefill)
            entry.select_range(0, tk.END)

        canvas_window_id = self.canvas.create_window(x * self.zoom_factor, y * self.zoom_factor, anchor=tk.NW, window=entry_frame)
        entry.focus_set()

        saved = False
        def save_text(event=None):
            nonlocal saved
            if saved:
                return
            saved = True

            text_str = entry.get().strip()
            self.canvas.delete(canvas_window_id)
            entry_frame.destroy()

            # Clear reference if this was the active saver
            if getattr(self, "active_text_saver", None) == save_text:
                self.active_text_saver = None

            if text_str:
                action = {
                    "type": "text",
                    "coords": (x, y),
                    "text": text_str,
                    "color": self.color,
                    "font_size": font_size,
                    "font_family": font_family
                }
                if index is not None:
                    self.history.insert(index, action)
                    selected_idx = index
                else:
                    self._push_history(action)
                    selected_idx = len(self.history) - 1
                self.redo_stack.clear()
                self._mark_dirty()
                
                # Automatically select text after creation/editing completes via Return key
                is_return = False
                if event and hasattr(event, "keysym") and event.keysym == "Return":
                    is_return = True

                if is_return and self.on_tool_change_callback:
                    self.on_tool_change_callback("select")
                    self.selected_index = selected_idx
                
                self.redraw()
                if self.on_draw_callback:
                    self.on_draw_callback()
            else:
                self.redraw()
                if self.on_draw_callback:
                    self.on_draw_callback()

        self.active_text_saver = save_text
        entry.bind("<Return>", save_text)
        entry.bind("<FocusOut>", save_text)

    def redraw(self):
        """Public entry point for a full canvas render."""
        self._full_render()

    def _full_render(self, exclude_index=None, show_selection=True):
        """Rebuilds the canvas. Uses cached grid, baked image and display photo so frequent
        redraws (window resize, hover, tool switches) don't re-render everything from scratch."""
        self.canvas.delete("all")
        self.bg_image_id = None
        self._drag_overlay_id = None
        self._crop_buttons_frame = None

        # Determine light/dark based on canvas background
        bg_hex = self.canvas.cget("bg").lower()
        is_dark = bg_hex in ("#1e1e1e", "#252525", "#141517", "#1c1c1c", "#1a1c1e", "#1f2022")

        text_color = "#FFFFFF" if is_dark else "#111827"
        muted_color = "#9CA3AF" if is_dark else "#6B7280"
        card_bg = "#2D2F31" if is_dark else "#FFFFFF"
        card_border = "#3F4347" if is_dark else "#E5E7EB"
        key_bg = "#3A3C3E" if is_dark else "#F3F4F6"
        key_border = "#4F5357" if is_dark else "#D1D5DB"
        key_text = "#FFFFFF" if is_dark else "#111827"

        if not self.base_image:
            self._reset_crop_state()
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
            if w <= 1 or h <= 1:
                w = max(w, 900)
                h = max(h, 600)

            cy = h / 2

            # Logo display with vector fallback
            logo_path = os.path.join(os.path.dirname(__file__), "SnippingTool.png")
            has_logo = False
            if os.path.exists(logo_path):
                try:
                    logo_img = Image.open(logo_path).convert("RGBA")
                    logo_scaled = logo_img.resize((80, 80), Image.Resampling.LANCZOS)
                    self.logo_tk = ImageTk.PhotoImage(logo_scaled)
                    self.canvas.create_image(w/2, cy - 65, image=self.logo_tk, tags="welcome")
                    has_logo = True
                except Exception:
                    pass

            if not has_logo:
                self.canvas.create_rectangle(w/2 - 32, cy - 90, w/2 + 32, cy - 40, outline=muted_color, width=2, tags="welcome")
                self.canvas.create_polygon([w/2 - 15, cy - 90, w/2 - 8, cy - 100, w/2 + 8, cy - 100, w/2 + 15, cy - 90], outline=muted_color, fill="", width=2, tags="welcome")
                self.canvas.create_oval(w/2 - 16, cy - 80, w/2 + 16, cy - 50, outline=muted_color, width=2, tags="welcome")
                self.canvas.create_oval(w/2 - 5, cy - 69, w/2 + 5, cy - 59, fill=muted_color, outline="", tags="welcome")
                self.canvas.create_oval(w/2 + 18, cy - 84, w/2 + 22, cy - 80, fill=muted_color, outline="", tags="welcome")

            # Text layout
            self.canvas.create_text(w / 2, cy - 15, text="SCREEN SNIP & ANNOTATION BOARD", fill=text_color, font=("Segoe UI", 12, "bold"), justify=tk.CENTER, tags="welcome")
            self.canvas.create_text(w / 2, cy + 8, text="Press a shortcut below or click 'New Snip' to capture your screen", fill=muted_color, font=("Segoe UI", 9), justify=tk.CENTER, tags="welcome")

            shortcuts = [
                (["Shift", "PrtSc"], "Capture Full Screen"),
                (["Ctrl", "N"], "New Region Snip"),
                (["Ctrl", "C"], "Copy current snippet"),
                (["Ctrl", "S"], "Quick-save image")
            ]

            start_y = cy + 40
            for keys, desc in shortcuts:
                curr_x = w / 2 - 20
                for i, key in enumerate(reversed(keys)):
                    kw = len(key) * 7 + 14
                    curr_x -= kw
                    self.canvas.create_rectangle(curr_x, start_y, curr_x + kw, start_y + 18, fill=key_bg, outline=key_border, width=1, tags="welcome")
                    self.canvas.create_text(curr_x + kw/2, start_y + 9, text=key, fill=key_text, font=("Consolas", 8, "bold"), tags="welcome")
                    if i < len(keys) - 1:
                        curr_x -= 14
                        self.canvas.create_text(curr_x + 7, start_y + 9, text="+", fill=muted_color, font=("Segoe UI", 9, "bold"), tags="welcome")
                self.canvas.create_text(w / 2 + 10, start_y + 9, text=desc, fill=muted_color, font=("Segoe UI", 9), anchor=tk.W, tags="welcome")
                start_y += 26
            return

        # Draw Figma-style dot grid background (cached)
        canvas_w = max(self.canvas.winfo_width(), int(self.base_image.width * self.zoom_factor) + 200)
        canvas_h = max(self.canvas.winfo_height(), int(self.base_image.height * self.zoom_factor) + 200)

        grid_key = (canvas_w, canvas_h, is_dark)
        if self._grid_cache is None or self._grid_cache[0] != grid_key:
            grid_img = Image.new("RGBA", (canvas_w, canvas_h), self.canvas.cget("bg"))
            grid_draw = ImageDraw.Draw(grid_img)
            grid_spacing = 20
            dot_color = (100, 110, 120, 40) if is_dark else (200, 210, 220, 80)
            for x in range(grid_spacing, canvas_w, grid_spacing):
                for y in range(grid_spacing, canvas_h, grid_spacing):
                    grid_draw.rectangle([x, y, x+1, y+1], fill=dot_color)
            self._grid_cache = (grid_key, ImageTk.PhotoImage(grid_img))

        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._grid_cache[1], tags="grid")

        # Base image with annotations (cached unless we're excluding a mid-drag element)
        if exclude_index is not None:
            base_rendered = self._get_edited_image_raw(exclude_index=exclude_index)
            _, photo = self._photo_at_zoom(base_rendered)
        else:
            base_rendered = self._baked()
            if self._display_zoom != self.zoom_factor or self._display_rev != self._baked_revision:
                _, photo = self._photo_at_zoom(base_rendered)
                self._display_zoom = self.zoom_factor
                self._display_rev = self._baked_revision
                self._display_photo = photo
            else:
                photo = self._display_photo

        # Draw a clean border/shadow around the screenshot
        sw = int(round(base_rendered.width * self.zoom_factor))
        sh = int(round(base_rendered.height * self.zoom_factor))
        border_col = "#3F4347" if is_dark else "#D1D5DB"
        self.canvas.create_rectangle(-1, -1, sw + 1, sh + 1, outline=border_col, width=1, tags="shadow")

        self.bg_image_tk = photo
        self.bg_image_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=photo, tags="background")

        # Selection highlight + resize handles (only in the normal render, not mid-drag)
        if show_selection and self.tool == "select" and self.selected_index is not None:
            if self.selected_index < len(self.history):
                action = self.history[self.selected_index]
                bx1, by1, bx2, by2 = self._action_bbox(action)
                bx1 -= 2; by1 -= 2; bx2 += 2; by2 += 2
                self.canvas.create_rectangle(
                    bx1 * self.zoom_factor, by1 * self.zoom_factor,
                    bx2 * self.zoom_factor, by2 * self.zoom_factor,
                    outline="#005FB8", width=1.5, dash=(4, 4), tags="selection_box"
                )
                handles = self.get_handles(action)
                for name, hx, hy in handles:
                    hx_s = hx * self.zoom_factor
                    hy_s = hy * self.zoom_factor
                    r = 4.5
                    self.canvas.create_oval(hx_s - r, hy_s - r, hx_s + r, hy_s + r,
                                            fill="#FFFFFF", outline="#005FB8", width=1.5, tags="resize_handle")

        # Crop confirmation UI
        if self.crop_pending and self.crop_rect and exclude_index is None:
            self._draw_crop_ui()

    # --- Select-drag overlay (fast per-move updates) ---
    def _ensure_drag_base(self):
        """Renders the image once without the element being dragged, then caches it."""
        if self._drag_base_ready:
            return
        self._drag_exclude = self.selected_index
        self._full_render(exclude_index=self.selected_index, show_selection=False)
        self._drag_base_ready = True

    def _render_moving_overlay(self):
        """Bakes just the dragged element onto a small overlay photo and stacks it on top."""
        action = self.history[self.selected_index]
        x1, y1, x2, y2 = self._action_bbox(action, pad=6)
        bw = int(round(x2 - x1))
        bh = int(round(y2 - y1))
        if bw <= 0 or bh <= 0:
            return
        img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        self._draw_action(draw, action, offx=x1, offy=y1)
        _, photo = self._photo_at_zoom(img)
        self._drag_overlay_tk = photo
        if self._drag_overlay_id is None:
            self._drag_overlay_id = self.canvas.create_image(
                x1 * self.zoom_factor, y1 * self.zoom_factor,
                anchor=tk.NW, image=photo, tags="drag_overlay"
            )
        else:
            self.canvas.itemconfig(self._drag_overlay_id, image=photo)
            self.canvas.coords(self._drag_overlay_id, x1 * self.zoom_factor, y1 * self.zoom_factor)
        self.canvas.tag_raise("drag_overlay")

    def _redraw_select_drag(self):
        """Renders the static image once and the moving element as an overlay each move."""
        self._mark_dirty()
        self._ensure_drag_base()
        self.canvas.delete("drag_overlay")
        self._drag_overlay_id = None
        self._render_moving_overlay()
        if self.on_draw_callback:
            self.on_draw_callback()

    def _finish_select_drag(self):
        """Finalizes a finished select-move/resize: fully re-renders with the element baked in."""
        self._mark_dirty()
        self._drag_base_ready = False
        self._drag_exclude = None
        self._drag_overlay_id = None
        self.redraw()
        if self.on_draw_callback:
            self.on_draw_callback()

    # --- Crop confirmation flow (#2) ---
    def _crop_handles(self):
        x1, y1, x2, y2 = self.crop_rect
        cxm, cym = (x1 + x2) / 2, (y1 + y2) / 2
        return [
            ("TL", x1, y1), ("T", cxm, y1), ("TR", x2, y1),
            ("R", x2, cym), ("BR", x2, y2), ("B", cxm, y2),
            ("BL", x1, y2), ("L", x1, cym),
        ]

    def _draw_crop_ui(self):
        self.canvas.delete("cropdim")
        x1, y1, x2, y2 = self.crop_rect
        z = self.zoom_factor
        sx1, sy1, sx2, sy2 = x1 * z, y1 * z, x2 * z, y2 * z
        W = max(self.canvas.winfo_width(), int(self.base_image.width * z) + 200)
        H = max(self.canvas.winfo_height(), int(self.base_image.height * z) + 200)

        # Dim the area outside the crop region
        dim = "#000000"
        self.canvas.create_rectangle(0, 0, W, sy1, fill=dim, stipple="gray25", tags="cropdim")
        self.canvas.create_rectangle(0, sy2, W, H, fill=dim, stipple="gray25", tags="cropdim")
        self.canvas.create_rectangle(0, sy1, sx1, sy2, fill=dim, stipple="gray25", tags="cropdim")
        self.canvas.create_rectangle(sx2, sy1, W, sy2, fill=dim, stipple="gray25", tags="cropdim")

        self.canvas.create_rectangle(sx1, sy1, sx2, sy2, outline="#005FB8", width=2, dash=(6, 4), tags="cropdim")
        self.canvas.create_text((sx1 + sx2) / 2, max(12, sy1 - 10),
                                text=f"{int(x2 - x1)} x {int(y2 - y1)} px",
                                fill="#005FB8", font=("Segoe UI", 9, "bold"), tags="cropdim")

        # 8 resize handles around the crop region
        for name, hx, hy in self._crop_handles():
            hx, hy = hx * z, hy * z
            r = 5
            self.canvas.create_oval(hx - r, hy - r, hx + r, hy + r,
                                    fill="#FFFFFF", outline="#005FB8", width=1.5, tags="cropdim")

        # Crop / Cancel buttons
        btn_y = min(sy2 + 8, max(H - 40, 8))
        if self._crop_buttons_frame is None:
            frame = tk.Frame(self.canvas, bg="#005FB8")
            b1 = tk.Button(frame, text=" Crop ", command=self.apply_crop, bg="#005FB8", fg="#FFFFFF",
                           activebackground="#004C94", activeforeground="#FFFFFF", bd=0, relief="flat",
                           padx=6, pady=2, font=("Segoe UI", 9, "bold"))
            b1.pack(side=tk.LEFT, padx=1, pady=2)
            b2 = tk.Button(frame, text=" Cancel ", command=self.cancel_crop, bg="#3A3C3E", fg="#FFFFFF",
                           activebackground="#2D2F31", bd=0, relief="flat", padx=6, pady=2,
                           font=("Segoe UI", 9, "bold"))
            b2.pack(side=tk.LEFT, padx=1, pady=2)
            self._crop_buttons_frame = frame
            self._crop_btn_window_id = self.canvas.create_window(sx1, btn_y, anchor=tk.NW, window=frame, tags="cropdim")
        else:
            self.canvas.coords(self._crop_btn_window_id, sx1, btn_y)
        self.canvas.tag_raise("cropdim")

    def _reset_crop_state(self):
        self.crop_rect = None
        self.crop_pending = False
        self._crop_buttons_frame = None
        self._crop_btn_window_id = None

    def apply_crop(self):
        if not self.crop_rect:
            return
        x1, y1, x2, y2 = self.crop_rect
        if (x2 - x1) <= 10 or (y2 - y1) <= 10:
            self.cancel_crop()
            return
        self.base_image = self.get_edited_image().crop((int(x1), int(y1), int(x2), int(y2)))
        self.history.clear()
        self.redo_stack.clear()
        self.selected_index = None
        self.zoom_factor = 1.0
        self._mark_dirty()
        self._reset_crop_state()
        self.redraw()
        self.canvas.config(scrollregion=(0, 0, self.base_image.width, self.base_image.height))
        if self.on_crop_complete_callback:
            self.on_crop_complete_callback(self.base_image.width, self.base_image.height)
        if self.on_tool_change_callback:
            self.on_tool_change_callback("pencil")

    def cancel_crop(self):
        self._reset_crop_state()
        self.redraw()

    def _adjust_crop(self, cx, cy):
        x1, y1, x2, y2 = self.crop_rect
        w_img, h_img = self.base_image.size
        cx = max(0, min(cx, w_img))
        cy = max(0, min(cy, h_img))
        h = self.active_handle
        dx = cx - self.start_x
        dy = cy - self.start_y
        nx1, ny1, nx2, ny2 = x1, y1, x2, y2
        if h == "MOVE":
            nx1 += dx; ny1 += dy; nx2 += dx; ny2 += dy
        elif h == "TL": nx1 += dx; ny1 += dy
        elif h == "T": ny1 += dy
        elif h == "TR": nx2 += dx; ny1 += dy
        elif h == "R": nx2 += dx
        elif h == "BR": nx2 += dx; ny2 += dy
        elif h == "B": ny2 += dy
        elif h == "BL": nx1 += dx; ny2 += dy
        elif h == "L": nx1 += dx
        nx1 = max(0, min(nx1, w_img)); nx2 = max(0, min(nx2, w_img))
        ny1 = max(0, min(ny1, h_img)); ny2 = max(0, min(ny2, h_img))
        self.crop_rect = (min(nx1, nx2), min(ny1, ny2), max(nx1, nx2), max(ny1, ny2))
        self._draw_crop_ui()

    def _draw_action(self, draw, action, offx=0, offy=0):
        """Draws a single annotation onto an ImageDraw, offset by (offx, offy).
        Used both for the final bake and for the drag overlay."""
        t = action["type"]

        if t == "highlighter":
            pts = [(p[0] - offx, p[1] - offy) for p in action["points"]]
            draw.line(pts, fill=(255, 204, 0, 100), width=18, joint="curve")
            return
        if t == "pencil":
            pts = [(p[0] - offx, p[1] - offy) for p in action["points"]]
            draw.line(pts, fill=action["color"], width=action["thickness"], joint="curve")
            return
        if t == "line":
            x1, y1, x2, y2 = action["coords"]
            draw.line([(x1 - offx, y1 - offy), (x2 - offx, y2 - offy)],
                      fill=action["color"], width=action["thickness"])
            return
        if t == "arrow":
            x1, y1, x2, y2 = action["coords"]
            dx, dy = x2 - x1, y2 - y1
            length = math.sqrt(dx*dx + dy*dy)
            if length > 0:
                ux, uy = dx/length, dy/length
                al = max(12, 10 + action["thickness"] * 2)
                aw = max(8, 6 + action["thickness"] * 1.5)
                bx, by = x2 - al * ux, y2 - al * uy
                nx, ny = -uy, ux
                lx, ly = bx + aw * nx, by + aw * ny
                rx, ry = bx - aw * nx, by - aw * ny
                draw.line([(x1 - offx, y1 - offy), (bx - offx, by - offy)],
                          fill=action["color"], width=action["thickness"])
                draw.polygon([(x2 - offx, y2 - offy), (lx - offx, ly - offy), (rx - offx, ry - offy)],
                             fill=action["color"])
            return
        if t == "rectangle":
            x1, y1, x2, y2 = action["coords"]
            draw.rectangle(
                [min(x1, x2) - offx, min(y1, y2) - offy, max(x1, x2) - offx, max(y1, y2) - offy],
                outline=action["color"], width=action["thickness"],
                fill=action["color"] if action.get("fill") == "filled" else None,
            )
            return
        if t == "circle":
            x1, y1, x2, y2 = action["coords"]
            draw.ellipse(
                [min(x1, x2) - offx, min(y1, y2) - offy, max(x1, x2) - offx, max(y1, y2) - offy],
                outline=action["color"], width=action["thickness"],
                fill=action["color"] if action.get("fill") == "filled" else None,
            )
            return
        if t == "text":
            x, y = action["coords"]
            p_font = get_pillow_font(action.get("font_family", "Arial"), action["font_size"])
            draw.text((x - offx, y - offy), action["text"], fill=action["color"], font=p_font)
            return

    def _get_edited_image_raw(self, exclude_index=None):
        """Bakes vector history onto a copy of the base image, supporting translucency."""
        if not self.base_image:
            return None
        edited = self.base_image.copy()
        draw = ImageDraw.Draw(edited)
        for i, action in enumerate(self.history):
            if i == exclude_index:
                continue
            self._draw_action(draw, action)
        return edited

    def get_edited_image(self):
        """Public API used by save/export/copy."""
        self.save_active_text()
        return self._get_edited_image_raw()

    def _baked(self):
        """Cached full-res image with all annotations, recomputed only when content changes."""
        if self._baked_cache is None or self._baked_cache[0] != self._baked_revision:
            self._baked_cache = (self._baked_revision, self._get_edited_image_raw())
        return self._baked_cache[1]

    def _photo_at_zoom(self, pil_rgba):
        """Resizes (LANCZOS for sharp zoom, fixing zoom-out blur) and converts to a PhotoImage."""
        if self.zoom_factor == 1.0:
            return pil_rgba, ImageTk.PhotoImage(pil_rgba)
        nw = max(1, int(pil_rgba.width * self.zoom_factor))
        nh = max(1, int(pil_rgba.height * self.zoom_factor))
        scaled = pil_rgba.resize((nw, nh), Image.Resampling.LANCZOS)
        return scaled, ImageTk.PhotoImage(scaled)

    def _action_bbox(self, action, pad=0):
        """Bounding box of an annotation in image coords: (x1, y1, x2, y2)."""
        t = action["type"]
        if t in ("rectangle", "circle", "line", "arrow"):
            x1, y1, x2, y2 = action["coords"]
            return min(x1, x2) - pad, min(y1, y2) - pad, max(x1, x2) + pad, max(y1, y2) + pad
        if t == "text":
            x, y = action["coords"]
            tw = len(action["text"]) * (action["font_size"] * 0.6)
            return x - pad, y - pad, x + tw + pad, y + action["font_size"] + pad
        pts = action["points"]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad
