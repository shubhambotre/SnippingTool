import math
from PIL import Image, ImageDraw, ImageTk

icon_cache = {}

def draw_vector_icon(draw, name, color, size):
    """Draws the vector paths for the requested icon onto the provided ImageDraw canvas."""
    w, h = size
    
    if name == "camera":
        draw.rounded_rectangle([2, 5, w-3, h-3], radius=2, outline=color, width=1.5)
        draw.ellipse([w//2-4, h//2-2, w//2+4, h//2+6], outline=color, width=1.5)
        draw.ellipse([w-7, 7, w-5, 9], fill=color)
        draw.rectangle([w//2-3, 2, w//2+3, 5], fill=color)
        
    elif name == "pencil":
        draw.polygon([(3, h-3), (6, h-3), (w-3, 6), (w-6, 3)], outline=color, width=1.5)
        draw.line([(3, h-3), (5, h-5)], fill=color, width=1.5)
        
    elif name == "highlighter":
        draw.polygon([(3, h-3), (8, h-3), (w-3, 8), (w-8, 3)], outline=color, width=1.5)
        draw.line([(5, h-11), (11, h-5)], fill=color, width=1)
        
    elif name == "line":
        draw.line([3, h-3, w-3, 3], fill=color, width=2)
        
    elif name == "arrow":
        draw.line([3, h-3, w-6, 6], fill=color, width=2)
        draw.polygon([w-3, 3, w-4, 11, w-11, 4], fill=color)
        
    elif name == "rectangle":
        draw.rectangle([3, 3, w-3, h-3], outline=color, width=1.5)
        
    elif name == "circle":
        draw.ellipse([3, 3, w-3, h-3], outline=color, width=1.5)
        
    elif name == "text":
        draw.line([3, 4, w-3, 4], fill=color, width=1.5)
        draw.line([w//2, 4, w//2, h-4], fill=color, width=1.5)
        draw.line([w//2-3, h-4, w//2+3, h-4], fill=color, width=1.5)
        
    elif name == "eraser":
        draw.polygon([(3, h-6), (7, h-3), (w-3, 7), (w-7, 4)], outline=color, width=1.5)
        draw.line([(7, h-10), (12, h-7)], fill=color, width=1.5)
        
    elif name == "crop":
        draw.line([(3, 7), (w-6, 7)], fill=color, width=1.5)
        draw.line([(7, 3), (7, h-6)], fill=color, width=1.5)
        draw.line([(w-7, 7), (w-7, h-3)], fill=color, width=1.5)
        draw.line([(7, h-7), (w-3, h-7)], fill=color, width=1.5)
        
    elif name in ("select", "pointer"):
        # Scaled vector pointer cursor arrow
        p_coords = [
            (int(w*0.16), int(h*0.16)),
            (int(w*0.16), int(h*0.75)),
            (int(w*0.33), int(h*0.58)),
            (int(w*0.5), int(h*0.75)),
            (int(w*0.58), int(h*0.66)),
            (int(w*0.42), int(h*0.5)),
            (int(w*0.62), int(h*0.5))
        ]
        draw.polygon(p_coords, fill=color)
        
    elif name == "zoom_in":
        draw.ellipse([2, 2, w-8, h-8], outline=color, width=1.5)
        draw.line([w-9, h-9, w-3, h-3], fill=color, width=2.5)
        cx, cy = (w-5)//2, (h-5)//2
        draw.line([cx-3, cy, cx+3, cy], fill=color, width=1.5)
        draw.line([cx, cy-3, cx, cy+3], fill=color, width=1.5)
        
    elif name == "zoom_out":
        draw.ellipse([2, 2, w-8, h-8], outline=color, width=1.5)
        draw.line([w-9, h-9, w-3, h-3], fill=color, width=2.5)
        cx, cy = (w-5)//2, (h-5)//2
        draw.line([cx-3, cy, cx+3, cy], fill=color, width=1.5)
        
    elif name == "undo":
        draw.arc([3, 5, w-3, h-3], 120, 310, fill=color, width=1.5)
        draw.polygon([(3, 9), (3, 3), (9, 6)], fill=color)
        
    elif name == "redo":
        draw.arc([3, 5, w-3, h-3], 230, 60, fill=color, width=1.5)
        draw.polygon([(w-3, 9), (w-3, 3), (w-9, 6)], fill=color)
        
    elif name == "save":
        draw.rectangle([3, 3, w-3, h-3], outline=color, width=1.5)
        draw.rectangle([6, 3, w-6, 8], fill=color)
        draw.rectangle([6, h-9, w-6, h-3], outline=color, width=1.5)
        
    elif name == "copy":
        draw.rectangle([3, 6, w-6, h-3], outline=color, width=1.5)
        draw.rectangle([6, 3, w-3, h-6], outline=color, width=1.5)
        
    elif name == "settings":
        draw.ellipse([w//2-3, h//2-3, w//2+3, h//2+3], outline=color, width=1.5)
        draw.ellipse([w//2-6, h//2-6, w//2+6, h//2+6], outline=color, width=1.5)
        for i in range(8):
            angle = i * (math.pi / 4)
            x1 = int(w//2 + 5 * math.cos(angle))
            y1 = int(h//2 + 5 * math.sin(angle))
            x2 = int(w//2 + 8 * math.cos(angle))
            y2 = int(h//2 + 8 * math.sin(angle))
            draw.line([x1, y1, x2, y2], fill=color, width=1.5)
            
    elif name == "clear":
        draw.line([3, 5, w-3, 5], fill=color, width=1.5)
        draw.rectangle([w//2-3, 2, w//2+3, 5], outline=color, width=1.5)
        draw.rectangle([5, 6, w-5, h-3], outline=color, width=1.5)
        draw.line([(8, 8), (8, h-6)], fill=color, width=1.5)
        draw.line([(w-8, 8), (w-8, h-6)], fill=color, width=1.5)

def get_icon(name, color="#333333", size=(24, 24)):
    """Generates and returns a Tkinter PhotoImage for the requested icon in Light/Dark themes."""
    key = (name, color, size)
    if key in icon_cache:
        return icon_cache[key]
        
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw_vector_icon(draw, name, color, size)
    
    tk_img = ImageTk.PhotoImage(img)
    icon_cache[key] = tk_img
    return tk_img

def get_button_image(name, icon_color, bg_color, border_color=None, size=(30, 30), icon_size=(16, 16)):
    """Generates a PhotoImage containing a rounded rectangle background and the centered vector icon."""
    key = (name, icon_color, bg_color, border_color, size, icon_size)
    if key in icon_cache:
        return icon_cache[key]
        
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw rounded background
    if bg_color:
        draw.rounded_rectangle([0, 0, w-1, h-1], radius=5, fill=bg_color)
    if border_color:
        draw.rounded_rectangle([0, 0, w-1, h-1], radius=5, outline=border_color, width=1)
        
    # Create icon layer
    icon_layer = Image.new("RGBA", icon_size, (0, 0, 0, 0))
    icon_draw = ImageDraw.Draw(icon_layer)
    draw_vector_icon(icon_draw, name, icon_color, icon_size)
    
    # Paste icon layer centered on the button background
    ix, iy = (w - icon_size[0]) // 2, (h - icon_size[1]) // 2
    img.paste(icon_layer, (ix, iy), mask=icon_layer)
    
    tk_img = ImageTk.PhotoImage(img)
    icon_cache[key] = tk_img
    return tk_img
