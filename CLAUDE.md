# CLAUDE.md

Guidance for working in this repository — a native Windows **Tkinter + Pillow (PIL)** snipping/capture tool with paint annotation.

## Overview

A custom desktop alternative to the Windows Snipping Tool. Captures screen regions (free-select or fixed-size), loads them into an annotation editor, and exports to PNG/JPEG/BMP or the clipboard. Pure Tkinter UI with PIL-rendered icons.

## Project layout

- `main.py` — `SnippingToolApp` (tk.Tk root): the launcher toolbar, status bar, settings dialog, capture flow, keyboard shortcuts, and the global **Shift+PrtSc** hotkey thread. Contains the `ToolTip` helper class.
- `canvas_editor.py` — `CanvasEditor` (tk.Frame): the scrollable image canvas, all drawing tools, undo/redo history, select/move/resize handles, crop flow, and the full-res bake used for export.
- `icons.py` — Pure-PIL vector icon generator. `draw_vector_icon` draws each glyph; `get_icon`/`get_button_image` produce Tk `PhotoImage`s (with caching via `icon_cache`).
- `capture.py` — `CaptureOverlay`: the dimming full-screen capture overlay (free region or fixed-size box).
- `config.py` — `AppConfig`: JSON settings persisted at `~/.custom_snipping_tool_config.json` (home dir), with `DEFAULT_SETTINGS` fallback.
- `SnippingTool.png` — App/brand logo used for the window icon, the launcher wordmark, and the empty-state hero.

## Architecture & data model

- **Annotations are stored as a vector list**, `CanvasEditor.history` (list of "action" dicts), not raster. `_draw_action(draw, action)` renders one action onto a PIL `ImageDraw`. `get_edited_image()`/`_get_edited_image_raw()` bake `history` onto a copy of `base_image` for the final export.
- Action dict shapes by `type`:
  - `pencil` / `highlighter`: `points` (list of (x,y)), `color`, `thickness`
  - `line` / `arrow` / `rectangle` / `circle`: `coords` `(x1,y1,x2,y2)`, `color`, `thickness`, `fill` (`"hollow"`/`"filled"`)
  - `text`: `coords` `(x,y)`, `text`, `color`, `font_size`, `font_family`
- Coordinates are **image-space**; all screen-space drawing multiplies by `zoom_factor`. When reading/writing coords, convert with `canvas.canvasx(e.x)/zoom_factor`.
- History is capped at `HISTORY_LIMIT = 500` via `_push_history`.

### Rendering/caching
- `_baked()` caches the full-res annotated image, invalidated by `_mark_dirty()` (bumps `_baked_revision`).
- During select-drag, the image is rendered once without the dragged element (`_ensure_drag_base`) and the moving element is redrawn as an overlay (`_render_moving_overlay`) for per-move speed — see `_redraw_select_drag`.
- `_grid_cache` caches the dot-grid background per (size, dark).
- `_full_render` / `redraw()` is the single canvas rebuild entry point.

## Key conventions

- **Fonts** use **Segoe UI** everywhere (`font_main`/`font_bold`/`font_title`/`font_status`). Do not introduce Arial.
- **Dual theme** (light/dark) sourced from `AppConfig.theme`. Token names live in `apply_theme_tokens()` (e.g. `bg_color`, `panel_bg`, `accent_color`, `text_color`, `active_tool_bg`). `apply_theme_colors()` + `update_theme_recursively()` re-theme widgets; tagged widgets use attributes like `is_muted`, `is_divider`, `is_border`, `is_swatch`, `is_picker`, `is_color_container`.
- **Icons are drawn in PIL** in `icons.py`. To change a toolbar glyph, edit `draw_vector_icon` — pass a theme-appropriate color. Icon glyph color derives from the theme (`text_color` on light, `#E5E7EB` on dark; active tool = `accent_color`).
- **Contacts between the editor and the app** use callbacks: `on_draw_callback`, `cursor_callback`, `on_crop_complete_callback`, `on_tool_change_callback`.

### Panels (main.py)
- `make_icon_button` builds a flat image button + `ToolTip`; `get_btn_img` returns the per-state (normal/hover/active) PIL card.
- The status bar labels are updated from methods like `update_actions_buttons_state`, `update_coordinates_status`, `on_crop_complete`.
- Toolbar visibility for the editing tools (`mid_grp`) is toggled by `update_toolbar_state()` depending on whether a `base_image` exists (compact launcher vs editing layout).

## Recent behavioral decisions (don't regress)

- **Rectangles/circles auto-select after drawing** and switch to the Select tool so resize handles appear immediately (`canvas_editor.on_release`). To draw multiple shapes in a row the user re-picks the tool.
- **Post-capture opens true fullscreen** (`set_fullscreen(True)` in `on_capture_complete`). F11 toggles, Esc exits; `reset_to_compact` exits fullscreen.
- **Shape resize** (rectangle/circle/text/line/arrow/select) is driven by 8-point `get_handles`; pressing a handle starts a drag, and `on_drag` mutates the action, then `_finish_select_drag` bakes it back.

## Fullscreen in context
`on_crop_complete` skips its window-geometry resize when `self._fullscreen` is true. `on_capture_complete` sets fullscreen before showing the window.

## Design System
Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.

## Verification
- Syntax: `python -m py_compile main.py canvas_editor.py icons.py capture.py`
- Headless icon render test: draw icons via `draw_vector_icon` (pure PIL, no Tk root needed); `get_button_image`/`get_icon` require a live Tk root.
- Manual: `python main.py` → New → snip → annotate → save.
