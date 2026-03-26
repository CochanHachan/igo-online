#!/usr/bin/env python3
"""login_form.py テスト環境

各パラメータを変更して、ログイン画面の見た目をリアルタイムで確認できます。
login_form.py, glossy_button.py と同じフォルダに置いて実行してください。

使い方:
    python test_login_form.py
"""
import tkinter as tk
from login_form import RoundedEntry, OutlineButton
from glossy_button import GlossyButton


def main():
    root = tk.Tk()
    root.title("LoginForm テスト環境")

    # =================================================================
    # ★ ここのパラメータを自由に変更してテストしてください ★
    # =================================================================

    # --- ウィンドウ背景色 ---
    window_bg = "#efe5d2"           # クリーム色（碁華の背景）

    # --- ウィンドウサイズ ---
    window_width = 420
    window_height = 500

    # --- タイトル ---
    title_text = "碁華 ログイン"
    title_font = ("Yu Gothic UI", 18, "bold")
    title_color = "#2a3a2a"

    # --- ラベル ---
    label_font = ("Yu Gothic UI", 10)
    label_color = "#3a3a2a"

    # --- 入力フィールド ---
    entry_width = 340               # フィールドの幅
    entry_height = 36               # フィールドの高さ
    entry_corner_radius = 10        # 角丸の半径
    entry_bg = "white"              # 入力欄の背景色
    entry_border = "#c0c0c0"        # 枠線の色
    entry_font = ("Yu Gothic UI", 11)

    # --- ログインボタン（GlossyButton） ---
    login_btn_width = 155
    login_btn_height = 42
    login_btn_color = (50, 150, 50)     # ベースカラー (R, G, B)
    login_btn_text = "ログイン"
    login_btn_font = ("Yu Gothic UI", 12, "bold")
    login_btn_depth = 1.0               # 立体感 (0.0～2.0)

    # --- アカウント作成ボタン（OutlineButton） ---
    reg_btn_width = 155
    reg_btn_height = 42
    reg_btn_text = "アカウント作成"
    reg_btn_font = ("Yu Gothic UI", 11)
    reg_btn_bg = "white"
    reg_btn_border = "#b0b0b0"
    reg_btn_text_color = "#444444"

    # =================================================================
    # ★ ここまでパラメータ ★
    # =================================================================

    root.configure(bg=window_bg)
    root.geometry(f"{window_width}x{window_height}")
    root.resizable(False, False)

    # --- ヘッダー ---
    tk.Label(root, text="LoginForm テスト環境",
             fg="black", bg=window_bg,
             font=("", 12, "bold")).pack(pady=(10, 2))
    tk.Label(root, text="パラメータを変更してスクリプトを再実行してください",
             fg="#888888", bg=window_bg,
             font=("", 9)).pack(pady=(0, 10))

    # --- プレビュー枠 ---
    preview = tk.Frame(root, bg=window_bg)
    preview.pack(padx=20, fill="x")

    # タイトル
    tk.Label(preview, text=title_text, font=title_font,
             bg=window_bg, fg=title_color).pack(pady=(10, 15))

    # フォーム
    form = tk.Frame(preview, bg=window_bg)
    form.pack(padx=20, fill="x")

    # ハンドルネーム
    tk.Label(form, text="ハンドルネーム", font=label_font,
             bg=window_bg, fg=label_color, anchor="w").pack(anchor="w")
    name_entry = RoundedEntry(form, width=entry_width, height=entry_height,
                              corner_radius=entry_corner_radius,
                              bg_color=entry_bg, border_color=entry_border,
                              font=entry_font, parent_bg=window_bg)
    name_entry.pack(pady=(2, 8), anchor="w")

    # パスワード
    tk.Label(form, text="パスワード", font=label_font,
             bg=window_bg, fg=label_color, anchor="w").pack(anchor="w")
    pw_entry = RoundedEntry(form, width=entry_width, height=entry_height,
                            corner_radius=entry_corner_radius,
                            bg_color=entry_bg, border_color=entry_border,
                            font=entry_font, show="●", parent_bg=window_bg)
    pw_entry.pack(pady=(2, 15), anchor="w")

    # ボタン
    btn_frame = tk.Frame(preview, bg=window_bg)
    btn_frame.pack(pady=(5, 0))

    log_var = tk.StringVar(value="")

    def on_login():
        log_var.set(f"ログイン: {name_entry.get()}")

    def on_register():
        log_var.set("アカウント作成がクリックされました")

    GlossyButton(btn_frame, text=login_btn_text,
                 width=login_btn_width, height=login_btn_height,
                 base_color=login_btn_color, text_color="white",
                 font=login_btn_font, depth=login_btn_depth,
                 command=on_login,
                 bg=window_bg).pack(side="left", padx=(0, 8))

    OutlineButton(btn_frame, text=reg_btn_text,
                  width=reg_btn_width, height=reg_btn_height,
                  bg_color=reg_btn_bg, border_color=reg_btn_border,
                  text_color=reg_btn_text_color, font=reg_btn_font,
                  command=on_register,
                  parent_bg=window_bg).pack(side="left", padx=(8, 0))

    # クリックログ
    tk.Label(preview, textvariable=log_var,
             fg="#555555", bg=window_bg,
             font=("", 10)).pack(pady=(8, 5))

    # --- パラメータ情報表示 ---
    tk.Label(root, text="── 現在のパラメータ ──",
             fg="#888888", bg=window_bg,
             font=("", 9)).pack(pady=(10, 3))

    info_frame = tk.Frame(root, bg=window_bg)
    info_frame.pack(padx=30, fill="x")

    params = [
        f"背景色: {window_bg}",
        f"入力欄サイズ: {entry_width} x {entry_height}",
        f"角丸半径: {entry_corner_radius}",
        f"ログインボタン色: {login_btn_color}",
        f"ログインボタン depth: {login_btn_depth}",
        f"枠線ボタン背景: {reg_btn_bg}",
        f"枠線ボタン枠色: {reg_btn_border}",
    ]
    for p in params:
        tk.Label(info_frame, text=p, fg="#555555", bg=window_bg,
                 font=("", 9), anchor="w").pack(anchor="w")

    name_entry.focus_set()
    root.mainloop()


if __name__ == "__main__":
    main()
