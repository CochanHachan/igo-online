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

    # =================================================================
    # ★ ここのパラメータを自由に変更してテストしてください ★
    # =================================================================

    # --- ウィンドウ ---
    window_bg = "#efe5d2"           # 背景色（クリーム色）
    window_width = 400
    window_height = 320

    # --- タイトル ---
    title_text = "\u7881\u83ef \u30ed\u30b0\u30a4\u30f3"   # 碁華 ログイン
    title_font = ("Yu Gothic UI", 16, "bold")
    title_color = "#3a4a3a"

    # --- ラベル ---
    label_font = ("Yu Gothic UI", 9)
    label_color = "#4a4a3a"

    # --- 入力フィールド ---
    entry_width = 320               # フィールドの幅
    entry_height = 34               # フィールドの高さ
    entry_corner_radius = 8         # 角丸の半径
    entry_bg = "white"              # 入力欄の背景色
    entry_border = "#c8c8c0"        # 枠線の色（薄いグレー）
    entry_font = ("Yu Gothic UI", 11)

    # --- ログインボタン（GlossyButton） ---
    login_btn_width = 150
    login_btn_height = 40
    login_btn_color = (60, 145, 60)     # ベースカラー (R, G, B)
    login_btn_text = "\u30ed\u30b0\u30a4\u30f3"
    login_btn_font = ("Yu Gothic UI", 11, "bold")
    login_btn_depth = 1.0

    # --- アカウント作成ボタン（OutlineButton） ---
    reg_btn_width = 150
    reg_btn_height = 40
    reg_btn_text = "\u30a2\u30ab\u30a6\u30f3\u30c8\u4f5c\u6210"
    reg_btn_font = ("Yu Gothic UI", 10)
    reg_btn_bg = "white"
    reg_btn_border = "#c0c0b8"
    reg_btn_text_color = "#505050"

    # =================================================================
    # ★ ここまでパラメータ ★
    # =================================================================

    root.configure(bg=window_bg)
    root.geometry(f"{window_width}x{window_height}")
    root.resizable(False, False)

    # --- タイトル ---
    tk.Label(root, text=title_text, font=title_font,
             bg=window_bg, fg=title_color).pack(pady=(28, 20))

    # --- フォーム ---
    form = tk.Frame(root, bg=window_bg)
    form.pack(padx=35, fill="x")

    # ハンドルネーム
    tk.Label(form, text="\u30cf\u30f3\u30c9\u30eb\u30cd\u30fc\u30e0",
             font=label_font,
             bg=window_bg, fg=label_color, anchor="w").pack(anchor="w")
    name_entry = RoundedEntry(form, width=entry_width, height=entry_height,
                              corner_radius=entry_corner_radius,
                              bg_color=entry_bg, border_color=entry_border,
                              font=entry_font, parent_bg=window_bg)
    name_entry.pack(pady=(2, 6), anchor="w")

    # パスワード
    tk.Label(form, text="\u30d1\u30b9\u30ef\u30fc\u30c9",
             font=label_font,
             bg=window_bg, fg=label_color, anchor="w").pack(anchor="w")
    pw_entry = RoundedEntry(form, width=entry_width, height=entry_height,
                            corner_radius=entry_corner_radius,
                            bg_color=entry_bg, border_color=entry_border,
                            font=entry_font, show="\u25cf", parent_bg=window_bg)
    pw_entry.pack(pady=(2, 18), anchor="w")

    # --- ボタン ---
    btn_frame = tk.Frame(root, bg=window_bg)
    btn_frame.pack()

    GlossyButton(btn_frame, text=login_btn_text,
                 width=login_btn_width, height=login_btn_height,
                 base_color=login_btn_color, text_color="white",
                 font=login_btn_font, depth=login_btn_depth,
                 bg=window_bg).pack(side="left", padx=(0, 6))

    OutlineButton(btn_frame, text=reg_btn_text,
                  width=reg_btn_width, height=reg_btn_height,
                  bg_color=reg_btn_bg, border_color=reg_btn_border,
                  text_color=reg_btn_text_color, font=reg_btn_font,
                  parent_bg=window_bg).pack(side="left", padx=(6, 0))

    name_entry.focus_set()
    root.mainloop()


if __name__ == "__main__":
    main()
