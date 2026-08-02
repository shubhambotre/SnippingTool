# Walkthrough - Custom Image Capture and Editing Tool

We have implemented a customized desktop alternative to the Windows Snipping Tool in Python, built around **Tkinter** and **Pillow (PIL)**. The tool offers robust image capture options combined with full paint annotation capabilities.

---

## 🚀 Key Features

1. **Dual Capture Modes**:
   - **Free Select (default)**: Clicking "New Snip" dims the screen and lets you draw a selection rectangle. The overlay highlights the clear, bright area within the selection dynamically.
   - **Fixed Size**: Allows setting precise width and height coordinates (e.g., `1024x768`) in the toolbar before snipping. When capturing, a box of that exact size follows your cursor, and clicking anywhere grabs that exact crop.
2. **Annotation Toolkit**:
   - **Draw Tools**: Pencil, Line, Arrow (computes mathematically correct scaling arrowheads), Rectangle (hollow/filled), Circle (hollow/filled), and Text (spawns an on-canvas text box with custom sizing).
   - **Eraser**: Paints with a white brush to easily mask annotations.
3. **Advanced History Manager**:
   - Unlimited **Undo** and **Redo** capabilities.
   - **Clear All** restores the original clean screenshot.
   - Operations are synced off-screen using vector draw operations, allowing you to edit dynamically on-screen while maintaining a high-fidelity image output.
4. **Smart Configuration Persistence**:
   - Config file `.custom_snipping_tool_config.json` is stored in the user's home directory.
   - Remembers the last-used color, tool, brush width, font size, fill mode, capture mode, default save path, and filename pattern.
5. **Flexible File Management**:
   - Save path configuration (defaults to the system's `Pictures` directory).
   - Filename template patterns supporting placeholders:
     - `{datetime}`: formats timestamp as `YYYYMMDD_HHMMSS`.
     - `{index}`: formats auto-incrementing file suffix (e.g. `001`, `002`) based on existing directory files.
   - Exports files in **PNG**, **JPEG**, and **BMP**. Safely flattens transparent RGBA layers onto solid white canvases when exporting to BMP or JPEG to avoid crashes.

---

## ⌨️ Keyboard Shortcuts

- `Ctrl + N`: Trigger new capture screen snip.
- `Ctrl + S`: Quick-save current canvas to the default save path with pattern.
- `Ctrl + Shift + S`: Save As dialog box to choose folder, name, and format (PNG, JPG, BMP).
- `Ctrl + Z`: Undo last action.
- `Ctrl + Y`: Redo last action.
- `Escape`: Cancel screen capture overlay.

---

## 🛠️ Verification & Test Plan

Follow these steps to test the application locally on Windows:

1. **Launch the application**:
   Propose running the launcher:
   ```powershell
   python main.py
   ```
2. **Capture screen**:
   - Select "free" from the Mode dropdown, click **New Snip**, and draw a selection area.
   - Select "fixed", enter `800` in `W` and `600` in `H`, click **New Snip**, move your cursor around, and click to capture.
3. **Annotate**:
   - Try the **Arrow** and **Text** tools. Click on the canvas in Text mode, type some text, and hit Enter.
   - Change colors, thicknesses, and draw rectangles.
4. **Undo/Redo**:
   - Click **Undo** (or `Ctrl+Z`) and **Redo** (or `Ctrl+Y`) and verify shapes are drawn/removed correctly.
5. **Save and Persistence**:
   - Click **Save** to verify files are auto-saved to your default path.
   - Go to **Settings**, browse to a custom folder, change the naming pattern, choose **JPEG** or **BMP**, and save again.
   - Close the application, relaunch, and verify that your last configurations (colors, paths, settings) are loaded.
