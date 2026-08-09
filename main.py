import tkinter as tk
from tkinter import messagebox, filedialog, ttk, colorchooser
import os
import time
import re
import threading
from PIL import Image, ImageTk, ImageGrab

# Import local components
from config import AppConfig
from capture import CaptureOverlay
from canvas_editor import CanvasEditor
from icons import get_icon, get_button_image
from collage_editor import CollageEditorDialog

class StyledEntry(tk.Entry):
    """Custom flat entry widget with dynamic themes and Segoe UI typography."""
    def __init__(self, parent, **kwargs):
        bg = kwargs.pop("bg", "#FFFFFF")
        fg = kwargs.pop("fg", "#0E1013")
        insertbackground = kwargs.pop("insertbackground", "#005FB8")
        font = kwargs.pop("font", ("Segoe UI", 9))
        
        super().__init__(
            parent, bg=bg, fg=fg, insertbackground=insertbackground, font=font,
            bd=0, highlightthickness=1, highlightbackground="#D0D0D0",
            highlightcolor="#005FB8", **kwargs
        )

class ToolTip:
    """Displays a small floating label when hovering over a widget."""
    def __init__(self, widget, text, delay_ms=600):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Motion>", self._move, add="+")

    def _schedule(self, event=None):
        self._cancel()
        if self.text:
            self._after_id = self.widget.after(self.delay_ms, self._show)

    def _show(self):
        self._hide()
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        # Keep the popup on top of the main window so it is always visible.
        self._tip.attributes("-topmost", True)
        self._tip.wm_geometry(f"+{x}+{y}")
        self._tip.lift()

        # Stylish rounded, subtle tooltip that adapts to the focus of the app
        lbl = tk.Label(
            self._tip, text=self.text, bg="#1F2937", fg="#F9FAFB",
            font=("Segoe UI", 9, "bold"), padx=8, pady=4,
            relief="flat", bd=0, highlightthickness=1, highlightbackground="#374151"
        )
        lbl.pack()

    def _move(self, event):
        # Keep the tooltip following the cursor if it's already showing
        if self._tip is not None:
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            self._tip.wm_geometry(f"+{x}+{y}")

    def _hide(self, event=None):
        self._cancel()
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None

    def _cancel(self):
        if self._after_id is not None:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

class SnippingToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Snipping Tool")
        
        # Set window icon photo
        logo_path = os.path.join(os.path.dirname(__file__), "SnippingTool.png")
        if os.path.exists(logo_path):
            try:
                logo_img = Image.open(logo_path)
                self.logo_photo = ImageTk.PhotoImage(logo_img)
                self.root.iconphoto(True, self.logo_photo)
            except Exception:
                pass
                
        # Start compact horizontal launcher pill - reduced width to fit tools cleanly and compactly
        self.root.geometry("480x102")
        self.root.resizable(True, True)

        # Fullscreen editing mode (enabled automatically after a capture, toggled with F11)
        self._fullscreen = False
        
        # Load configuration settings
        self.config = AppConfig()
        
        # Segoe UI Font System definitions
        self.font_main = ("Segoe UI", 9)
        self.font_bold = ("Segoe UI", 9, "bold")
        self.font_title = ("Segoe UI", 10, "bold")
        self.font_status = ("Segoe UI", 8, "bold")
        self.font_status_italic = ("Segoe UI", 8, "italic")
        self.font_data = ("Consolas", 9, "bold")  # instrument-style coordinate/status readout (DESIGN.md)
        
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

        # Fullscreen toggle (F11) and exit (Esc) so the post-capture fullscreen view isn't a trap
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<Escape>", self.exit_fullscreen)
        
        # Start global hotkey listener
        self.start_global_hotkey_listener()

    def apply_theme_tokens(self):
        """Loads Light or Dark theme color tokens dynamically."""
        self.theme_name = self.config.get("theme")
        if self.theme_name == "dark":
            self.bg_color = "#1A1C1E"       # Modern Windows 11 dark frame
            self.panel_bg = "#2D2F31"       # Dark grey panels
            self.accent_color = "#3B82F6"   # Modern Fluent Cobalt
            self.btn_bg = "#3A3C3E"         # Hover button dark grey
            self.border_color = "#3F4347"   # Dark card border
            self.text_color = "#F9FAFB"     # High contrast dark text
            self.text_muted = "#9CA3AF"     # Muted grey
            self.canvas_bg = "#141517"      # Dark workspace background
            self.active_tool_bg = "#1E3B8B" # Rich active blue highlights
        else:
            self.bg_color = "#F3F4F6"       # Modern Windows 11 light frame
            self.panel_bg = "#FFFFFF"       # Clean white cards
            self.accent_color = "#2563EB"   # Modern Fluent Blue
            self.btn_bg = "#F3F4F6"         # Hover button grey
            self.border_color = "#E5E7EB"   # Thin card border
            self.text_color = "#111827"     # Dark charcoal text
            self.text_muted = "#6B7280"     # Muted grey
            self.canvas_bg = "#F3F4F6"      # Light workspace background
            self.active_tool_bg = "#E0E7FF" # Soft active indigo highlights

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
            fieldbackground="#FFFFFF" if self.theme_name == "light" else "#3A3C3E", 
            background=self.panel_bg, 
            foreground=self.text_color, 
            arrowcolor=self.text_color, 
            bd=0, 
            font=self.font_main
        )
        self.style.map(
            "TCombobox", 
            fieldbackground=[("readonly", "#FFFFFF" if self.theme_name == "light" else "#3A3C3E")], 
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
            elif (hasattr(widget, "is_divider") and widget.is_divider) or (hasattr(widget, "is_border") and widget.is_border):
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
        """Builds the compact horizontal toolbar with Segoe UI typography."""
        # Top toolbar border container (Fluent floating design)
        self.toolbar_border_frame = tk.Frame(self.root, bg=self.border_color)
        self.toolbar_border_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(10, 0))
        self.toolbar_border_frame.is_border = True
        
        # Inner panel
        self.toolbar_frame = tk.Frame(self.toolbar_border_frame, bg=self.panel_bg, bd=0, height=48)
        self.toolbar_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self.toolbar_frame.pack_propagate(False)
        
        # --- LEFT: Brand + Launch & Mode ---
        left_grp = tk.Frame(self.toolbar_frame, bg=self.panel_bg)
        left_grp.pack(side=tk.LEFT, fill=tk.Y, padx=5)

        # Brand mark: small app logo + wordmark for a distinctive identity
        brand_path = os.path.join(os.path.dirname(__file__), "SnippingTool.png")
        self.brand_logo_tk = None
        if os.path.exists(brand_path):
            try:
                brand_img = Image.open(brand_path).convert("RGBA").resize((22, 22), Image.Resampling.LANCZOS)
                self.brand_logo_tk = ImageTk.PhotoImage(brand_img)
            except Exception:
                self.brand_logo_tk = None
        if self.brand_logo_tk:
            lbl_brand_logo = tk.Label(left_grp, image=self.brand_logo_tk, bg=self.panel_bg)
            lbl_brand_logo.pack(side=tk.LEFT, padx=(0, 3), pady=8)
        self.lbl_brand = tk.Label(
            left_grp, text="Snipping Tool", bg=self.panel_bg, fg=self.text_color,
            font=("Segoe UI", 9, "bold")
        )
        self.lbl_brand.pack(side=tk.LEFT, padx=(0, 8), pady=8)

        # New Crop button with white icon on active Cobalt background
        self.icon_camera = get_icon("camera", "#FFFFFF", size=(20, 20))
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
            btn = self.make_icon_button(self.mid_grp, icon_name, lambda t=tool_name: self.set_tool(t), tooltip=tooltip)
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
        
        self.btn_settings = self.make_icon_button(self.right_grp, "settings", self.open_settings_dialog, tooltip="Preferences")
        self.btn_settings.pack(side=tk.RIGHT, padx=1, pady=5)
        
        div4 = tk.Frame(self.right_grp, bg=self.border_color, width=1)
        div4.pack(side=tk.RIGHT, fill=tk.Y, padx=4, pady=6)
        div4.is_divider = True
        
        self.btn_save_as = self.make_icon_button(self.right_grp, "save", self.save_as, tooltip="Save As (Ctrl+Shift+S)")
        self.btn_save_as.pack(side=tk.RIGHT, padx=1, pady=5)

        self.btn_collage = self.make_icon_button(self.right_grp, "collage", self.open_collage_editor, tooltip="Photo Collage Editor")
        # Collage button is shown/hidden by update_toolbar_state based on whether an image is loaded

        self.btn_copy = self.make_icon_button(self.right_grp, "copy", self.copy_to_clipboard, tooltip="Copy to Clipboard (Ctrl+C)")
        self.btn_copy.pack(side=tk.RIGHT, padx=1, pady=5)

        self.btn_clear = self.make_icon_button(self.right_grp, "clear", self.clear_canvas, tooltip="Clear / Reset Workspace")
        self.btn_clear.pack(side=tk.RIGHT, padx=1, pady=5)
        
        div5 = tk.Frame(self.right_grp, bg=self.border_color, width=1)
        div5.pack(side=tk.RIGHT, fill=tk.Y, padx=4, pady=6)
        div5.is_divider = True
        
        # Zoom Controls
        self.btn_zoom_in = self.make_icon_button(self.right_grp, "zoom_in", self.zoom_in, tooltip="Zoom In (Ctrl+Scroll)")
        self.btn_zoom_in.pack(side=tk.RIGHT, padx=1, pady=5)

        self.btn_zoom_out = self.make_icon_button(self.right_grp, "zoom_out", self.zoom_out, tooltip="Zoom Out (Ctrl+Scroll)")
        self.btn_zoom_out.pack(side=tk.RIGHT, padx=1, pady=5)
        
        div_z = tk.Frame(self.right_grp, bg=self.border_color, width=1)
        div_z.pack(side=tk.RIGHT, fill=tk.Y, padx=4, pady=6)
        div_z.is_divider = True
        
        self.btn_redo = self.make_icon_button(self.right_grp, "redo", self.redo, tooltip="Redo (Ctrl+Y)")
        self.btn_redo.pack(side=tk.RIGHT, padx=1, pady=5)

        self.btn_undo = self.make_icon_button(self.right_grp, "undo", self.undo, tooltip="Undo (Ctrl+Z)")
        self.btn_undo.pack(side=tk.RIGHT, padx=1, pady=5)
        
        # Center Canvas Editor Frame
        self.canvas_editor = CanvasEditor(self.root, bg=self.bg_color)
        self.canvas_editor.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.canvas_editor.on_draw_callback = self.update_actions_buttons_state
        self.canvas_editor.cursor_callback = self.update_coordinates_status
        self.canvas_editor.on_crop_complete_callback = self.on_crop_complete
        self.canvas_editor.on_tool_change_callback = self.set_tool
        
        # Bottom Status Bar border container (Fluent floating design)
        self.status_border_frame = tk.Frame(self.root, bg=self.border_color)
        self.status_border_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 10))
        self.status_border_frame.is_border = True
        
        # Inner panel
        self.status_bar = tk.Frame(self.status_border_frame, bg=self.panel_bg, bd=0, height=22)
        self.status_bar.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self.status_bar.pack_propagate(False)
        
        self.lbl_status_tool = tk.Label(self.status_bar, text="TOOL: PENCIL", bg=self.panel_bg, fg=self.text_color, font=self.font_data)
        self.lbl_status_tool.pack(side=tk.LEFT, padx=15, pady=3)

        self.lbl_status_zoom = tk.Label(self.status_bar, text="ZOOM: 100%", bg=self.panel_bg, fg=self.text_color, font=self.font_data)
        self.lbl_status_zoom.pack(side=tk.LEFT, padx=20, pady=3)

        self.lbl_status_dims = tk.Label(self.status_bar, text="RESOLUTION: 0 x 0 PX", bg=self.panel_bg, fg=self.text_color, font=self.font_data)
        self.lbl_status_dims.pack(side=tk.LEFT, padx=20, pady=3)

        self.lbl_status_coords = tk.Label(self.status_bar, text="COORDS: 0, 0", bg=self.panel_bg, fg=self.text_color, font=self.font_data)
        self.lbl_status_coords.pack(side=tk.LEFT, padx=20, pady=3)
        
        self.lbl_status_path = tk.Label(
            self.status_bar, 
            text=f"SAVE DEST: {self.config.get('default_save_path')}", 
            bg=self.panel_bg, fg=self.text_muted, font=self.font_status_italic
        )
        self.lbl_status_path.pack(side=tk.RIGHT, padx=15, pady=3)
        self.lbl_status_path.is_muted = True
        
        self.update_actions_buttons_state()

    def get_btn_img(self, button, state):
        """Helper to get button image for a specific state ('normal', 'hover', 'active')."""
        icon_name = button.icon_name
        # Theme-matched glyph color: deep charcoal on Light, soft white on Dark.
        icon_col = self.text_color if self.theme_name == "light" else "#E5E7EB"

        if state == "active":
            bg = self.active_tool_bg
            border = self.accent_color
            icon_col = self.accent_color
        elif state == "hover":
            bg = self.btn_bg
            border = self.border_color
        else:
            bg = self.panel_bg
            border = None

        return get_button_image(icon_name, icon_col, bg, border, size=(34, 34), icon_size=(20, 20))

    def make_icon_button(self, parent, icon_name, command, tooltip=None):
        """Builds a flat button styled dynamically based on theme icons."""
        btn = tk.Button(
            parent, command=command, bg=self.panel_bg,
            activebackground=self.panel_bg, bd=0, relief="flat", highlightthickness=0
        )
        btn.icon_name = icon_name
        if tooltip:
            ToolTip(btn, tooltip)
        
        img_normal = self.get_btn_img(btn, "normal")
        btn.config(image=img_normal)
        btn.image = img_normal
        
        # Hover bindings
        def on_enter(e):
            if not self.is_active_tool(btn.icon_name):
                img_hover = self.get_btn_img(btn, "hover")
                btn.config(image=img_hover)
                btn.image = img_hover
                
        def on_leave(e):
            state = "active" if self.is_active_tool(btn.icon_name) else "normal"
            img_state = self.get_btn_img(btn, state)
            btn.config(image=img_state)
            btn.image = img_state
            
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def update_icons(self):
        """Refreshes all toolbar icons to match Light/Dark high contrast specifications."""
        self.icon_camera = get_icon("camera", "#FFFFFF", size=(20, 20))
        self.btn_new.config(image=self.icon_camera)
        
        # Refresh utilities on the right
        for button in [
            self.btn_settings,
            self.btn_save_as,
            self.btn_collage,
            self.btn_copy,
            self.btn_clear,
            self.btn_zoom_in,
            self.btn_zoom_out,
            self.btn_redo,
            self.btn_undo
        ]:
            img = self.get_btn_img(button, "normal")
            button.config(image=img)
            button.image = img
            
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
            self.lbl_status_tool.config(text="TOOL: CROP (DRAG A BOX, ADJUST IT, THEN CLICK 'CROP' TO APPLY)")
        else:
            self.lbl_status_tool.config(text=f"TOOL: {tool_name.upper()}")
        
        # Highlight active tool button with Cobalt icon and active state
        for name, button in self.tool_buttons.items():
            state = "active" if name == tool_name else "normal"
            img = self.get_btn_img(button, state)
            button.config(image=img)
            button.image = img

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

    def open_collage_editor(self):
        """Opens the Photo Collage Editor dialog with the current snip pre-loaded."""
        theme_colors = {
            "bg_color":     self.bg_color,
            "panel_bg":     self.panel_bg,
            "accent_color": self.accent_color,
            "btn_bg":       self.btn_bg,
            "border_color": self.border_color,
            "text_color":   self.text_color,
            "text_muted":   self.text_muted,
            "canvas_bg":    self.canvas_bg,
            "theme_name":   self.theme_name,
        }
        # Pass the current annotated image (if any) as the first cell
        initial_image = None
        if self.canvas_editor.base_image:
            initial_image = self.canvas_editor.get_edited_image()

        CollageEditorDialog(
            self.root,
            theme_colors=theme_colors,
            initial_image=initial_image,
            result_callback=self.on_capture_complete,
            root_window=self.root,
        )

    def on_capture_complete(self, image):
        if image:
            self.canvas_editor.set_image(image)
            self.update_toolbar_state()
            self.update_actions_buttons_state()

            # Open the editor maximized so the snip gets maximum workspace.
            self.root.state('zoomed')

            self.on_crop_complete(image.width, image.height)
            self.root.lift()
            self.root.focus_force()

    def take_full_screenshot(self):
        """Hides the main window, captures a full screenshot, and loads it into the editor."""
        # Hide the main window if it's currently shown
        self.root.withdraw()
        self.root.update()
        
        # Brief pause to allow the window to fade out
        time.sleep(0.35)
        
        try:
            image = ImageGrab.grab(all_screens=True)
        except Exception:
            try:
                image = ImageGrab.grab()
            except Exception as e:
                messagebox.showerror("Capture Error", f"Failed to grab screen:\n{e}")
                self.root.deiconify()
                self.root.update()
                return
            
        # Show main window again
        self.root.deiconify()
        self.root.update()
        
        self.on_capture_complete(image)

    def start_global_hotkey_listener(self):
        """Starts a background thread to listen for the global Shift + Print Screen hotkey (Windows only)."""
        if os.name != 'nt':
            return
            
        def listener():
            import ctypes
            from ctypes import wintypes
            
            user32 = ctypes.windll.user32
            
            # Constants
            MOD_SHIFT = 0x0004
            VK_SNAPSHOT = 0x2C  # Print Screen
            WM_HOTKEY = 0x0312
            HOTKEY_ID = 101     # Unique ID for our hotkey
            
            # Register the hotkey: Shift + Print Screen
            # Passing None as hwnd registers a thread-specific hotkey.
            if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_SHIFT, VK_SNAPSHOT):
                # If already registered by another running instance/app, exit thread silently
                return
                
            try:
                msg = wintypes.MSG()
                while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                    if msg.message == WM_HOTKEY:
                        if msg.wParam == HOTKEY_ID:
                            # Safely schedule screenshot capture on the main tkinter thread
                            self.root.after(0, self.take_full_screenshot)
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
            finally:
                user32.UnregisterHotKey(None, HOTKEY_ID)
                
        self.hotkey_thread = threading.Thread(target=listener, daemon=True)
        self.hotkey_thread.start()

    def on_crop_complete(self, w, h):
        self.lbl_status_dims.config(text=f"RESOLUTION: {w} x {h} PX")
        self.lbl_status_zoom.config(text=f"ZOOM: {int(round(self.canvas_editor.zoom_factor * 100))}%")
        if not self._fullscreen and self.root.state() != 'zoomed':
            win_w = max(900, w + 30)
            win_h = h + 138
            self.root.geometry(f"{win_w}x{win_h}")

    def set_fullscreen(self, on):
        """Toggles true fullscreen on the main window."""
        self._fullscreen = bool(on)
        self.root.attributes("-fullscreen", self._fullscreen)

    def toggle_fullscreen(self, event=None):
        """F11 handler: flips in and out of fullscreen."""
        self.set_fullscreen(not self._fullscreen)
        return "break"

    def exit_fullscreen(self, event=None):
        """Esc handler: only leaves fullscreen (doesn't interfere elsewhere)."""
        if self._fullscreen:
            self.set_fullscreen(False)
        return "break"

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
        self.canvas_editor.selected_index = None
        self.canvas_editor._grid_cache = None
        self.canvas_editor._baked_cache = None
        self.canvas_editor._display_photo = None
        self.canvas_editor._reset_crop_state()
        self.canvas_editor.redraw()

        self.set_fullscreen(False)
        self.root.state('normal')
        self.root.geometry("480x102")
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
            self.btn_collage.pack(side=tk.RIGHT, padx=1, pady=5)
            self.btn_save_as.pack(side=tk.RIGHT, padx=1, pady=5)
        else:
            self.mid_grp.pack_forget()
            self.btn_clear.pack_forget()
            self.btn_undo.pack_forget()
            self.btn_redo.pack_forget()
            self.btn_zoom_in.pack_forget()
            self.btn_zoom_out.pack_forget()
            self.btn_copy.pack_forget()
            self.btn_collage.pack_forget()
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
            clipboard_opened = False
            try:
                import io
                import ctypes
                
                # Convert to BMP DIB format (BMP file bytes minus first 14-byte header)
                output = io.BytesIO()
                edited_image.convert("RGB").save(output, "BMP")
                data = output.getvalue()[14:]
                output.close()
                
                # Configure ctypes signatures for 64-bit safety
                kernel32 = ctypes.windll.kernel32
                user32 = ctypes.windll.user32
                
                kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
                kernel32.GlobalAlloc.restype = ctypes.c_void_p
                
                kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalLock.restype = ctypes.c_void_p
                
                kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalUnlock.restype = ctypes.c_int
                
                user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
                user32.SetClipboardData.restype = ctypes.c_void_p
                
                if user32.OpenClipboard(None):
                    clipboard_opened = True
                    user32.EmptyClipboard()

                    CF_DIB = 8
                    hglb = kernel32.GlobalAlloc(2, len(data)) # GMEM_MOVEABLE = 2
                    copied = False
                    if not hglb:
                        raise RuntimeError("Failed to allocate clipboard memory.")
                    p_box = kernel32.GlobalLock(hglb)
                    if not p_box:
                        kernel32.GlobalFree(hglb)
                        raise RuntimeError("Could not lock clipboard memory.")
                    ctypes.memmove(p_box, data, len(data))
                    kernel32.GlobalUnlock(hglb)
                    # On success the clipboard takes ownership of hglb; only free it on failure.
                    copied = bool(user32.SetClipboardData(CF_DIB, hglb))
                    if not copied:
                        kernel32.GlobalFree(hglb)

                    if copied:
                        orig_text = self.lbl_status_path.cget("text")
                        self.lbl_status_path.config(text="COPIED TO CLIPBOARD!", fg=self.accent_color)
                        self.root.after(3000, lambda: self.lbl_status_path.config(text=orig_text, fg=self.text_muted))
                else:
                    raise RuntimeError("Could not open Windows clipboard.")
            except Exception as e:
                messagebox.showerror("Clipboard Error", f"Failed to copy to clipboard:\n{e}")
            finally:
                if clipboard_opened:
                    try:
                        ctypes.windll.user32.CloseClipboard()
                    except:
                        pass

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
