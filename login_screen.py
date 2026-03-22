#!/usr/bin/env python3
"""Tkinter login screen for Go online game with glossy 3D buttons."""
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageTk, ImageFilter


# --------------- Glossy 3D Button Widget ---------------

class GlossyButton(tk.Canvas):
    """A custom Canvas-based button with 3D appearance, gloss, and focus highlight."""

    def __init__(self, master, text="Button", width=180, height=44,
                 base_color=(60, 160, 60), text_color="white",
                 font=("Yu Gothic UI", 13, "bold"), command=None, **kwargs):
        super().__init__(master, width=width, height=height,
                         highlightthickness=0, borderwidth=0, **kwargs)
        self._text = text
        self._width = width
        self._height = height
        self._base_color = base_color
        self._text_color = text_color
        self._font = font
        self._command = command
        self._state = "normal"  # normal, hover, pressed, focused

        # Pre-render button images for each state
        self._images = {}
        self._build_images()

        # Draw initial state
        self._draw("normal")

        # Bind events
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Return>", self._on_key_activate)
        self.bind("<space>", self._on_key_activate)

        # Make focusable
        self.configure(takefocus=True)

    def _lighten(self, color, amount=30):
        return tuple(min(255, c + amount) for c in color)

    def _darken(self, color, amount=30):
        return tuple(max(0, c - amount) for c in color)

    def _calc_gradient(self, base, t, is_pressed):
        """Calculate gradient color at position t (0..1)."""
        if is_pressed:
            if t < 0.5:
                tt = t / 0.5
                r = int(base[0] * 0.75 + tt * base[0] * 0.1)
                g = int(base[1] * 0.75 + tt * base[1] * 0.1)
                b = int(base[2] * 0.75 + tt * base[2] * 0.1)
            else:
                tt = (t - 0.5) / 0.5
                r = int(base[0] * 0.85 + tt * base[0] * 0.05)
                g = int(base[1] * 0.85 + tt * base[1] * 0.05)
                b = int(base[2] * 0.85 + tt * base[2] * 0.05)
        else:
            if t < 0.1:
                tt = t / 0.1
                r = min(255, int(base[0] + (255 - base[0]) * 0.5 * (1 - tt)))
                g = min(255, int(base[1] + (255 - base[1]) * 0.5 * (1 - tt)))
                b = min(255, int(base[2] + (255 - base[2]) * 0.5 * (1 - tt)))
            elif t < 0.45:
                tt = (t - 0.1) / 0.35
                r = min(255, int(base[0] * 1.2 - tt * base[0] * 0.2))
                g = min(255, int(base[1] * 1.2 - tt * base[1] * 0.2))
                b = min(255, int(base[2] * 1.2 - tt * base[2] * 0.2))
            elif t < 0.55:
                tt = (t - 0.45) / 0.1
                r = int(base[0] * (1.0 - tt * 0.15))
                g = int(base[1] * (1.0 - tt * 0.15))
                b = int(base[2] * (1.0 - tt * 0.15))
            else:
                tt = (t - 0.55) / 0.45
                r = int(base[0] * 0.85 - tt * base[0] * 0.1)
                g = int(base[1] * 0.85 - tt * base[1] * 0.1)
                b = int(base[2] * 0.85 - tt * base[2] * 0.1)
        return max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))

    def _render_button(self, base, is_pressed=False, focus_glow=False):
        """Render a glossy 3D button image using Pillow."""
        scale = 3
        w, h = self._width * scale, self._height * scale
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        radius = 8 * scale

        # Shadow (below button, offset)
        if not is_pressed:
            shadow_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_img)
            shadow_offset = 2 * scale
            shadow_draw.rounded_rectangle(
                [2 * scale, shadow_offset + 1 * scale,
                 w - 2 * scale, h - 1 * scale],
                radius=radius, fill=(0, 0, 0, 80)
            )
            shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(radius=2 * scale))
            img = Image.alpha_composite(img, shadow_img)
            draw = ImageDraw.Draw(img)

        # Focus glow ring
        if focus_glow:
            glow_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_img)
            glow_draw.rounded_rectangle(
                [0, 0, w - 1, h - 1],
                radius=radius + 2 * scale,
                fill=(100, 180, 255, 100)
            )
            glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=3 * scale))
            img = Image.alpha_composite(img, glow_img)
            draw = ImageDraw.Draw(img)

        # Button body
        margin = 2 * scale
        top = margin if not is_pressed else margin + 1 * scale
        bottom = h - margin - (2 * scale if not is_pressed else 1 * scale)
        body_rect = [margin, top, w - margin, bottom]

        # Outer border (dark)
        border_color = self._darken(base, 60)
        draw.rounded_rectangle(body_rect, radius=radius, fill=border_color)

        # Inner body with gradient
        inner = [margin + scale, top + scale, w - margin - scale, bottom - scale]
        inner_radius = max(1, radius - scale)

        # Draw gradient fill
        body_h = inner[3] - inner[1]
        for y_off in range(body_h):
            t = y_off / max(1, body_h - 1)
            yy = inner[1] + y_off
            r, g, b = self._calc_gradient(base, t, is_pressed)
            draw.line([(inner[0], yy), (inner[2], yy)], fill=(r, g, b))

        # Rounded corner mask
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle(inner, radius=inner_radius, fill=255)

        # Create body with gradient and apply mask
        body_only = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        body_draw = ImageDraw.Draw(body_only)
        for y_off in range(body_h):
            t = y_off / max(1, body_h - 1)
            yy = inner[1] + y_off
            r, g, b = self._calc_gradient(base, t, is_pressed)
            body_draw.line([(inner[0], yy), (inner[2], yy)], fill=(r, g, b, 255))

        body_masked = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        body_masked.paste(body_only, mask=mask)

        # Composite layers
        border_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(border_layer).rounded_rectangle(
            body_rect, radius=radius, fill=border_color)
        img = Image.alpha_composite(img, border_layer)
        img = Image.alpha_composite(img, body_masked)

        # Glossy highlight overlay (elliptical, top area)
        if not is_pressed:
            gloss = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            gloss_h = body_h // 3
            ImageDraw.Draw(gloss).ellipse(
                [inner[0] + 2 * scale, inner[1],
                 inner[2] - 2 * scale, inner[1] + gloss_h],
                fill=(255, 255, 255, 55)
            )
            gloss = gloss.filter(ImageFilter.GaussianBlur(radius=scale))
            img = Image.alpha_composite(img, gloss)

        # Top edge highlight
        hl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(hl).rounded_rectangle(
            [inner[0] + scale, inner[1], inner[2] - scale, inner[1] + 2 * scale],
            radius=max(1, inner_radius // 2),
            fill=(255, 255, 255, 70 if not is_pressed else 30)
        )
        img = Image.alpha_composite(img, hl)

        return img.resize((self._width, self._height), Image.LANCZOS)

    def _build_images(self):
        """Pre-render all button state images."""
        base = self._base_color
        hover = self._lighten(base, 25)
        pressed = self._darken(base, 20)
        self._images["normal"] = ImageTk.PhotoImage(self._render_button(base))
        self._images["hover"] = ImageTk.PhotoImage(self._render_button(hover))
        self._images["pressed"] = ImageTk.PhotoImage(
            self._render_button(pressed, is_pressed=True))
        self._images["focused"] = ImageTk.PhotoImage(
            self._render_button(base, focus_glow=True))
        self._images["focused_hover"] = ImageTk.PhotoImage(
            self._render_button(hover, focus_glow=True))

    def _draw(self, state):
        self.delete("all")
        img_key = state if state in self._images else "normal"
        self.create_image(0, 0, anchor="nw", image=self._images[img_key])
        cx, cy = self._width // 2, self._height // 2
        if state == "pressed":
            cy += 1
        # Text shadow for depth
        self.create_text(cx + 1, cy + 1, text=self._text,
                         font=self._font, fill="#333333", anchor="center")
        self.create_text(cx, cy, text=self._text,
                         font=self._font, fill=self._text_color, anchor="center")

    def _on_enter(self, event):
        if self._state == "focused":
            self._draw("focused_hover")
        else:
            self._state = "hover"
            self._draw("hover")

    def _on_leave(self, event):
        if self._state == "focused" or self.focus_get() == self:
            self._state = "focused"
            self._draw("focused")
        else:
            self._state = "normal"
            self._draw("normal")

    def _on_press(self, event):
        self._draw("pressed")
        self.focus_set()

    def _on_release(self, event):
        self._state = "focused"
        self._draw("focused_hover")
        if self._command:
            self._command()

    def _on_focus_in(self, event):
        self._state = "focused"
        self._draw("focused")

    def _on_focus_out(self, event):
        self._state = "normal"
        self._draw("normal")

    def _on_key_activate(self, event):
        """Activate button via Enter or Space key."""
        self._draw("pressed")
        self.after(100, lambda: self._draw("focused"))
        if self._command:
            self._command()


# --------------- Login Screen ---------------

class LoginScreen(tk.Tk):
    """Tkinter login screen with glossy 3D buttons."""

    def __init__(self):
        super().__init__()
        self.title("\u56f2\u7881\u30aa\u30f3\u30e9\u30a4\u30f3 - \u30ed\u30b0\u30a4\u30f3")
        self.configure(bg="#2c2c2c")
        self.geometry("460x420")
        self.resizable(False, False)
        self._result = None
        self._build_ui()

    def _build_ui(self):
        bg = "#2c2c2c"
        fg = "#ffffff"
        entry_bg = "#3c3c3c"
        entry_fg = "#ffffff"
        entry_focus_bg = "#50507a"
        label_font = ("Yu Gothic UI", 11)
        entry_font = ("Yu Gothic UI", 12)
        title_font = ("Yu Gothic UI", 18, "bold")

        # Title
        tk.Label(self, text="\u56f2\u7881\u30aa\u30f3\u30e9\u30a4\u30f3", font=title_font,
                 bg=bg, fg=fg).pack(pady=(30, 5))
        tk.Label(self, text="\u30ed\u30b0\u30a4\u30f3", font=("Yu Gothic UI", 12),
                 bg=bg, fg="#c8c8c8").pack(pady=(0, 20))

        # Nickname field
        nick_frame = tk.Frame(self, bg=bg)
        nick_frame.pack(pady=(5, 2))
        tk.Label(nick_frame, text="\u30cb\u30c3\u30af\u30cd\u30fc\u30e0:", font=label_font,
                 bg=bg, fg=fg, anchor="w", width=16).pack(anchor="w")
        self._nick_entry = tk.Entry(nick_frame, font=entry_font, width=30,
                                    bg=entry_bg, fg=entry_fg,
                                    insertbackground=fg, relief="flat",
                                    highlightthickness=2,
                                    highlightcolor="#6688cc",
                                    highlightbackground="#555555")
        self._nick_entry.pack(ipady=4, pady=(2, 0))

        # Password field
        pw_frame = tk.Frame(self, bg=bg)
        pw_frame.pack(pady=(10, 2))
        tk.Label(pw_frame, text="\u30d1\u30b9\u30ef\u30fc\u30c9:", font=label_font,
                 bg=bg, fg=fg, anchor="w", width=16).pack(anchor="w")
        self._pw_entry = tk.Entry(pw_frame, font=entry_font, width=30,
                                  bg=entry_bg, fg=entry_fg,
                                  insertbackground=fg, relief="flat", show="\u25cf",
                                  highlightthickness=2,
                                  highlightcolor="#6688cc",
                                  highlightbackground="#555555")
        self._pw_entry.pack(ipady=4, pady=(2, 0))

        # Save checkbox
        self._save_var = tk.BooleanVar(value=True)
        cb_frame = tk.Frame(self, bg=bg)
        cb_frame.pack(pady=(10, 5))
        tk.Checkbutton(cb_frame, text="\u30ed\u30b0\u30a4\u30f3\u60c5\u5831\u3092\u4fdd\u5b58",
                       variable=self._save_var,
                       font=("Yu Gothic UI", 10), bg=bg, fg="#c8c8c8",
                       selectcolor="#3c3c3c", activebackground=bg,
                       activeforeground="#c8c8c8",
                       highlightthickness=0).pack()

        # Login button (glossy 3D)
        btn_frame = tk.Frame(self, bg=bg)
        btn_frame.pack(pady=(15, 5))
        self._login_btn = GlossyButton(
            btn_frame, text="\u30ed\u30b0\u30a4\u30f3", width=200, height=48,
            base_color=(50, 150, 50), text_color="white",
            font=("Yu Gothic UI", 14, "bold"),
            command=self._do_login, bg=bg
        )
        self._login_btn.pack()

        # Registration link
        link_frame = tk.Frame(self, bg=bg)
        link_frame.pack(pady=(15, 0))
        link = tk.Label(link_frame,
                        text="\u30a2\u30ab\u30a6\u30f3\u30c8\u3092\u304a\u6301\u3061\u3067\u306a\u3044\u65b9\u306f\u3053\u3061\u3089\u304b\u3089\u767b\u9332\u3057\u3066\u304f\u3060\u3055\u3044\u3002",
                        font=("Yu Gothic UI", 9), bg=bg, fg="#64b4ff",
                        cursor="hand2")
        link.pack()
        link.bind("<Enter>", lambda e: link.configure(fg="#8cd2ff"))
        link.bind("<Leave>", lambda e: link.configure(fg="#64b4ff"))
        link.bind("<Button-1>", lambda e: self._show_register())

        # Message label
        self._msg_label = tk.Label(self, text="", font=("Yu Gothic UI", 10),
                                   bg=bg, fg="#cc5050")
        self._msg_label.pack(pady=(10, 0))

        # Tab order & key bindings
        self._nick_entry.focus_set()
        self._nick_entry.bind("<Return>", lambda e: self._pw_entry.focus_set())
        self._pw_entry.bind("<Return>", lambda e: self._do_login())

        # Entry focus color change
        for entry in [self._nick_entry, self._pw_entry]:
            entry.bind("<FocusIn>",
                       lambda e, ent=entry: ent.configure(bg=entry_focus_bg))
            entry.bind("<FocusOut>",
                       lambda e, ent=entry: ent.configure(bg=entry_bg))

    def _do_login(self):
        nickname = self._nick_entry.get().strip()
        password = self._pw_entry.get()
        if not nickname or not password:
            self._msg_label.configure(
                text="\u30cb\u30c3\u30af\u30cd\u30fc\u30e0\u3068\u30d1\u30b9\u30ef\u30fc\u30c9\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044",
                fg="#cc5050")
            return
        self._result = (nickname, password, self._save_var.get())
        self._msg_label.configure(
            text="\u30ed\u30b0\u30a4\u30f3\u4e2d...", fg="#50cc50")
        self.after(300, self.destroy)

    def _show_register(self):
        messagebox.showinfo(
            "\u767b\u9332",
            "\u767b\u9332\u753b\u9762\u306f\u73fe\u5728\u6e96\u5099\u4e2d\u3067\u3059\u3002")

    def get_result(self):
        return self._result


def run_login():
    """Run the login screen and return (nickname, password, save_creds) or None."""
    app = LoginScreen()
    app.mainloop()
    return app.get_result()


if __name__ == "__main__":
    result = run_login()
    if result:
        print(f"Login: nickname={result[0]}, save={result[2]}")
    else:
        print("Login cancelled")
