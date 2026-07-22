import tkinter as tk
import time
import os
import ctypes
from PIL import Image, ImageGrab, ImageTk, ImageEnhance

# Enable DPI awareness on Windows to prevent resolution mismatch
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

class CaptureOverlay:
    def __init__(self, root, mode="free", fixed_width=800, fixed_height=600, callback=None):
        self.root = root
        self.mode = mode
        self.fixed_width = fixed_width
        self.fixed_height = fixed_height
        self.callback = callback
        
        self.original_image = None
        self.darkened_image = None
        self.darkened_tk = None
        
        self.crop_image_id = None
        self.crop_tk = None
        
        self.start_x = None
        self.start_y = None
        self.captured_image = None

        # Colors for the HUD overlay (Precision Cyan)
        self.hud_color = "#00E5FF"
        self.hud_bg = "#0E1013"

        # Hide the main window
        self.root.withdraw()
        self.root.update()
        
        # Brief pause to allow the window to fade out
        time.sleep(0.35)
        
        # Grab screen
        self.take_screenshot()
        
        # Create overlay window
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        # Disable default Windows cursor to draw our custom crosshair reticle
        self.overlay.config(cursor="none")
        
        # Canvas to display screenshot and handle selections
        self.canvas = tk.Canvas(self.overlay, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=tk.YES)
        
        # Draw background image (darkened)
        self.darkened_tk = ImageTk.PhotoImage(self.darkened_image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.darkened_tk)
        
        # Bind events
        self.overlay.bind("<Escape>", self.cancel)
        self.overlay.bind("<Motion>", self.on_mouse_move)
        
        if self.mode == "fixed":
            self.overlay.bind("<Button-1>", self.capture_fixed_box)
        else:
            self.canvas.bind("<ButtonPress-1>", self.on_press)
            self.canvas.bind("<B1-Motion>", self.on_drag)
            self.canvas.bind("<ButtonRelease-1>", self.on_release)

    def take_screenshot(self):
        """Grabs the current screen screen contents."""
        try:
            self.original_image = ImageGrab.grab(all_screens=True)
        except Exception:
            self.original_image = ImageGrab.grab()
            
        # Create a darkened version of the image
        enhancer = ImageEnhance.Brightness(self.original_image)
        self.darkened_image = enhancer.enhance(0.4) # Slightly darker for higher contrast overlay

    def draw_hud_elements(self, cx, cy):
        """Draws the viewfinder crosshair and coordinates near the cursor."""
        self.canvas.delete("hud")
        
        # 1. Custom crosshair reticle (with a gap in the center)
        self.canvas.create_line(cx - 15, cy, cx - 4, cy, fill=self.hud_color, width=1, tags="hud")
        self.canvas.create_line(cx + 4, cy, cx + 15, cy, fill=self.hud_color, width=1, tags="hud")
        self.canvas.create_line(cx, cy - 15, cx, cy - 4, fill=self.hud_color, width=1, tags="hud")
        self.canvas.create_line(cx, cy + 4, cx, cy + 15, fill=self.hud_color, width=1, tags="hud")
        
        # 2. Text readout box (X/Y coordinates)
        coord_text = f"X:{cx:04d}\nY:{cy:04d}"
        text_id = self.canvas.create_text(
            cx + 18, cy + 18, text=coord_text, fill=self.hud_color, 
            font=("Consolas", 8, "bold"), anchor=tk.NW, tags="hud"
        )
        
        # Draw background capsule for text readability
        try:
            bbox = self.canvas.bbox(text_id)
            bg_id = self.canvas.create_rectangle(
                bbox[0] - 5, bbox[1] - 3, bbox[2] + 5, bbox[3] + 3,
                fill=self.hud_bg, outline=self.hud_color, width=1, tags="hud"
            )
            self.canvas.tag_raise(text_id)
        except Exception:
            pass

    def draw_crop_hud(self, x1, y1, x2, y2):
        """Draws gridlines, border lines, and dimension labels for the selected crop box."""
        self.canvas.delete("crop_ui")
        
        width = x2 - x1
        height = y2 - y1
        if width <= 0 or height <= 0:
            return
            
        # 1. Border line (Cyan, dashed)
        self.canvas.create_rectangle(
            x1, y1, x2, y2, outline=self.hud_color, width=1.5, dash=(6, 4), tags="crop_ui"
        )
        
        # 2. Rule of Thirds Gridlines (subtle dashes)
        dx = width / 3
        dy = height / 3
        
        # Vertical grids
        self.canvas.create_line(x1 + dx, y1, x1 + dx, y2, fill=self.hud_color, dash=(2, 6), width=1, tags="crop_ui")
        self.canvas.create_line(x1 + 2 * dx, y1, x1 + 2 * dx, y2, fill=self.hud_color, dash=(2, 6), width=1, tags="crop_ui")
        
        # Horizontal grids
        self.canvas.create_line(x1, y1 + dy, x2, y1 + dy, fill=self.hud_color, dash=(2, 6), width=1, tags="crop_ui")
        self.canvas.create_line(x1, y1 + 2 * dy, x2, y1 + 2 * dy, fill=self.hud_color, dash=(2, 6), width=1, tags="crop_ui")
        
        # 3. Dynamic Dimension label capsule on the top edge
        dim_text = f" {width} x {height} px "
        label_x = (x1 + x2) / 2
        label_y = y1 - 16 if y1 > 30 else y1 + 16 # Adjust if too close to top edge
        
        lbl_id = self.canvas.create_text(
            label_x, label_y, text=dim_text, fill=self.hud_color,
            font=("Consolas", 9, "bold"), tags="crop_ui"
        )
        
        try:
            l_box = self.canvas.bbox(lbl_id)
            self.canvas.create_rectangle(
                l_box[0] - 6, l_box[1] - 3, l_box[2] + 6, l_box[3] + 3,
                fill=self.hud_bg, outline=self.hud_color, width=1, tags="crop_ui"
            )
            self.canvas.tag_raise(lbl_id)
        except Exception:
            pass

    def on_mouse_move(self, event):
        """Called on cursor motion; manages reticle HUD and fixed-size preview."""
        cx, cy = event.x, event.y
        self.draw_hud_elements(cx, cy)
        
        if self.mode == "fixed":
            w, h = self.fixed_width, self.fixed_height
            screen_w = self.original_image.width
            screen_h = self.original_image.height
            
            # Position box centered at cursor, constrained within monitor
            x1 = max(0, min(cx - w // 2, screen_w - w))
            y1 = max(0, min(cy - h // 2, screen_h - h))
            x2 = x1 + w
            y2 = y1 + h
            
            # Render crop preview image
            cropped = self.original_image.crop((x1, y1, x2, y2))
            self.crop_tk = ImageTk.PhotoImage(cropped)
            
            if self.crop_image_id is not None:
                self.canvas.itemconfig(self.crop_image_id, image=self.crop_tk)
                self.canvas.coords(self.crop_image_id, x1, y1)
            else:
                self.crop_image_id = self.canvas.create_image(x1, y1, anchor=tk.NW, image=self.crop_tk)
                
            self.draw_crop_hud(x1, y1, x2, y2)
            
            # Make sure HUD reticle stays on top of everything
            self.canvas.tag_raise("crop_ui")
            self.canvas.tag_raise("hud")

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y

    def on_drag(self, event):
        if self.start_x is None or self.start_y is None:
            return
            
        cur_x, cur_y = event.x, event.y
        screen_w = self.original_image.width
        screen_h = self.original_image.height
        
        cur_x = max(0, min(cur_x, screen_w))
        cur_y = max(0, min(cur_y, screen_h))
        
        x1 = min(self.start_x, cur_x)
        y1 = min(self.start_y, cur_y)
        x2 = max(self.start_x, cur_x)
        y2 = max(self.start_y, cur_y)
        
        # Render the viewfinder elements
        self.draw_hud_elements(cur_x, cur_y)
        
        if (x2 - x1) > 0 and (y2 - y1) > 0:
            # Crop clear image portion
            cropped = self.original_image.crop((x1, y1, x2, y2))
            self.crop_tk = ImageTk.PhotoImage(cropped)
            
            if self.crop_image_id is not None:
                self.canvas.itemconfig(self.crop_image_id, image=self.crop_tk)
                self.canvas.coords(self.crop_image_id, x1, y1)
            else:
                self.crop_image_id = self.canvas.create_image(x1, y1, anchor=tk.NW, image=self.crop_tk)
                
            self.draw_crop_hud(x1, y1, x2, y2)
            
            # Layer ordering: background image < crop image < crop boxes < HUD crosshair
            self.canvas.tag_raise("crop_ui")
            self.canvas.tag_raise("hud")

    def on_release(self, event):
        if self.start_x is None or self.start_y is None:
            return
            
        cur_x, cur_y = event.x, event.y
        screen_w = self.original_image.width
        screen_h = self.original_image.height
        
        cur_x = max(0, min(cur_x, screen_w))
        cur_y = max(0, min(cur_y, screen_h))
        
        x1 = min(self.start_x, cur_x)
        y1 = min(self.start_y, cur_y)
        x2 = max(self.start_x, cur_x)
        y2 = max(self.start_y, cur_y)
        
        if (x2 - x1) > 5 and (y2 - y1) > 5:
            self.captured_image = self.original_image.crop((x1, y1, x2, y2))
            
        self.close()

    def capture_fixed_box(self, event):
        """Captures the fixed size box area."""
        cx, cy = event.x, event.y
        w, h = self.fixed_width, self.fixed_height
        screen_w = self.original_image.width
        screen_h = self.original_image.height
        
        x1 = max(0, min(cx - w // 2, screen_w - w))
        y1 = max(0, min(cy - h // 2, screen_h - h))
        x2 = x1 + w
        y2 = y1 + h
        
        self.captured_image = self.original_image.crop((x1, y1, x2, y2))
        self.close()

    def cancel(self, event=None):
        self.captured_image = None
        self.close()

    def close(self):
        # Restore cursor and destroy overlay
        self.overlay.destroy()
        
        # Show main window again
        self.root.deiconify()
        self.root.update()
        
        if self.callback:
            self.callback(self.captured_image)
