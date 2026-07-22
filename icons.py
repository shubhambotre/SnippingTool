import math
from PIL import Image, ImageDraw, ImageTk

icon_cache = {}

def get_icon(name, color="#333333", size=(24, 24)):
    """Generates and returns a Tkinter PhotoImage for the requested icon in Light/Dark themes."""
    key = (name, color, size)
    if key in icon_cache:
        return icon_cache[key]
        
    w, h = size
    # Draw transparent RGBA icon canvas
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    if name == "camera":
        draw.rounded_rectangle([3, 6, w-4, h-4], radius=3, outline=color, width=2)
        draw.ellipse([w//2-5, h//2-1, w//2+5, h//2+9], outline=color, width=2)
        draw.ellipse([w-8, 8, w-6, 10], fill=color)
        draw.rectangle([w//2-4, 3, w//2+4, 6], fill=color)
        
    elif name == "pencil":
        draw.polygon([(4, h-4), (8, h-4), (w-4, 8), (w-8, 4)], outline=color, width=2)
        draw.line([(4, h-4), (6, h-6)], fill=color, width=2)
        
    elif name == "highlighter":
        draw.polygon([(4, h-4), (10, h-4), (w-4, 10), (w-10, 4)], outline=color, width=2)
        draw.line([(6, h-14), (14, h-6)], fill=color, width=1)
        
    elif name == "line":
        draw.line([4, h-4, w-4, 4], fill=color, width=3)
        
    elif name == "arrow":
        draw.line([4, h-4, w-8, 8], fill=color, width=3)
        draw.polygon([w-4, 4, w-5, 14, w-14, 5], fill=color)
        
    elif name == "rectangle":
        draw.rectangle([4, 4, w-4, h-4], outline=color, width=2)
        
    elif name == "circle":
        draw.ellipse([4, 4, w-4, h-4], outline=color, width=2)
        
    elif name == "text":
        draw.line([4, 5, w-4, 5], fill=color, width=2)
        draw.line([w//2, 5, w//2, h-5], fill=color, width=2)
        draw.line([w//2-4, h-5, w//2+4, h-5], fill=color, width=2)
        
    elif name == "eraser":
        draw.polygon([(4, h-7), (9, h-4), (w-4, 9), (w-9, 6)], outline=color, width=2)
        draw.line([(9, h-12), (15, h-8)], fill=color, width=2)
        
    elif name == "crop":
        draw.line([(4, 9), (w-8, 9)], fill=color, width=2)
        draw.line([(9, 4), (9, h-8)], fill=color, width=2)
        draw.line([(w-9, 9), (w-9, h-4)], fill=color, width=2)
        draw.line([(9, h-9), (w-4, h-9)], fill=color, width=2)
        
    elif name == "pointer":
        # Non-self-intersecting clean pointer cursor arrow
        draw.polygon([
            (4, 4), (4, 18), (8, 14), (12, 18), 
            (14, 16), (10, 12), (15, 12)
        ], fill=color)
        
    elif name == "undo":
        draw.arc([4, 6, w-4, h-4], 120, 310, fill=color, width=2)
        draw.polygon([(4, 11), (4, 4), (11, 7)], fill=color)
        
    elif name == "redo":
        draw.arc([4, 6, w-4, h-4], 230, 60, fill=color, width=2)
        draw.polygon([(w-4, 11), (w-4, 4), (w-11, 7)], fill=color)
        
    elif name == "save":
        draw.rectangle([4, 4, w-4, h-4], outline=color, width=2)
        draw.rectangle([7, 4, w-7, 10], fill=color)
        draw.rectangle([7, h-10, w-7, h-4], outline=color, width=2)
        
    elif name == "copy":
        draw.rectangle([4, 7, w-7, h-4], outline=color, width=2)
        draw.rectangle([7, 4, w-4, h-7], outline=color, width=2)
        
    elif name == "settings":
        draw.ellipse([w//2-4, h//2-4, w//2+4, h//2+4], outline=color, width=2)
        draw.ellipse([w//2-8, h//2-8, w//2+8, h//2+8], outline=color, width=2)
        for i in range(8):
            angle = i * (math.pi / 4)
            x1 = int(w//2 + 6 * math.cos(angle))
            y1 = int(h//2 + 6 * math.sin(angle))
            x2 = int(w//2 + 10 * math.cos(angle))
            y2 = int(h//2 + 10 * math.sin(angle))
            draw.line([x1, y1, x2, y2], fill=color, width=2)
            
    elif name == "clear":
        draw.line([4, 6, w-4, 6], fill=color, width=2)
        draw.rectangle([w//2-4, 3, w//2+4, 6], outline=color, width=2)
        draw.rectangle([6, 7, w-6, h-4], outline=color, width=2)
        draw.line([(10, 10), (10, h-7)], fill=color, width=2)
        draw.line([(w-10, 10), (w-10, h-7)], fill=color, width=2)
        
    tk_img = ImageTk.PhotoImage(img)
    icon_cache[key] = tk_img
    return tk_img
