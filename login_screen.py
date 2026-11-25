#!/usr/bin/env python3
"""Tkinter login screen for Go online game with glossy 3D buttons."""
import tkinter as tk
from tkinter import messagebox
from glossy_button import GlossyButton


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
            focus_border_color=(40, 120, 40),
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
