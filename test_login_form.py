#!/usr/bin/env python3
"""login_form.py テスト環境

パラメータを変更して、ログイン画面の見た目をリアルタイムで確認できます。
login_form.py, glossy_button.py と同じフォルダに置いて実行してください。

使い方:
    python test_login_form.py
"""
import tkinter as tk
from login_form import RoundedEntry, OutlineButton
from glossy_button import GlossyButton


def main():
    root = tk.Tk()
    root.title("\u7881\u83ef")  # 碁華

    # --- デザインパラメータ ---
    window_bg = "white"
    window_width = 460
    window_height = 420
    green = "#3a7a3a"

    title_text = "\u7881\u83ef \u30ed\u30b0\u30a4\u30f3"
    title_font = ("Yu Gothic UI", 18, "bold")
    title_color = green

    label_font = ("Yu Gothic UI", 10)
    label_color = "#333333"

    entry_width = 380
    entry_height = 42
    entry_border = "#c0c0c0"
    entry_focus_border = green
    entry_font = ("Yu Gothic UI", 11)

    login_btn_width = 180
    login_btn_height = 46
    login_btn_color = (55, 130, 55)
    login_btn_text = "\u30ed\u30b0\u30a4\u30f3"
    login_btn_font = ("Yu Gothic UI", 13, "bold")
    login_btn_depth = 0.6

    reg_btn_width = 180
    reg_btn_height = 46
    reg_btn_corner_radius = 10
    reg_btn_text = "\u30a2\u30ab\u30a6\u30f3\u30c8\u4f5c\u6210"
    reg_btn_font = ("Yu Gothic UI", 12)
    reg_btn_border = "#4a8c4a"
    reg_btn_text_color = "#3a6a3a"

    root.configure(bg=window_bg)
    root.geometry(f"{window_width}x{window_height}")
    root.resizable(False, False)

    # --- タイトル ---
    tk.Label(root, text=title_text, font=title_font,
             bg=window_bg, fg=title_color).pack(pady=(35, 30))

    # --- フォーム ---
    form = tk.Frame(root, bg=window_bg)
    form.pack(padx=40, fill="x")

    # ハンドルネーム
    tk.Label(form, text="\u30cf\u30f3\u30c9\u30eb\u30cd\u30fc\u30e0",
             font=label_font,
             bg=window_bg, fg=label_color, anchor="w").pack(anchor="w")
    name_entry = RoundedEntry(form, width=entry_width, height=entry_height,
                              border_color=entry_border,
                              focus_border_color=entry_focus_border,
                              font=entry_font, parent_bg=window_bg)
    name_entry.pack(pady=(4, 12), anchor="w")

    # パスワード
    tk.Label(form, text="\u30d1\u30b9\u30ef\u30fc\u30c9",
             font=label_font,
             bg=window_bg, fg=label_color, anchor="w").pack(anchor="w")
    pw_entry = RoundedEntry(form, width=entry_width, height=entry_height,
                            border_color=entry_border,
                            focus_border_color=entry_focus_border,
                            font=entry_font, parent_bg=window_bg)
    pw_entry.pack(pady=(4, 25), anchor="w")

    # --- ボタン ---
    btn_frame = tk.Frame(form, bg=window_bg)
    btn_frame.pack(anchor="w")

    GlossyButton(btn_frame, text=login_btn_text,
                 width=login_btn_width, height=login_btn_height,
                 base_color=login_btn_color, text_color="white",
                 font=login_btn_font, depth=login_btn_depth,
                 bg=window_bg).pack(side="left", padx=(0, 10))

    OutlineButton(btn_frame, text=reg_btn_text,
                  width=reg_btn_width, height=reg_btn_height,
                  corner_radius=reg_btn_corner_radius,
                  border_color=reg_btn_border,
                  text_color=reg_btn_text_color, font=reg_btn_font,
                  parent_bg=window_bg).pack(side="left")

    name_entry.focus_set()
    root.mainloop()


if __name__ == "__main__":
    main()
