#!/usr/bin/env python3
"""GlossyButton テスト環境

各パラメータを変更して、ボタンの見た目をリアルタイムで確認できます。
glossy_button.py と同じフォルダに置いて実行してください。

使い方:
    python test_glossy_button.py
"""
import tkinter as tk
from glossy_button import GlossyButton


def main():
    root = tk.Tk()
    root.title("GlossyButton テスト環境")
    root.configure(bg="#2c2c2c")

    # =================================================================
    # ★ ここのパラメータを自由に変更してテストしてください ★
    # =================================================================

    # --- ボタンのサイズ ---
    btn_width = 180          # ボタンの幅（ピクセル）
    btn_height = 44          # ボタンの高さ（ピクセル）

    # --- 文字列 ---
    btn_text = "ログイン"

    # --- ベースカラー ---
    base_color = (60, 160, 60)    # ボタンの基本色 (R, G, B)

    # --- 文字色 ---
    text_color = "white"          # 文字色（"white", "#ff0000", など）

    # --- フォント ---
    btn_font = ("Yu Gothic UI", 13, "bold")  # (フォント名, サイズ, 太さ)

    # --- フォーカス時の縁 ---
    focus_border_width = 3        # フォーカス縁の太さ（ピクセル）
    focus_border_color = None     # フォーカス縁の色, None=デフォルト青

    # =================================================================
    # ★ ここまでパラメータ ★
    # =================================================================

    # --- ヘッダー ---
    tk.Label(root, text="GlossyButton テスト環境",
             fg="white", bg="#2c2c2c",
             font=("", 14, "bold")).pack(pady=(20, 5))
    tk.Label(root, text="パラメータを変更してスクリプトを再実行してください",
             fg="#888888", bg="#2c2c2c",
             font=("", 10)).pack(pady=(0, 15))

    # --- クリック時のログ表示 ---
    log_var = tk.StringVar(value="（ボタンをクリックするとここに表示）")

    def on_click():
        log_var.set(f"「{btn_text}」がクリックされました！")

    # --- メインのボタン（上記パラメータで表示） ---
    btn = GlossyButton(
        root,
        text=btn_text,
        width=btn_width,
        height=btn_height,
        base_color=base_color,
        text_color=text_color,
        font=btn_font,
        focus_border_width=focus_border_width,
        focus_border_color=focus_border_color,
        command=on_click,
        bg="#2c2c2c",
    )
    btn.pack(pady=10)

    # --- クリックログ ---
    tk.Label(root, textvariable=log_var,
             fg="#aaaaaa", bg="#2c2c2c",
             font=("", 10)).pack(pady=(0, 10))

    # --- パラメータ情報表示 ---
    info_frame = tk.Frame(root, bg="#2c2c2c")
    info_frame.pack(pady=10, padx=20, fill="x")

    params = [
        f"サイズ: {btn_width} x {btn_height}",
        f"文字列: {btn_text}",
        f"ベースカラー: {base_color}",
        f"文字色: {text_color}",
        f"フォント: {btn_font}",
        f"フォーカス縁太さ: {focus_border_width}",
        f"フォーカス縁色: {focus_border_color if focus_border_color is not None else 'デフォルト青'}",
    ]
    for p in params:
        tk.Label(info_frame, text=p, fg="#aaaaaa", bg="#2c2c2c",
                 font=("", 9), anchor="w").pack(anchor="w")

    # --- 比較用バリエーション ---
    tk.Label(root, text="── 比較用バリエーション ──",
             fg="#666666", bg="#2c2c2c",
             font=("", 10)).pack(pady=(15, 5))

    # 青いボタン
    GlossyButton(root, text="青いボタン",
                 width=160, height=40,
                 base_color=(50, 100, 200),
                 bg="#2c2c2c").pack(pady=4)

    # 赤いボタン
    GlossyButton(root, text="赤いボタン",
                 width=160, height=40,
                 base_color=(200, 60, 60),
                 bg="#2c2c2c").pack(pady=4)

    # グレー（取消ボタン風）
    GlossyButton(root, text="取消",
                 width=120, height=36,
                 base_color=(140, 140, 140),
                 bg="#2c2c2c").pack(pady=4)

    # 大きいボタン
    GlossyButton(root, text="大きいボタン",
                 width=250, height=55,
                 base_color=(60, 160, 60),
                 font=("Yu Gothic UI", 16, "bold"),
                 bg="#2c2c2c").pack(pady=4)

    # フォーカス縁カスタム色
    GlossyButton(root, text="カスタム縁色",
                 width=160, height=40,
                 base_color=(60, 160, 60),
                 focus_border_color=(255, 165, 0),
                 focus_border_width=4,
                 bg="#2c2c2c").pack(pady=4)

    tk.Label(root, text="Tabキーでフォーカス移動、Enter/Spaceでクリック",
             fg="#666666", bg="#2c2c2c",
             font=("", 9)).pack(pady=(10, 20))

    root.mainloop()


if __name__ == "__main__":
    main()
