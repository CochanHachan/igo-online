#!/usr/bin/env python3
"""Reusable decorative banner widget for Tkinter applications.

Gold-bordered navy banner with elegant decorations, suitable for
notification headers, alerts, and important messages.
"""
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk, ImageFilter, ImageFont
import os


class DecorativeBanner(tk.Canvas):
    """A custom Canvas-based banner with gold border, navy gradient, and decorations.

    Usage::

        import tkinter as tk
        from decorative_banner import DecorativeBanner

        root = tk.Tk()
        banner = DecorativeBanner(root, text="対局の申し込みです！",
                                  width=380, height=70)
        banner.pack(pady=20)
        root.mainloop()
    """

    # Font search paths (tried in order)
    _FONT_CANDIDATES = [
        # Windows
        "C:/Windows/Fonts/yugothb.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
        # macOS
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "/Library/Fonts/Yu Gothic Bold.otf",
        # Linux
        "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
        "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    ]

    def __init__(self, master, text="Banner", width=380, height=70,
                 font=None, font_size=None, text_color=(240, 215, 140),
                 border_color=(180, 150, 80), bg_top=(25, 35, 65),
                 bg_bottom=(40, 55, 90), line_color=(210, 180, 100),
                 diamond_color=(220, 190, 110), **kwargs):
        super().__init__(master, width=width, height=height,
                         highlightthickness=0, borderwidth=0, **kwargs)
        self._text = text
        self._width = width
        self._height = height
        self._font_spec = font
        self._font_size = font_size
        self._text_color = text_color
        self._border_color = border_color
        self._bg_top = bg_top
        self._bg_bottom = bg_bottom
        self._line_color = line_color
        self._diamond_color = diamond_color

        self._photo = None
        self._render()

    def _find_font(self, size):
        """Find an available font, preferring user-specified font."""
        if self._font_spec is not None:
            # User specified a font family name or path
            if os.path.isfile(self._font_spec):
                return ImageFont.truetype(self._font_spec, size)
            try:
                return ImageFont.truetype(self._font_spec, size)
            except (OSError, IOError):
                pass

        for path in self._FONT_CANDIDATES:
            if os.path.isfile(path):
                try:
                    return ImageFont.truetype(path, size)
                except (OSError, IOError):
                    continue
        return ImageFont.load_default()

    def _smooth(self, t):
        """Smoothstep for natural gradient transitions."""
        t = max(0.0, min(1.0, t))
        return t * t * (3.0 - 2.0 * t)

    def _blend(self, c1, c2, t):
        """Linearly blend two RGB tuples."""
        return (
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t),
        )

    def _render(self):
        """Render the banner image and display it on the canvas."""
        scale = 3
        sw, sh = self._width * scale, self._height * scale
        img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        radius = min(12 * scale, sh // 3)

        # --- Gold border ---
        draw.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=radius,
                               fill=self._border_color)

        # --- Inner gradient (navy) ---
        inner_m = 3 * scale
        inner = [inner_m, inner_m, sw - inner_m, sh - inner_m]
        inner_r = max(1, radius - inner_m)

        grad = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for y in range(inner[1], inner[3]):
            t = (y - inner[1]) / max(1, inner[3] - inner[1] - 1)
            st = self._smooth(t)
            r, g, b = self._blend(self._bg_top, self._bg_bottom, st)
            gd.line([(inner[0], y), (inner[2], y)], fill=(r, g, b, 255))

        mask = Image.new("L", (sw, sh), 0)
        ImageDraw.Draw(mask).rounded_rectangle(inner, radius=inner_r, fill=255)
        gm = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        gm.paste(grad, mask=mask)
        img = Image.alpha_composite(img, gm)

        # --- Subtle top highlight ---
        hl = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        ImageDraw.Draw(hl).ellipse(
            [sw // 5, inner[1] - sh // 6, sw * 4 // 5, inner[1] + sh // 4],
            fill=(255, 255, 255, 18)
        )
        hl = hl.filter(ImageFilter.GaussianBlur(radius=2 * scale))
        hl_masked = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        hl_masked.paste(hl, mask=mask)
        img = Image.alpha_composite(img, hl_masked)

        # --- Decorative gold lines (top and bottom) ---
        line_layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        ld = ImageDraw.Draw(line_layer)
        line_alpha = (*self._line_color, 140)
        line_inset_x = max(15 * scale, sw // 12)
        line_inset_y = max(6 * scale, sh // 10)
        ld.line([(inner[0] + line_inset_x, inner[1] + line_inset_y),
                 (inner[2] - line_inset_x, inner[1] + line_inset_y)],
                fill=line_alpha, width=scale)
        ld.line([(inner[0] + line_inset_x, inner[3] - line_inset_y),
                 (inner[2] - line_inset_x, inner[3] - line_inset_y)],
                fill=line_alpha, width=scale)
        img = Image.alpha_composite(img, line_layer)

        # --- Diamond decorations (left and right) ---
        ds = max(3 * scale, sh // 18)
        diamond_inset = max(12 * scale, sw // 18)
        for cx in [inner[0] + diamond_inset, inner[2] - diamond_inset]:
            cy = sh // 2
            dl = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
            ImageDraw.Draw(dl).polygon(
                [(cx, cy - ds), (cx + ds, cy),
                 (cx, cy + ds), (cx - ds, cy)],
                fill=(*self._diamond_color, 200)
            )
            img = Image.alpha_composite(img, dl)

        # --- Text ---
        auto_font_size = self._font_size if self._font_size else max(10, self._height * scale // 5)
        pil_font = self._find_font(auto_font_size)

        txt = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        td = ImageDraw.Draw(txt)
        bbox = td.textbbox((0, 0), self._text, font=pil_font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (sw - tw) // 2
        ty = (sh - th) // 2 - bbox[1]

        # Text shadow
        td.text((tx + scale, ty + scale), self._text, font=pil_font,
                fill=(0, 0, 0, 120))
        # Main text
        td.text((tx, ty), self._text, font=pil_font,
                fill=(*self._text_color, 255))
        img = Image.alpha_composite(img, txt)

        # --- Downscale with antialiasing ---
        final = img.resize((self._width, self._height), Image.LANCZOS)

        self._photo = ImageTk.PhotoImage(final)
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=self._photo)

    def update_text(self, text):
        """Update the displayed text and re-render."""
        self._text = text
        self._render()

    def update_size(self, width, height):
        """Update the banner size and re-render."""
        self._width = width
        self._height = height
        self.configure(width=width, height=height)
        self._render()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("DecorativeBanner Demo")
    root.configure(bg="#2c2c2c")
    root.geometry("500x400")

    tk.Label(root, text="DecorativeBanner デモ", fg="white", bg="#2c2c2c",
             font=("", 14, "bold")).pack(pady=(20, 10))

    # Default size
    b1 = DecorativeBanner(root, text="対局の申し込みです！",
                          width=380, height=70, bg="#2c2c2c")
    b1.pack(pady=10)

    # Smaller
    b2 = DecorativeBanner(root, text="あなたの番です", width=280, height=50,
                          bg="#2c2c2c")
    b2.pack(pady=10)

    # Wider, different text
    b3 = DecorativeBanner(root, text="対局が終了しました",
                          width=420, height=60, bg="#2c2c2c")
    b3.pack(pady=10)

    # Compact
    b4 = DecorativeBanner(root, text="通知", width=150, height=40,
                          bg="#2c2c2c")
    b4.pack(pady=10)

    root.mainloop()
