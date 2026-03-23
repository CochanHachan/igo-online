#!/usr/bin/env python3
"""Reusable decorative banner widget for Tkinter applications.

Gold-bordered navy banner with elegant decorations, suitable for
notification headers, alerts, and important messages.
"""
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk, ImageFilter, ImageFont
import os


class DecorativeBanner(tk.Canvas):
    """A custom Canvas-based banner with metallic gold border, navy gradient,
    and decorations.

    Usage::

        import tkinter as tk
        from decorative_banner import DecorativeBanner

        root = tk.Tk()
        banner = DecorativeBanner(root, text="対局の申し込みです！",
                                  width=380, height=70)
        banner.pack(pady=20)
        root.mainloop()
    """

    # Font search paths — bold serif preferred, then bold gothic, then regular
    _FONT_CANDIDATES = [
        # Bold serif (closest to reference image)
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
        "/usr/share/fonts/opentype/ipafont-mincho/ipam.ttf",
        # Windows serif / bold
        "C:/Windows/Fonts/yumindb.ttf",
        "C:/Windows/Fonts/msmincho.ttc",
        "C:/Windows/Fonts/yugothb.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        # macOS
        "/System/Library/Fonts/ヒラギノ明朝 ProN W6.otf",
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        # Linux gothic fallback
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
        "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]

    def __init__(self, master, text="Banner", width=380, height=70,
                 font=None, font_size=None, text_color=(240, 215, 140),
                 text_stroke_color=(30, 20, 10),
                 border_color_light=(230, 200, 120),
                 border_color_dark=(120, 85, 30),
                 bg_top=(30, 35, 65), bg_bottom=(45, 55, 95),
                 line_color=(180, 155, 90), diamond_color=(210, 185, 110),
                 **kwargs):
        super().__init__(master, width=width, height=height,
                         highlightthickness=0, borderwidth=0, **kwargs)
        self._text = text
        self._width = width
        self._height = height
        self._font_spec = font
        self._font_size = font_size
        self._text_color = text_color
        self._text_stroke_color = text_stroke_color
        self._border_color_light = border_color_light
        self._border_color_dark = border_color_dark
        self._bg_top = bg_top
        self._bg_bottom = bg_bottom
        self._line_color = line_color
        self._diamond_color = diamond_color

        self._photo = None
        self._render()

    def _find_font(self, size):
        """Find an available font, preferring user-specified font."""
        if self._font_spec is not None:
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
        scale = 4
        sw, sh = self._width * scale, self._height * scale
        img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))

        radius = min(10 * scale, sh // 4)
        border_w = max(4 * scale, sh // 8)

        # --- Metallic gold border (vertical gradient: dark->light->dark) ---
        border_layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        bd = ImageDraw.Draw(border_layer)
        for y in range(sh):
            t = y / max(1, sh - 1)
            if t < 0.5:
                mt = t / 0.5
            else:
                mt = (1.0 - t) / 0.5
            mt = self._smooth(mt)
            r, g, b = self._blend(self._border_color_dark,
                                  self._border_color_light, mt)
            bd.line([(0, y), (sw, y)], fill=(r, g, b, 255))

        outer_mask = Image.new("L", (sw, sh), 0)
        ImageDraw.Draw(outer_mask).rounded_rectangle(
            [0, 0, sw - 1, sh - 1], radius=radius, fill=255)
        border_masked = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        border_masked.paste(border_layer, mask=outer_mask)
        img = Image.alpha_composite(img, border_masked)

        # --- Thin bright inner edge ---
        edge_layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        edge_m = border_w - scale
        edge_rect = [edge_m, edge_m, sw - edge_m, sh - edge_m]
        edge_r = max(1, radius - edge_m)
        ImageDraw.Draw(edge_layer).rounded_rectangle(
            edge_rect, radius=edge_r,
            outline=(*self._border_color_light, 120), width=scale)
        img = Image.alpha_composite(img, edge_layer)

        # --- Inner gradient (dark navy) ---
        inner = [border_w, border_w, sw - border_w, sh - border_w]
        inner_r = max(1, radius - border_w)

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

        # --- Top highlight (subtle glow) ---
        hl = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        ImageDraw.Draw(hl).ellipse(
            [sw // 5, inner[1] - sh // 8, sw * 4 // 5, inner[1] + sh // 4],
            fill=(180, 200, 255, 15)
        )
        hl = hl.filter(ImageFilter.GaussianBlur(radius=3 * scale))
        hl_masked = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        hl_masked.paste(hl, mask=mask)
        img = Image.alpha_composite(img, hl_masked)

        # --- Inner border: thin dark line around navy area ---
        inner_border = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        ImageDraw.Draw(inner_border).rounded_rectangle(
            inner, radius=inner_r,
            outline=(15, 15, 30, 180), width=scale)
        img = Image.alpha_composite(img, inner_border)

        # --- Decorative gold lines (top and bottom, inside navy area) ---
        line_layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        ld = ImageDraw.Draw(line_layer)
        line_alpha = (*self._line_color, 120)
        line_inset_x = max(15 * scale, sw // 10)
        line_inset_y = max(5 * scale, (inner[3] - inner[1]) // 7)
        ld.line([(inner[0] + line_inset_x, inner[1] + line_inset_y),
                 (inner[2] - line_inset_x, inner[1] + line_inset_y)],
                fill=line_alpha, width=scale)
        ld.line([(inner[0] + line_inset_x, inner[3] - line_inset_y),
                 (inner[2] - line_inset_x, inner[3] - line_inset_y)],
                fill=line_alpha, width=scale)
        img = Image.alpha_composite(img, line_layer)

        # --- Diamond decorations (left and right) ---
        ds = max(3 * scale, (inner[3] - inner[1]) // 12)
        diamond_inset = max(12 * scale, sw // 16)
        for cx in [inner[0] + diamond_inset, inner[2] - diamond_inset]:
            cy = sh // 2
            dl = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
            ImageDraw.Draw(dl).polygon(
                [(cx, cy - ds), (cx + ds, cy),
                 (cx, cy + ds), (cx - ds, cy)],
                fill=(*self._diamond_color, 180)
            )
            img = Image.alpha_composite(img, dl)

        # --- Text ---
        auto_font_size = (self._font_size * scale if self._font_size
                          else max(12, self._height * scale // 5))
        pil_font = self._find_font(auto_font_size)

        txt = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        td = ImageDraw.Draw(txt)
        bbox = td.textbbox((0, 0), self._text, font=pil_font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (sw - tw) // 2
        ty = (sh - th) // 2 - bbox[1]

        # Text stroke (outline) for depth
        stroke_color = (*self._text_stroke_color, 200)
        for dx in (-scale, 0, scale):
            for dy in (-scale, 0, scale):
                if dx == 0 and dy == 0:
                    continue
                td.text((tx + dx, ty + dy), self._text, font=pil_font,
                        fill=stroke_color)

        # Text shadow (subtle drop)
        td.text((tx + scale, ty + scale), self._text, font=pil_font,
                fill=(0, 0, 0, 100))
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
    root.geometry("550x420")

    tk.Label(root, text="DecorativeBanner デモ", fg="white", bg="#2c2c2c",
             font=("", 14, "bold")).pack(pady=(20, 10))

    # Reference style
    b1 = DecorativeBanner(root, text="挑戦状が届いています！",
                          width=420, height=60, bg="#2c2c2c")
    b1.pack(pady=8)

    # Default size
    b2 = DecorativeBanner(root, text="対局の申し込みです！",
                          width=380, height=70, bg="#2c2c2c")
    b2.pack(pady=8)

    # Smaller
    b3 = DecorativeBanner(root, text="あなたの番です", width=280, height=50,
                          bg="#2c2c2c")
    b3.pack(pady=8)

    # Wider
    b4 = DecorativeBanner(root, text="対局が終了しました",
                          width=450, height=55, bg="#2c2c2c")
    b4.pack(pady=8)

    # Compact
    b5 = DecorativeBanner(root, text="通知", width=150, height=40,
                          bg="#2c2c2c")
    b5.pack(pady=8)

    root.mainloop()
