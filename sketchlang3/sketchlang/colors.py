"""
Colour table shared by the semantic analyser (which colours are legal) and
the back ends (SVG uses the names directly; PostScript needs RGB triples).
RGB values match the CSS named colours so that SVG and PostScript output
look the same.
"""

COLOR_RGB = {
    "black":  (0.0, 0.0, 0.0),
    "red":    (1.0, 0.0, 0.0),
    "green":  (0.0, 128 / 255, 0.0),
    "blue":   (0.0, 0.0, 1.0),
    "orange": (1.0, 165 / 255, 0.0),
    "purple": (128 / 255, 0.0, 128 / 255),
    "brown":  (165 / 255, 42 / 255, 42 / 255),
    "pink":   (1.0, 192 / 255, 203 / 255),
}
