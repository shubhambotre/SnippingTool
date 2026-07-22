# Custom Snipping and Drawing Tool

A streamlined, modern alternative to the standard snipping tool, built entirely in Python. It is designed to capture screen regions, annotate them with vector drawing tools, modify text placements, and crop regions dynamically within the editor.

---

## 🎨 Key Features

1. **Light & Dark Theme Switcher**:
   - Toggle between **Light Mode** (white interface) and **Dark Mode** (charcoal dark interface) inside the Preferences Settings.
   - Dynamic real-time styling cascades to all buttons, scrollbars, frames, inputs, and background panels.
   - High-contrast vector icons adjust automatically (dark charcoal `#333333` in Light Mode vs light silver-grey `#DDDDDD` in Dark Mode).

2. **Select & Move Text and Shapes**:
   - Active **Select & Move** tool (classic mouse pointer icon) allows clicking on any canvas element to select it.
   - Highlights the selected element with a blue dashed bounding rectangle.
   - Drag and drop the selected element (pencils, highlighters, lines, arrows, rectangles, circles, or text) to move it.
   - Nudge elements using keyboard **Arrow Keys** (1-pixel increments) or **Shift + Arrow Keys** (5-pixel increments) for perfect alignments.

3. **Dynamic Scaling & Canvas Zooming**:
   - **Scroll Wheel Element Resizing**: With the selection tool active, select any shape or text block and simply scroll the mouse wheel up/down to dynamically resize it.
   - **Keyboard Element Scaling**: Resize selected elements by 10% increments using the `+` (plus/equals) and `-` (minus) keys.
   - **Canvas Zoom (25% to 300%)**: Zoom in/out of your workspace using the magnifying glass toolbar buttons or holding the **Control (`Ctrl`)** key while scrolling the mouse wheel.
   - Resolution-independent coordinates ensure saved captures and clipboard copies are preserved at original high-resolution quality.

4. **Dynamic Selection Formatting**:
   - Change the color swatches, brush stroke thickness, shape fill options (hollow vs filled), font size, or font family of a selected element dynamically from the toolbar in real-time.

5. **Font Family dropdown Customization**:
   - Select font styles from a dropdown list of 7 cross-platform system fonts: `Arial, Times New Roman, Courier New, Georgia, Segoe UI, Verdana, Impact`.
   - Text editing double-clicks automatically preserve the text block's specific font style.

6. **Text Annotation & Modification**:
   - Add text labels to snippets easily. Inputs use black text on a white background, ensuring readability while typing regardless of the active drawing color.
   - Click on any existing text block to open the entry box pre-filled, allowing easy corrections and changes.

7. **Dynamic Image Cropping**:
   - Drag a crop box over any captured snippet. Releasing the mouse crops the region, bakes existing annotations, and dynamically adjusts the workspace window size.

8. **Clipboard & File Management**:
   - **Native Copy to Clipboard**: Copies the edited canvas image directly to the Windows Clipboard (CF_DIB format) so you can paste it (`Ctrl+V`) directly into other apps.
   - **Custom Exports**: Set default save paths, custom file naming patterns using `{datetime}` or `{index}`, and save in PNG, JPEG, or BMP formats.
   - Full Undo and Redo operations.

---

## ⌨️ Keyboard & Mouse Shortcuts

| Shortcut | Action |
| --- | --- |
| `Mouse Wheel` | Resize active selected element (in Select mode) |
| `Ctrl + Mouse Wheel` | Zoom canvas workspace In / Out |
| `+` (Plus / Equals) | Scale selected element larger by 10% |
| `-` (Minus) | Scale selected element smaller by 10% |
| `Arrow Keys` | Nudge selected element by 1px |
| `Shift + Arrow Keys` | Nudge selected element by 5px |
| `Ctrl + N` | Trigger new screen capture viewfinder |
| `Ctrl + C` | Copy current edited image to OS clipboard |
| `Ctrl + S` | Quick-save image to default path |
| `Ctrl + Shift + S` | Open Save As export dialog |
| `Ctrl + Z` | Undo last drawing/movement |
| `Ctrl + Y` | Redo last drawing/movement |
| `Escape` | Cancel screen capture overlay |

---

## 📂 Project Architecture

* **[main.py](file:///e:/Snipping-Tool/main.py)**: Application launcher and main GUI window controller. Handles toolbar layouts, theme cascading, settings panels, and clipboard operations.
* **[canvas_editor.py](file:///e:/Snipping-Tool/canvas_editor.py)**: Interactive vector canvas drawing board. Manages history states, selections, dragging, key nudges, cropping, and double-buffered image rendering.
* **[capture.py](file:///e:/Snipping-Tool/capture.py)**: Screen snip overlay. Captures screen coordinates using click-and-drag viewfinders.
* **[icons.py](file:///e:/Snipping-Tool/icons.py)**: Dynamically generates vector theme icons using PIL.
* **[config.py](file:///e:/Snipping-Tool/config.py)**: Reads and writes user settings and preferences to a local JSON file.

---

## 🛠️ Installation & Setup

### Prerequisites
Make sure Python 3.10+ is installed on your machine.

### Dependencies
Install the required image processing library:
```bash
pip install pillow
```

### Running the Application
Launch the tool from the project directory:
```bash
python main.py
```
