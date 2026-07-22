import tkinter as tk
from tkinter import ttk
import math
import os
from PIL import Image, ImageDraw, ImageTk, ImageFont

def get_pillow_font(size):
    """Loads Arial Bold font from Windows or returns default."""
    font_paths = [
        "C:\\Windows\\Fonts\\arialbd.ttf", # Arial Bold
        "C:\\Windows\\Fonts\\arial.ttf",   # Arial Regular
        "C:\\Windows\\Fonts\\segoeuib.ttf",
        "C:\\Windows\\Fonts\\segoeui.ttf"
    ]
    for path in font_paths:
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
        self.zoom_factor = 1.0  # Dynamic zoom level
        
        # History
        self.history = []
        self.redo_stack = []
        
        # Select & Move state (supports text and all shapes)
        self.selected_index = None
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        
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
        
        self.canvas.bind("<Configure>", lambda e: self.redraw())

    def set_image(self, pil_image):
        self.base_image = pil_image.convert("RGBA")
        self.history.clear()
        self.redo_stack.clear()
        self.selected_index = None
        self.zoom_factor = 1.0  # Reset zoom on new capture
        self.redraw()
        self.update_scrollregion()

    def set_tool(self, tool):
        self.tool = tool
        self.selected_index = None
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

    def undo(self):
        if self.history:
            self.selected_index = None
            action = self.history.pop()
            self.redo_stack.append(action)
            self.redraw()
            if self.on_draw_callback:
                self.on_draw_callback()

    def redo(self):
        if self.redo_stack:
            self.selected_index = None
            action = self.redo_stack.pop()
            self.history.append(action)
            self.redraw()
            if self.on_draw_callback:
                self.on_draw_callback()

    def clear_annotations(self):
        if self.history:
            self.selected_index = None
            self.history.clear()
            self.redo_stack.clear()
            self.redraw()
            if self.on_draw_callback:
                self.on_draw_callback()

    def on_mouse_move(self, event):
        if self.cursor_callback:
            # Divide by zoom factor to convert mouse coords to base image coordinates
            cx = int(self.canvas.canvasx(event.x) / self.zoom_factor)
            cy = int(self.canvas.canvasy(event.y) / self.zoom_factor)
            if self.base_image:
                w, h = self.base_image.size
                cx = max(0, min(cx, w - 1))
                cy = max(0, min(cy, h - 1))
            self.cursor_callback(cx, cy)

    def on_press(self, event):
        if not self.base_image:
            return
            
        # Convert coords to base image coordinates
        self.start_x = int(self.canvas.canvasx(event.x) / self.zoom_factor)
        self.start_y = int(self.canvas.canvasy(event.y) / self.zoom_factor)
        
        # Focus canvas so keypress events register
        self.canvas.focus_set()
        
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
                self.create_text_input(ax, ay, prefill=action["text"], index=editing_index)
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
                    
                self.redraw()
                
        elif self.tool == "eraser":
            self.erase_at(cx, cy)
            
        elif self.tool in ("pencil", "highlighter"):
            color = "#FFCC00" if self.tool == "highlighter" else self.color
            thickness = 16 if self.tool == "highlighter" else self.thickness
            
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
            if self.preview_id:
                self.canvas.delete(self.preview_id)
            self.preview_id = self.canvas.create_rectangle(
                self.start_x * self.zoom_factor, self.start_y * self.zoom_factor, 
                cx * self.zoom_factor, cy * self.zoom_factor,
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
                if self.on_draw_callback:
                    self.on_draw_callback()
                    
        elif self.tool == "crop":
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
                self.base_image = self.get_edited_image().crop((crop_x1, crop_y1, crop_x2, crop_y2))
                self.history.clear()
                self.redo_stack.clear()
                self.selected_index = None
                self.zoom_factor = 1.0
                self.redraw()
                
                self.canvas.config(scrollregion=(0, 0, self.base_image.width, self.base_image.height))
                
                if self.on_crop_complete_callback:
                    self.on_crop_complete_callback(self.base_image.width, self.base_image.height)
                
                if self.on_tool_change_callback:
                    self.on_tool_change_callback("pencil")
                    
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
            self.history.append(action)
            self.redo_stack.clear()
            self.redraw()
            if self.on_draw_callback:
                self.on_draw_callback()
                
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
                    # Text: scale the font size
                    new_fs = max(6, min(120, int(round(action["font_size"] * factor))))
                    action["font_size"] = new_fs
                elif t in ("pencil", "highlighter"):
                    # Scribbles: scale all points relative to their centroid
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
                    # Vector shapes: scale endpoints relative to their bounding box center
                    x1, y1, x2, y2 = action["coords"]
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2
                    action["coords"] = (
                        cx + (x1 - cx) * factor,
                        cy + (y1 - cy) * factor,
                        cx + (x2 - cx) * factor,
                        cy + (y2 - cy) * factor
                    )
                    
                self.redraw()
                if self.on_draw_callback:
                    self.on_draw_callback()

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
            self.redraw()
            if self.on_draw_callback:
                self.on_draw_callback()

    def create_text_input(self, x, y, prefill="", index=None):
        """Spawns text entry box. Prefills and inserts at index if modifying."""
        entry_frame = tk.Frame(self.canvas, bg="#005FB8", bd=1)
        
        # Scale input font size to match canvas zoom levels dynamically
        scaled_font_size = int(round(self.font_size * self.zoom_factor))
        entry = tk.Entry(
            entry_frame, fg="#0E1013", bg="#FFFFFF",
            font=("Arial", scaled_font_size, "bold"), bd=0, width=25,
            highlightthickness=0, insertbackground="#005FB8",
            selectbackground="#E5E5E5", selectforeground="#0E1013"
        )
        entry.pack(padx=2, pady=2)
        
        if prefill:
            entry.insert(0, prefill)
            entry.select_range(0, tk.END)
            
        canvas_window_id = self.canvas.create_window(x * self.zoom_factor, y * self.zoom_factor, anchor=tk.NW, window=entry_frame)
        entry.focus_set()
        
        def save_text(event=None):
            text_str = entry.get().strip()
            self.canvas.delete(canvas_window_id)
            entry_frame.destroy()
            
            if text_str:
                action = {
                    "type": "text",
                    "coords": (x, y),
                    "text": text_str,
                    "color": self.color,
                    "font_size": self.font_size
                }
                if index is not None:
                    self.history.insert(index, action)
                else:
                    self.history.append(action)
                self.redo_stack.clear()
                self.redraw()
                if self.on_draw_callback:
                    self.on_draw_callback()
            else:
                self.redraw()
                if self.on_draw_callback:
                    self.on_draw_callback()

        entry.bind("<Return>", save_text)
        entry.bind("<FocusOut>", save_text)

    def redraw(self):
        self.canvas.delete("all")
        self.bg_image_id = None
        
        if not self.base_image:
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
            self.canvas.create_text(
                w / 2, h / 2,
                text="[ CLICK 'NEW' TO CAPTURE THE SCREEN ]",
                fill="#5F6368",
                font=("Arial", 10, "bold"),
                justify=tk.CENTER,
                tags="welcome"
            )
            return
            
        # Draw base + vector annotations
        base_rendered = self.get_edited_image()
        
        # Apply dynamic canvas zoom scaling using fast high-quality Bilinear interpolation
        if self.zoom_factor != 1.0:
            new_w = int(base_rendered.width * self.zoom_factor)
            new_h = int(base_rendered.height * self.zoom_factor)
            self.current_display_image = base_rendered.resize((new_w, new_h), Image.Resampling.BILINEAR)
        else:
            self.current_display_image = base_rendered
            
        self.bg_image_tk = ImageTk.PhotoImage(self.current_display_image)
        self.bg_image_id = self.canvas.create_image(
            0, 0, anchor=tk.NW, image=self.bg_image_tk, tags="background"
        )
        
        # If select tool is active, draw scaled dashed highlight box around currently selected shape or text
        if self.tool == "select" and self.selected_index is not None:
            if self.selected_index < len(self.history):
                action = self.history[self.selected_index]
                t = action["type"]
                bx1, by1, bx2, by2 = None, None, None, None
                
                if t == "text":
                    ax, ay = action["coords"]
                    text_h = action["font_size"]
                    text_w = len(action["text"]) * (action["font_size"] * 0.6)
                    bx1, by1, bx2, by2 = ax - 6, ay - 4, ax + text_w + 6, ay + text_h + 4
                elif t in ("pencil", "highlighter"):
                    pts = action["points"]
                    xs = [pt[0] for pt in pts]
                    ys = [pt[1] for pt in pts]
                    bx1, by1, bx2, by2 = min(xs) - 4, min(ys) - 4, max(xs) + 4, max(ys) + 4
                elif t in ("line", "arrow", "rectangle", "circle"):
                    x1, y1, x2, y2 = action["coords"]
                    bx1, by1, bx2, by2 = min(x1, x2) - 4, min(y1, y2) - 4, max(x1, x2) + 4, max(y1, y2) + 4
                    
                if bx1 is not None:
                    # Scale selection borders to match zoom factor
                    self.canvas.create_rectangle(
                        bx1 * self.zoom_factor, by1 * self.zoom_factor, 
                        bx2 * self.zoom_factor, by2 * self.zoom_factor,
                        outline="#005FB8", width=1.5, dash=(4, 4), tags="selection_box"
                    )

    def get_edited_image(self):
        """Bakes vector history onto a copy of the base image, supporting translucency."""
        if not self.base_image:
            return None
            
        edited = self.base_image.copy()
        
        for action in self.history:
            t = action["type"]
            
            if t == "highlighter":
                pts = action["points"]
                overlay = Image.new("RGBA", edited.size, (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)
                overlay_draw.line(pts, fill=(255, 204, 0, 100), width=18, joint="curve")
                edited = Image.alpha_composite(edited, overlay)
                continue
                
            draw = ImageDraw.Draw(edited)
            
            if t == "pencil":
                pts = action["points"]
                draw.line(pts, fill=action["color"], width=action["thickness"], joint="curve")
            elif t == "line":
                x1, y1, x2, y2 = action["coords"]
                draw.line([(x1, y1), (x2, y2)], fill=action["color"], width=action["thickness"])
            elif t == "arrow":
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
                    draw.line([(x1, y1), (bx, by)], fill=action["color"], width=action["thickness"])
                    draw.polygon([(x2, y2), (lx, ly), (rx, ry)], fill=action["color"])
            elif t == "rectangle":
                x1, y1, x2, y2 = action["coords"]
                rx1, ry1 = min(x1, x2), min(y1, y2)
                rx2, ry2 = max(x1, x2), max(y1, y2)
                fill_col = action["color"] if action["fill"] == "filled" else None
                draw.rectangle([rx1, ry1, rx2, ry2], outline=action["color"], width=action["thickness"], fill=fill_col)
            elif t == "circle":
                x1, y1, x2, y2 = action["coords"]
                rx1, ry1 = min(x1, x2), min(y1, y2)
                rx2, ry2 = max(x1, x2), max(y1, y2)
                fill_col = action["color"] if action["fill"] == "filled" else None
                draw.ellipse([rx1, ry1, rx2, ry2], outline=action["color"], width=action["thickness"], fill=fill_col)
            elif t == "text":
                x, y = action["coords"]
                p_font = get_pillow_font(action["font_size"])
                draw.text((x, y), action["text"], fill=action["color"], font=p_font)
                
        return edited
