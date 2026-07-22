import tkinter as tk
from tkinter import messagebox, filedialog, ttk, colorchooser
import os
import time
import re
from PIL import Image, ImageTk

# Import local components
from config import AppConfig
from capture import CaptureOverlay
from canvas_editor import CanvasEditor
from icons import get_icon

class StyledEntry(tk.Entry):
    """Custom flat entry widget with dynamic themes, Arial font, and active highlights."""
    def __init__(self, parent, **kwargs):
        bg = kwargs.pop("bg", "#FFFFFF")
        fg = kwargs.pop("fg", "#0E1013")
        insertbackground = kwargs.pop("insertbackground", "#005FB8")
        font = kwargs.pop("font", ("Arial", 9))
        
        super().__init__(
            parent, bg=bg, fg=fg, insertbackground=insertbackground, font=font,
            bd=0, highlightthickness=1, highlightbackground="#D0D0D0",
            highlightcolor="#005FB8", **kwargs
        )

class SnippingToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Snipping Tool")
        
        # Start compact horizontal launcher pill - expanded to 900px to fit tools neatly
        self.root.geometry("900x72")
        self.root.resizable(True, True)
        
        # Load configuration settings
        self.config = AppConfig()
        
        # Arial Font System definitions (decent bold/regular combinations)
        self.font_main = ("Arial", 9)
        self.font_bold = ("Arial", 9, "bold")
        self.font_title = ("Arial", 10, "bold")
        self.font_status = ("Arial", 8, "bold")
        self.font_status_italic = ("Arial", 8, "italic")
        
        # Load dynamic theme colors from config
        self.apply_theme_tokens()
        
        self.root.configure(bg=self.bg_color)
        
        # Configure TTK Scrollbars and dropdowns
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        # Initialize tool list
        self.tool_buttons = {}
        
        self.build_ui()
        self.load_settings_into_ui()
        self.apply_theme_colors()
        self.update_toolbar_state()
        
        # Bind keyboard shortcuts
        self.root.bind("<Control-z>", lambda e: self.canvas_editor.undo())
        self.root.bind("<Control-y>", lambda e: self.canvas_editor.redo())
        self.root.bind("<Control-s>", lambda e: self.save_quick())
        self.root.bind("<Control-c>", lambda e: self.copy_to_clipboard())
        self.root.bind("<Control-Shift-S>", lambda e: self.save_as())
        self.root.bind("<Control-n>", lambda e: self.start_capture())

    def apply_theme_tokens(self):
        """Loads Light or Dark theme color tokens dynamically."""
        self.theme_name = self.config.get("theme")
        if self.theme_name == "dark":
            self.bg_color = "#1E1E1E"       # Charcoal black background
            self.panel_bg = "#2D2D2D"       # Dark grey panels
            self.accent_color = "#0078D4"   # Cobalt active accent
            self.btn_bg = "#3D3D3D"         # Hover dark grey
            self.border_color = "#444444"   # Dark dividers
            self.text_color = "#FFFFFF"     # White text
            self.text_muted = "#AAAAAA"     # Muted light grey
            self.canvas_bg = "#252525"      # Dark editor workspace canvas
        else:
            self.bg_color = "#FFFFFF"       # Solid white background
            self.panel_bg = "#F3F3F3"       # Clean light grey toolbar
            self.accent_color = "#005FB8"   # High-contrast Cobalt Blue active accent
            self.btn_bg = "#EAEAEA"         # Hover button grey
            self.border_color = "#E5E5E5"   # Thin dividers
            self.text_color = "#0E1013"     # Dark charcoal text
            self.text_muted = "#5F6368"     # Muted grey
            self.canvas_bg = "#EAEAEA"      # Light grey canvas workspace

    def apply_theme_colors(self):
        """Recursively updates all UI widgets, dropdowns, and canvas backgrounds to the selected theme."""
        self.apply_theme_tokens()
        
        # Update standard widgets recursively
        self.update_theme_recursively(self.root)
        
        # Update global ttk style settings
        self.style.configure(".", background=self.panel_bg, foreground=self.text_color, font=self.font_main)
        self.style.configure("TLabel", background=self.panel_bg, foreground=self.text_color, font=self.font_bold)
        self.style.configure(
            "TCombobox", 
            fieldbackground="#FFFFFF" if self.theme_name == "light" else "#3D3D3D", 
            background=self.panel_bg, 
            foreground=self.text_color, 
            arrowcolor=self.text_color, 
            bd=0, 
            font=self.font_main
        )
        self.style.map(
            "TCombobox", 
            fieldbackground=[("readonly", "#FFFFFF" if self.theme_name == "light" else "#3D3D3D")], 
            foreground=[("readonly", self.text_color)]
        )
        
        self.style.configure(
            "Vertical.TScrollbar", gripcount=0, background=self.btn_bg, 
            troughcolor=self.bg_color, bordercolor=self.border_color, lightcolor=self.btn_bg, darkcolor=self.btn_bg
        )
        self.style.configure(
            "Horizontal.TScrollbar", gripcount=0, background=self.btn_bg, 
            troughcolor=self.bg_color, bordercolor=self.border_color, lightcolor=self.btn_bg, darkcolor=self.btn_bg
        )
        
        # Update canvas editor background
        self.canvas_editor.canvas.configure(bg=self.canvas_bg)
        
        # Reload vector icons in the correct theme color
        self.update_icons()

    def update_theme_recursively(self, widget):
        """Walks the Tkinter widget hierarchy updating colors based on tagged roles."""
        w_class = widget.winfo_class()
        
        if w_class == "Frame":
            if widget == self.root or widget == self.canvas_editor:
                widget.configure(bg=self.bg_color)
            elif hasattr(widget, "is_divider") and widget.is_divider:
                widget.configure(bg=self.border_color)
            elif hasattr(widget, "is_color_container") and widget.is_color_container:
                widget.configure(bg=self.panel_bg)
            else:
                widget.configure(bg=self.panel_bg)
                
        elif w_class == "Label":
            if hasattr(widget, "is_muted") and widget.is_muted:
                widget.configure(bg=self.panel_bg, fg=self.text_muted)
            else:
                widget.configure(bg=self.panel_bg, fg=self.text_color)
                
        elif w_class == "Button":
            if widget == self.btn_new:
                widget.configure(bg=self.accent_color, fg="#FFFFFF")
            elif hasattr(widget, "is_swatch") and widget.is_swatch:
                pass # Swatches have distinct solid colors
            elif hasattr(widget, "is_picker") and widget.is_picker:
                widget.configure(bg=self.btn_bg, fg=self.accent_color)
            else:
                widget.configure(bg=self.panel_bg, fg=self.text_color, activebackground=self.btn_bg, activeforeground=self.text_color)
                
        elif isinstance(widget, StyledEntry):
            widget.configure(bg="#FFFFFF" if self.theme_name == "light" else "#3D3D3D", fg=self.text_color)
            
        for child in widget.winfo_children():
            self.update_theme_recursively(child)

    def build_ui(self):
        """Builds the compact horizontal toolbar with Arial typography."""
        # Top toolbar frame container
        self.toolbar_frame = tk.Frame(self.root, bg=self.panel_bg, bd=0, height=50)
        self.toolbar_frame.pack(side=tk.TOP, fill=tk.X)
        self.toolbar_frame.pack_propagate(False)
        
        # Bottom border line for toolbar
        self.border_h = tk.Frame(self.root, bg=self.border_color, height=1)
        self.border_h.pack(side=tk.TOP, fill=tk.X)
        self.border_h.is_divider = True
        
        # --- LEFT: Launch & Mode ---
        left_grp = tk.Frame(self.toolbar_frame, bg=self.panel_bg)
        left_grp.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # New Crop button with white icon on active Cobalt background
        self.icon_camera = get_icon("camera", "#FFFFFF", size=(16, 16))
        self.btn_new = tk.Button(
            left_grp, text=" New", image=self.icon_camera, compound=tk.LEFT,
            command=self.start_capture, bg=self.accent_color, fg="#FFFFFF",
            activebackground="#004C94", activeforeground="#FFFFFF", bd=0,
            relief="flat", padx=14, pady=5, font=self.font_bold
        )
        self.btn_new.pack(side=tk.LEFT, padx=5, pady=8)
        
        self.mode_var = tk.StringVar(value=self.config.get("default_capture_mode"))
        self.cb_mode = ttk.Combobox(left_grp, textvariable=self.mode_var, values=["free", "fixed"], width=6, state="readonly")
        self.cb_mode.pack(side=tk.LEFT, padx=5, pady=8)
        self.cb_mode.bind("<<ComboboxSelected>>", self.on_capture_mode_changed)
        
        self.lbl_w = tk.Label(left_grp, text="W:", bg=self.panel_bg, fg=self.text_muted, font=self.font_bold)
        self.lbl_w.pack(side=tk.LEFT, padx=(5, 1))
        self.lbl_w.is_muted = True
        self.entry_w = StyledEntry(left_grp, width=4)
        self.entry_w.insert(0, str(self.config.get("fixed_width")))
        self.entry_w.pack(side=tk.LEFT, padx=2, pady=8)
        
        self.lbl_h = tk.Label(left_grp, text="H:", bg=self.panel_bg, fg=self.text_muted, font=self.font_bold)
        self.lbl_h.pack(side=tk.LEFT, padx=(5, 1))
        self.lbl_h.is_muted = True
        self.entry_h = StyledEntry(left_grp, width=4)
        self.entry_h.insert(0, str(self.config.get("fixed_height")))
        self.entry_h.pack(side=tk.LEFT, padx=2, pady=8)
        
        self.on_capture_mode_changed()
        
        # --- MIDDLE: Image Tools (High Contrast, Bold Icons) ---
        self.mid_grp = tk.Frame(self.toolbar_frame, bg=self.panel_bg)
        self.mid_grp.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Vertical divider line
        div1 = tk.Frame(self.mid_grp, bg=self.border_color, width=1)
        div1.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=6)
        div1.is_divider = True
        
        # Spaced inline drawing & editing tools (including select & Crop tools)
        tools = [
            ("select", "pointer", "Select & Move Text"),
            ("pencil", "pencil", "Pencil Brush"),
            ("highlighter", "highlighter", "Translucent Highlighter"),
            ("eraser", "eraser", "Object Eraser"),
            ("text", "text", "Add Text Annotations"),
            ("crop", "crop", "Crop Snippet Area"),
            ("line", "line", "Straight Line"),
            ("arrow", "arrow", "Vector Arrow"),
            ("rectangle", "rectangle", "Rectangle outline"),
            ("circle", "circle", "Circle/Ellipse")
        ]
        
        for tool_name, icon_name, tooltip in tools:
            btn = self.make_icon_button(self.mid_grp, icon_name, lambda t=tool_name: self.set_tool(t))
            btn.pack(side=tk.LEFT, padx=1, pady=5)
            self.tool_buttons[tool_name] = btn
            
        # Divider
        div2 = tk.Frame(self.mid_grp, bg=self.border_color, width=1)
        div2.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=6)
        div2.is_divider = True
        
        # Stroke Size selector
        self.thickness_var = tk.IntVar(value=self.config.get("last_thickness"))
        self.cb_thickness = ttk.Combobox(self.mid_grp, textvariable=self.thickness_var, values=[1, 2, 3, 5, 8, 12, 16, 24], width=3, state="readonly")
        self.cb_thickness.pack(side=tk.LEFT, padx=2, pady=8)
        self.cb_thickness.bind("<<ComboboxSelected>>", lambda e: self.on_style_changed())
        
        # Shape Fill selector
        self.fill_var = tk.StringVar(value=self.config.get("last_fill_mode"))
        self.cb_fill = ttk.Combobox(self.mid_grp, textvariable=self.fill_var, values=["hollow", "filled"], width=6, state="readonly")
        self.cb_fill.pack(side=tk.LEFT, padx=2, pady=8)
        self.cb_fill.bind("<<ComboboxSelected>>", lambda e: self.on_style_changed())
        
        # Font family dropdown selector
        self.font_family_var = tk.StringVar(value=self.config.get("last_font_family") or "Arial")
        self.cb_font_family = ttk.Combobox(self.mid_grp, textvariable=self.font_family_var, values=["Arial", "Times New Roman", "Courier New", "Georgia", "Segoe UI", "Verdana", "Impact"], width=12, state="readonly")
        self.cb_font_family.pack(side=tk.LEFT, padx=3, pady=8)
        self.cb_font_family.bind("<<ComboboxSelected>>", lambda e: self.on_style_changed())
        
        # Text size controls (A- / A+ buttons) & dropdown
        self.btn_font_dec = tk.Button(
            self.mid_grp, text="A-", command=self.font_size_decrease, bg=self.panel_bg,
            activebackground=self.btn_bg, fg=self.text_color, bd=0, relief="flat",
            padx=6, pady=4, font=self.font_bold
        )
        self.btn_font_dec.pack(side=tk.LEFT, padx=(3, 1), pady=8)
        
        self.font_size_var = tk.IntVar(value=self.config.get("last_font_size"))
        self.cb_font_size = ttk.Combobox(self.mid_grp, textvariable=self.font_size_var, values=[8, 10, 12, 14, 16, 20, 24, 32, 40, 48, 72], width=3, state="readonly")
        self.cb_font_size.pack(side=tk.LEFT, padx=1, pady=8)
        self.cb_font_size.bind("<<ComboboxSelected>>", lambda e: self.on_style_changed())
        
        self.btn_font_inc = tk.Button(
            self.mid_grp, text="A+", command=self.font_size_increase, bg=self.panel_bg,
            activebackground=self.btn_bg, fg=self.text_color, bd=0, relief="flat",
            padx=6, pady=4, font=self.font_bold
        )
        self.btn_font_inc.pack(side=tk.LEFT, padx=(1, 3), pady=8)
        
        # Circular Color Palette
        div3 = tk.Frame(self.mid_grp, bg=self.border_color, width=1)
        div3.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=6)
        div3.is_divider = True
        
        self.colors_container = tk.Frame(self.mid_grp, bg=self.panel_bg)
        self.colors_container.pack(side=tk.LEFT, padx=3, pady=8)
        self.colors_container.is_color_container = True
        
        swatches = ["#FF3B30", "#FFCC00", "#34C759", "#007AFF", "#00E5FF", "#0E1013"]
        for col in swatches:
            c_btn = tk.Button(
                self.colors_container, bg=col, activebackground=col, bd=1, relief="solid",
                width=1, height=1, command=lambda c=col: self.set_color(c), highlightthickness=0
            )
            c_btn.pack(side=tk.LEFT, padx=1)
            c_btn.is_swatch = True
            
        self.btn_picker = tk.Button(
            self.colors_container, text="+", bg=self.btn_bg, fg=self.accent_color,
            font=self.font_bold, bd=1, relief="solid", width=2, height=1,
            command=self.choose_custom_color, highlightthickness=0
        )
        self.btn_picker.pack(side=tk.LEFT, padx=(2, 0))
        self.btn_picker.is_picker = True
        
        # --- RIGHT: Actions ---
        self.right_grp = tk.Frame(self.toolbar_frame, bg=self.panel_bg)
        self.right_grp.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        
        self.btn_settings = self.make_icon_button(self.right_grp, "settings", self.open_settings_dialog)
        self.btn_settings.pack(side=tk.RIGHT, padx=1, pady=5)
        
        div4 = tk.Frame(self.right_grp, bg=self.border_color, width=1)
        div4.pack(side=tk.RIGHT, fill=tk.Y, padx=4, pady=6)
        div4.is_divider = True
        
        self.btn_save_as = self.make_icon_button(self.right_grp, "save", self.save_as)
        self.btn_save_as.pack(side=tk.RIGHT, padx=1, pady=5)
        
        self.btn_copy = self.make_icon_button(self.right_grp, "copy", self.copy_to_clipboard)
        self.btn_copy.pack(side=tk.RIGHT, padx=1, pady=5)
        
        self.btn_clear = self.make_icon_button(self.right_grp, "clear", self.clear_canvas)
        self.btn_clear.pack(side=tk.RIGHT, padx=1, pady=5)
        
        div5 = tk.Frame(self.right_grp, bg=self.border_color, width=1)
        div5.pack(side=tk.RIGHT, fill=tk.Y, padx=4, pady=6)
        div5.is_divider = True
        
        # Zoom Controls
        self.btn_zoom_in = self.make_icon_button(self.right_grp, "zoom_in", self.zoom_in)
        self.btn_zoom_in.pack(side=tk.RIGHT, padx=1, pady=5)
        
        self.btn_zoom_out = self.make_icon_button(self.right_grp, "zoom_out", self.zoom_out)
        self.btn_zoom_out.pack(side=tk.RIGHT, padx=1, pady=5)
        
        div_z = tk.Frame(self.right_grp, bg=self.border_color, width=1)
        div_z.pack(side=tk.RIGHT, fill=tk.Y, padx=4, pady=6)
        div_z.is_divider = True
        
        self.btn_redo = self.make_icon_button(self.right_grp, "redo", self.redo)
        self.btn_redo.pack(side=tk.RIGHT, padx=1, pady=5)
        
        self.btn_undo = self.make_icon_button(self.right_grp, "undo", self.undo)
        self.btn_undo.pack(side=tk.RIGHT, padx=1, pady=5)
        
        # Center Canvas Editor Frame
        self.canvas_editor = CanvasEditor(self.root, bg=self.bg_color)
        self.canvas_editor.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.canvas_editor.on_draw_callback = self.update_actions_buttons_state
        self.canvas_editor.cursor_callback = self.update_coordinates_status
        self.canvas_editor.on_crop_complete_callback = self.on_crop_complete
        self.canvas_editor.on_tool_change_callback = self.set_tool
        
        # Bottom Status Bar Frame
        self.status_bar = tk.Frame(self.root, bg=self.panel_bg, bd=0, height=24)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.border_s = tk.Frame(self.status_bar, bg=self.border_color, height=1)
        self.border_s.pack(side=tk.TOP, fill=tk.X)
        self.border_s.is_divider = True
        
        self.lbl_status_tool = tk.Label(self.status_bar, text="TOOL: PENCIL", bg=self.panel_bg, fg=self.text_color, font=self.font_bold)
        self.lbl_status_tool.pack(side=tk.LEFT, padx=15, pady=3)
        
        self.lbl_status_zoom = tk.Label(self.status_bar, text="ZOOM: 100%", bg=self.panel_bg, fg=self.text_color, font=self.font_bold)
        self.lbl_status_zoom.pack(side=tk.LEFT, padx=20, pady=3)
        
        self.lbl_status_dims = tk.Label(self.status_bar, text="RESOLUTION: 0 x 0 PX", bg=self.panel_bg, fg=self.text_color, font=self.font_bold)
        self.lbl_status_dims.pack(side=tk.LEFT, padx=20, pady=3)
        
        self.lbl_status_coords = tk.Label(self.status_bar, text="COORDS: 0, 0", bg=self.panel_bg, fg=self.text_color, font=self.font_bold)
        self.lbl_status_coords.pack(side=tk.LEFT, padx=20, pady=3)
        
        self.lbl_status_path = tk.Label(
            self.status_bar, 
            text=f"SAVE DEST: {self.config.get('default_save_path')}", 
            bg=self.panel_bg, fg=self.text_muted, font=self.font_status_italic
        )
        self.lbl_status_path.pack(side=tk.RIGHT, padx=15, pady=3)
        self.lbl_status_path.is_muted = True
        
        self.update_actions_buttons_state()

    def make_icon_button(self, parent, icon_name, command):
        """Builds a flat button styled dynamically based on theme icons."""
        icon_col = "#333333" if self.theme_name == "light" else "#DDDDDD"
        icon = get_icon(icon_name, icon_col)
        btn = tk.Button(
            parent, image=icon, command=command, bg=self.panel_bg,
            activebackground=self.btn_bg, bd=0, relief="flat", padx=8, pady=8
        )
        btn.image = icon # Prevent GC
        btn.bind("<Enter>", lambda e: btn.config(bg=self.btn_bg))
        btn.bind("<Leave>", lambda e: btn.config(bg=self.panel_bg if not self.is_active_tool(icon_name) else self.btn_bg))
        return btn

    def update_icons(self):
        """Refreshes all toolbar icons to match Light/Dark high contrast specifications."""
        icon_col = "#333333" if self.theme_name == "light" else "#DDDDDD"
        
        self.icon_camera = get_icon("camera", "#FFFFFF", size=(16, 16))
        self.btn_new.config(image=self.icon_camera)
        
        # Refresh utilities on the right
        for button, name in [
            (self.btn_settings, "settings"),
            (self.btn_save_as, "save"),
            (self.btn_copy, "copy"),
            (self.btn_clear, "clear"),
            (self.btn_zoom_in, "zoom_in"),
            (self.btn_zoom_out, "zoom_out"),
            (self.btn_redo, "redo"),
            (self.btn_undo, "undo")
        ]:
            icon = get_icon(name, icon_col)
            button.config(image=icon)
            button.image = icon
            
        # Refresh drawing tools active/inactive indicators
        self.set_tool(self.config.get("last_tool"))

    def is_active_tool(self, name):
        return self.config.get("last_tool") == name

    def load_settings_into_ui(self):
        self.set_tool(self.config.get("last_tool"))
        self.set_color(self.config.get("last_color"))
        self.canvas_editor.set_thickness(self.thickness_var.get())
        self.canvas_editor.set_fill_mode(self.fill_var.get())
        self.canvas_editor.set_font_size(self.font_size_var.get())
        self.canvas_editor.set_font_family(self.font_family_var.get())

    def on_capture_mode_changed(self, event=None):
        mode = self.mode_var.get()
        self.config.set("default_capture_mode", mode)
        if mode == "fixed":
            self.entry_w.config(state="normal", bg="#FFFFFF" if self.theme_name == "light" else "#3D3D3D", fg=self.text_color)
            self.entry_h.config(state="normal", bg="#FFFFFF" if self.theme_name == "light" else "#3D3D3D", fg=self.text_color)
            self.lbl_w.config(foreground=self.text_color)
            self.lbl_h.config(foreground=self.text_color)
        else:
            self.entry_w.config(state="disabled", bg=self.panel_bg, fg="#D0D0D0" if self.theme_name == "light" else "#666666")
            self.entry_h.config(state="disabled", bg=self.panel_bg, fg="#D0D0D0" if self.theme_name == "light" else "#666666")
            self.lbl_w.config(foreground="#D0D0D0" if self.theme_name == "light" else "#666666")
            self.lbl_h.config(foreground="#D0D0D0" if self.theme_name == "light" else "#666666")

    def on_style_changed(self):
        self.config.set("last_thickness", self.thickness_var.get())
        self.config.set("last_fill_mode", self.fill_var.get())
        self.config.set("last_font_size", self.font_size_var.get())
        self.config.set("last_font_family", self.font_family_var.get())
        
        self.canvas_editor.set_thickness(self.thickness_var.get())
        self.canvas_editor.set_fill_mode(self.fill_var.get())
        self.canvas_editor.set_font_size(self.font_size_var.get())
        self.canvas_editor.set_font_family(self.font_family_var.get())

    def set_tool(self, tool_name):
        self.config.set("last_tool", tool_name)
        self.canvas_editor.set_tool(tool_name)
        
        # Interactive status guides
        if tool_name == "select":
            self.lbl_status_tool.config(text="TOOL: SELECT (CLICK & DRAG ELEMENTS TO MOVE / USE ARROW KEYS OR + / - KEY)")
        elif tool_name == "text":
            self.lbl_status_tool.config(text="TOOL: TEXT (CLICK CANVAS TO TYPE / CLICK TEXT TO EDIT)")
        elif tool_name == "crop":
            self.lbl_status_tool.config(text="TOOL: CROP (DRAG BOX & RELEASE TO CROP)")
        else:
            self.lbl_status_tool.config(text=f"TOOL: {tool_name.upper()}")
        
        icon_inactive_col = "#333333" if self.theme_name == "light" else "#DDDDDD"
        # Highlight active tool button with Cobalt icon
        for name, button in self.tool_buttons.items():
            if name == tool_name:
                icon_active = get_icon(name, self.accent_color)
                button.config(bg=self.btn_bg, image=icon_active)
                button.image = icon_active
            else:
                icon_inactive = get_icon(name, icon_inactive_col)
                button.config(bg=self.panel_bg, image=icon_inactive)
                button.image = icon_inactive

    def set_color(self, color_hex):
        self.config.set("last_color", color_hex)
        self.canvas_editor.set_color(color_hex)
        self.btn_picker.config(fg=color_hex)

    def choose_custom_color(self):
        color = colorchooser.askcolor(initialcolor=self.config.get("last_color"), title="Select Custom Color")
        if color[1]:
            self.set_color(color[1])

    def font_size_decrease(self):
        curr = self.font_size_var.get()
        presets = [8, 10, 12, 14, 16, 20, 24, 32, 40, 48, 72]
        lower = [p for p in presets if p < curr]
        new_size = lower[-1] if lower else max(6, curr - 2)
        self.font_size_var.set(new_size)
        self.on_style_changed()

    def font_size_increase(self):
        curr = self.font_size_var.get()
        presets = [8, 10, 12, 14, 16, 20, 24, 32, 40, 48, 72]
        higher = [p for p in presets if p > curr]
        new_size = higher[0] if higher else min(96, curr + 4)
        self.font_size_var.set(new_size)
        self.on_style_changed()

    def zoom_in(self):
        self.canvas_editor.zoom_in()
        self.update_actions_buttons_state()

    def zoom_out(self):
        self.canvas_editor.zoom_out()
        self.update_actions_buttons_state()

    def start_capture(self):
        mode = self.mode_var.get()
        w, h = 800, 600
        
        if mode == "fixed":
            try:
                w = int(self.entry_w.get())
                h = int(self.entry_h.get())
                if w <= 0 or h <= 0:
                    raise ValueError
                self.config.set("fixed_width", w)
                self.config.set("fixed_height", h)
            except ValueError:
                messagebox.showerror("Invalid Size", "Please enter positive integer values for width and height.")
                return
                
        CaptureOverlay(self.root, mode=mode, fixed_width=w, fixed_height=h, callback=self.on_capture_complete)

    def on_capture_complete(self, image):
        if image:
            self.canvas_editor.set_image(image)
            self.on_crop_complete(image.width, image.height)
            
            self.update_toolbar_state()
            self.update_actions_buttons_state()
            
            self.root.lift()
            self.root.focus_force()

    def on_crop_complete(self, w, h):
        self.lbl_status_dims.config(text=f"RESOLUTION: {w} x {h} PX")
        self.lbl_status_zoom.config(text=f"ZOOM: {int(round(self.canvas_editor.zoom_factor * 100))}%")
        win_w = max(900, w + 30)
        win_h = h + 115
        self.root.geometry(f"{win_w}x{win_h}")

    def undo(self):
        self.canvas_editor.undo()

    def redo(self):
        self.canvas_editor.redo()

    def clear_canvas(self):
        if messagebox.askyesno("Reset Snippet Workspace", "Are you sure you want to discard this screenshot and reset the window?"):
            self.reset_to_compact()

    def reset_to_compact(self):
        self.canvas_editor.base_image = None
        self.canvas_editor.history.clear()
        self.canvas_editor.redo_stack.clear()
        self.canvas_editor.redraw()
        
        self.root.geometry("900x72")
        self.lbl_status_dims.config(text="RESOLUTION: 0 x 0 PX")
        self.lbl_status_zoom.config(text="ZOOM: 100%")
        self.update_toolbar_state()
        self.update_actions_buttons_state()

    def update_toolbar_state(self):
        has_img = self.canvas_editor.base_image is not None
        
        if has_img:
            self.mid_grp.pack(side=tk.LEFT, fill=tk.Y, padx=5)
            self.btn_clear.pack(side=tk.RIGHT, padx=1, pady=5)
            self.btn_undo.pack(side=tk.RIGHT, padx=1, pady=5)
            self.btn_redo.pack(side=tk.RIGHT, padx=1, pady=5)
            self.btn_zoom_in.pack(side=tk.RIGHT, padx=1, pady=5)
            self.btn_zoom_out.pack(side=tk.RIGHT, padx=1, pady=5)
            self.btn_copy.pack(side=tk.RIGHT, padx=1, pady=5)
            self.btn_save_as.pack(side=tk.RIGHT, padx=1, pady=5)
        else:
            self.mid_grp.pack_forget()
            self.btn_clear.pack_forget()
            self.btn_undo.pack_forget()
            self.btn_redo.pack_forget()
            self.btn_zoom_in.pack_forget()
            self.btn_zoom_out.pack_forget()
            self.btn_copy.pack_forget()
            self.btn_save_as.pack_forget()

    def update_actions_buttons_state(self):
        has_history = len(self.canvas_editor.history) > 0
        has_redo = len(self.canvas_editor.redo_stack) > 0
        
        self.btn_undo.config(state="normal" if has_history else "disabled")
        self.btn_redo.config(state="normal" if has_redo else "disabled")
        self.btn_clear.config(state="normal" if self.canvas_editor.base_image else "disabled")
        self.lbl_status_zoom.config(text=f"ZOOM: {int(round(self.canvas_editor.zoom_factor * 100))}%")

    def update_coordinates_status(self, x, y):
        self.lbl_status_coords.config(text=f"COORDS: {x:04d}, {y:04d}")

    def get_auto_filename(self):
        save_dir = self.config.get("default_save_path")
        pattern = self.config.get("naming_pattern")
        fmt = self.config.get("default_format").lower()
        
        now_str = time.strftime("%Y%m%d_%H%M%S")
        filename = pattern.replace("{datetime}", now_str)
        
        if "{index}" in filename:
            regex_pattern = filename.replace("{index}", r"(\d+)")
            regex = re.compile("^" + regex_pattern + r"\." + fmt + "$", re.IGNORECASE)
            
            max_idx = 0
            if os.path.exists(save_dir):
                try:
                    for f in os.listdir(save_dir):
                        match = regex.match(f)
                        if match:
                            idx = int(match.group(1))
                            if idx > max_idx:
                                max_idx = idx
                except Exception:
                    pass
            next_idx = max_idx + 1
            filename = filename.replace("{index}", f"{next_idx:03d}")
            
        return os.path.join(save_dir, f"{filename}.{fmt}")

    def save_image_file(self, pil_image, file_path, format_str):
        try:
            img_to_save = pil_image
            if format_str.upper() in ("JPEG", "JPG", "BMP"):
                bg = Image.new("RGB", pil_image.size, (255, 255, 255))
                if pil_image.mode == "RGBA":
                    bg.paste(pil_image, mask=pil_image.split()[3])
                else:
                    bg.paste(pil_image)
                img_to_save = bg
                
            img_to_save.save(file_path, format=format_str.upper())
            return True
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to save image:\n{e}")
            return False

    def save_quick(self):
        if not self.canvas_editor.base_image:
            return
            
        file_path = self.get_auto_filename()
        fmt = self.config.get("default_format")
        
        edited_image = self.canvas_editor.get_edited_image()
        if edited_image:
            if self.save_image_file(edited_image, file_path, fmt):
                orig_text = self.lbl_status_path.cget("text")
                self.lbl_status_path.config(text=f"EXPORTED: {os.path.basename(file_path)}", fg="#34C759")
                self.root.after(3000, lambda: self.lbl_status_path.config(text=orig_text, fg=self.text_muted))

    def save_as(self):
        if not self.canvas_editor.base_image:
            messagebox.showwarning("Empty Workspace", "There is no captured image to save. Take a snip first!")
            return
            
        default_dir = self.config.get("default_save_path")
        default_fmt = self.config.get("default_format").upper()
        
        file_types = [
            ("PNG Image", "*.png"),
            ("JPEG Image", "*.jpg;*.jpeg"),
            ("BMP Image", "*.bmp")
        ]
        
        initial_file_type = 0
        if default_fmt == "JPEG":
            initial_file_type = 1
        elif default_fmt == "BMP":
            initial_file_type = 2
            
        file_path = filedialog.asksaveasfilename(
            initialdir=default_dir,
            initialfile=os.path.basename(self.get_auto_filename()),
            filetypes=file_types,
            defaultextension=".png" if default_fmt == "PNG" else ".jpg"
        )
        
        if not file_path:
            return
            
        ext = os.path.splitext(file_path)[1].lower()
        fmt = "PNG"
        if ext in (".jpg", ".jpeg"):
            fmt = "JPEG"
        elif ext == ".bmp":
            fmt = "BMP"
            
        edited_image = self.canvas_editor.get_edited_image()
        if edited_image:
            self.save_image_file(edited_image, file_path, fmt)

    def copy_to_clipboard(self):
        """Copies the edited canvas image directly to Windows Clipboard natively."""
        if not self.canvas_editor.base_image:
            messagebox.showwarning("Empty Workspace", "No image to copy. Take a snip first!")
            return
            
        edited_image = self.canvas_editor.get_edited_image()
        if edited_image:
            try:
                import io
                import ctypes
                
                # Convert to BMP DIB format (BMP file bytes minus first 14-byte header)
                output = io.BytesIO()
                edited_image.convert("RGB").save(output, "BMP")
                data = output.getvalue()[14:]
                output.close()
                
                ctypes.windll.user32.OpenClipboard(None)
                ctypes.windll.user32.EmptyClipboard()
                
                CF_DIB = 8
                hglb = ctypes.windll.kernel32.GlobalAlloc(2, len(data)) # GMEM_MOVEABLE = 2
                p_box = ctypes.windll.kernel32.GlobalLock(hglb)
                ctypes.memmove(p_box, data, len(data))
                ctypes.windll.kernel32.GlobalUnlock(hglb)
                
                ctypes.windll.user32.SetClipboardData(CF_DIB, hglb)
                ctypes.windll.user32.CloseClipboard()
                
                orig_text = self.lbl_status_path.cget("text")
                self.lbl_status_path.config(text="COPIED TO CLIPBOARD!", fg=self.accent_color)
                self.root.after(3000, lambda: self.lbl_status_path.config(text=orig_text, fg=self.text_muted))
            except Exception as e:
                messagebox.showerror("Clipboard Error", f"Failed to copy to clipboard:\n{e}")

    def open_settings_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Preferences Configuration")
        dialog.geometry("520x360")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=self.panel_bg)
        dialog.resizable(False, False)
        
        dialog.grid_columnconfigure(1, weight=1)
        
        # 1. Save Path
        lbl1 = tk.Label(dialog, text="DEFAULT EXPORT PATH:", bg=self.panel_bg, fg=self.text_muted, font=self.font_bold)
        lbl1.grid(row=0, column=0, sticky="w", padx=20, pady=(25, 5))
        lbl1.is_muted = True
        
        path_var = tk.StringVar(value=self.config.get("default_save_path"))
        entry_path = StyledEntry(dialog, textvariable=path_var)
        entry_path.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=5)
        
        def browse_path():
            directory = filedialog.askdirectory(initialdir=path_var.get())
            if directory:
                path_var.set(os.path.normpath(directory))
        
        btn_browse = tk.Button(
            dialog, text="BROWSE...", command=browse_path, bg=self.btn_bg, fg=self.text_color,
            activebackground=self.btn_bg, activeforeground=self.text_color, bd=0, relief="flat",
            padx=10, pady=5, font=self.font_bold
        )
        btn_browse.grid(row=1, column=2, padx=20, pady=5)
        
        # 2. File Pattern
        lbl2 = tk.Label(dialog, text="NAMING PATTERN (Use {datetime} or {index}):", bg=self.panel_bg, fg=self.text_muted, font=self.font_bold)
        lbl2.grid(row=2, column=0, sticky="w", padx=20, pady=10)
        lbl2.is_muted = True
        pattern_var = tk.StringVar(value=self.config.get("naming_pattern"))
        entry_pattern = StyledEntry(dialog, textvariable=pattern_var)
        entry_pattern.grid(row=2, column=1, columnspan=2, sticky="ew", padx=20, pady=10)
        
        # 3. Application Theme (Light vs Dark switcher)
        lbl_theme = tk.Label(dialog, text="APPLICATION THEME:", bg=self.panel_bg, fg=self.text_muted, font=self.font_bold)
        lbl_theme.grid(row=3, column=0, sticky="w", padx=20, pady=10)
        lbl_theme.is_muted = True
        theme_var = tk.StringVar(value="Light" if self.config.get("theme") == "light" else "Dark")
        cb_theme = ttk.Combobox(dialog, textvariable=theme_var, values=["Light", "Dark"], state="readonly", width=12)
        cb_theme.grid(row=3, column=1, sticky="w", padx=20, pady=10)
        
        # 4. Save Format
        lbl4 = tk.Label(dialog, text="EXPORT FORMAT:", bg=self.panel_bg, fg=self.text_muted, font=self.font_bold)
        lbl4.grid(row=4, column=0, sticky="w", padx=20, pady=10)
        lbl4.is_muted = True
        format_var = tk.StringVar(value=self.config.get("default_format"))
        cb_format = ttk.Combobox(dialog, textvariable=format_var, values=["PNG", "JPEG", "BMP"], state="readonly", width=12)
        cb_format.grid(row=4, column=1, sticky="w", padx=20, pady=10)
        
        def save_and_close():
            p = path_var.get().strip()
            pat = pattern_var.get().strip()
            f = format_var.get()
            t = "light" if theme_var.get() == "Light" else "dark"
            
            if not p or not os.path.exists(p):
                messagebox.showerror("Invalid Directory", "The specified default save directory does not exist.")
                return
                
            if not pat:
                messagebox.showerror("Invalid Pattern", "Naming pattern cannot be empty.")
                return
                
            self.config.set("default_save_path", p)
            self.config.set("naming_pattern", pat)
            self.config.set("default_format", f)
            self.config.set("theme", t)
            
            self.apply_theme_colors()
            self.canvas_editor.redraw()
            
            self.lbl_status_path.config(text=f"SAVE DEST: {p}")
            dialog.destroy()
            
        btn_frame = tk.Frame(dialog, bg=self.panel_bg)
        btn_frame.grid(row=5, column=0, columnspan=3, sticky="e", padx=20, pady=20)
        
        # Cancel
        tk.Button(
            btn_frame, text="CANCEL", command=dialog.destroy, bg=self.btn_bg, fg=self.text_color,
            activebackground=self.btn_bg, activeforeground=self.text_color, bd=0, relief="flat",
            padx=10, pady=5, font=self.font_bold
        ).pack(side=tk.LEFT, padx=5)
        
        # Apply
        tk.Button(
            btn_frame, text="APPLY CHANGES", command=save_and_close, bg=self.accent_color, fg="#FFFFFF",
            activebackground="#004C94", activeforeground="#FFFFFF", bd=0, relief="flat",
            padx=10, pady=5, font=self.font_bold
        ).pack(side=tk.LEFT, padx=5)


if __name__ == "__main__":
    root = tk.Tk()
    app = SnippingToolApp(root)
    root.mainloop()
