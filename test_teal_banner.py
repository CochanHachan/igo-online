#!/usr/bin/env python3
"""TealBanner テスト環境

各パラメータを変更して、バナーの見た目をリアルタイムで確認できます。
teal_banner.py と同じフォルダに置いて実行してください。

使い方:
    python test_teal_banner.py
"""
import tkinter as tk
from teal_banner import TealBanner


def main():
    root = tk.Tk()
    root.title("TealBanner テスト環境")
    root.configure(bg="#2c2c2c")

    # =================================================================
    # ★ ここのパラメータを自由に変更してテストしてください ★
    # =================================================================

    # --- バナーのサイズ ---
    banner_width = 460       # バナーの幅（ピクセル）
    banner_height = 48       # バナーの高さ（ピクセル）

    # --- 文字列 ---
    banner_text = "山田太郎（初段(中))"

    # --- フォント ---
    banner_font = None       # None=自動検出, またはフォントファイルのパス
                             # 例: "C:/Windows/Fonts/yugothb.ttc"
    banner_font_size = None  # None=高さに合わせて自動, または数値（例: 18）
    banner_font_weight = "bold"  # "bold" または "normal"

    # --- 文字の色 ---
    text_color = (210, 255, 255)       # メインの文字色 (R, G, B)
    text_stroke_color = (0, 10, 15)    # 文字の縁取り色 (R, G, B)

    # --- バックカラー（グラデーション） ---
    bg_edge = (10, 20, 30)             # 端の色（暗い方）(R, G, B)
    bg_center = (50, 110, 130)         # 中央の色（明るい方）(R, G, B)

    # --- グラデーションの強さ ---
    gradient_strength = 1.0  # 0.0=フラット ～ 2.0=非常に強い

    # --- 角の丸み ---
    corner_radius = None     # None=自動, 0=角ばった, 数値=丸みの大きさ

    # --- 外枠（バナーの縁） ---
    border_color = (90, 190, 190)      # 外枠の色, None=外枠なし
    border_width = None                # 外枠の太さ, None=自動

    # --- 内側の装飾 ---
    line_color = None                  # 内側ラインの色, None=ラインなし
    diamond_color = None               # ダイヤモンドの色, None=ダイヤなし

    # =================================================================
    # ★ ここまでパラメータ ★
    # =================================================================

    # --- ヘッダー ---
    tk.Label(root, text="TealBanner テスト環境",
             fg="white", bg="#2c2c2c",
             font=("", 14, "bold")).pack(pady=(20, 5))
    tk.Label(root, text="パラメータを変更してスクリプトを再実行してください",
             fg="#888888", bg="#2c2c2c",
             font=("", 10)).pack(pady=(0, 15))

    # --- メインのバナー（上記パラメータで表示） ---
    banner = TealBanner(
        root,
        text=banner_text,
        width=banner_width,
        height=banner_height,
        font=banner_font,
        font_size=banner_font_size,
        font_weight=banner_font_weight,
        text_color=text_color,
        text_stroke_color=text_stroke_color,
        bg_edge=bg_edge,
        bg_center=bg_center,
        gradient_strength=gradient_strength,
        corner_radius=corner_radius,
        border_color=border_color,
        border_width=border_width,
        line_color=line_color,
        diamond_color=diamond_color,
        bg="#2c2c2c",
    )
    banner.pack(pady=10)

    # --- パラメータ情報表示 ---
    info_frame = tk.Frame(root, bg="#2c2c2c")
    info_frame.pack(pady=10, padx=20, fill="x")

    params = [
        f"サイズ: {banner_width} x {banner_height}",
        f"文字列: {banner_text}",
        f"フォント: {banner_font or '自動検出'} / サイズ: {banner_font_size or '自動'} / {banner_font_weight}",
        f"文字色: {text_color} / 縁取り: {text_stroke_color}",
        f"背景端: {bg_edge} / 背景中央: {bg_center}",
        f"グラデーション強さ: {gradient_strength}",
        f"角の丸み: {corner_radius if corner_radius is not None else '自動'}",
        f"外枠色: {border_color} / 外枠太さ: {border_width if border_width is not None else '自動'}",
        f"内側ライン色: {line_color} / ダイヤ色: {diamond_color}",
    ]
    for p in params:
        tk.Label(info_frame, text=p, fg="#aaaaaa", bg="#2c2c2c",
                 font=("", 9), anchor="w").pack(anchor="w")

    # --- 比較用バリエーション ---
    tk.Label(root, text="── 比較用バリエーション ──",
             fg="#666666", bg="#2c2c2c",
             font=("", 10)).pack(pady=(15, 5))

    # グラデーション弱
    TealBanner(root, text="グラデーション弱 (0.3)",
               width=350, height=36,
               gradient_strength=0.3, bg="#2c2c2c").pack(pady=4)

    # グラデーション強
    TealBanner(root, text="グラデーション強 (2.0)",
               width=350, height=36,
               gradient_strength=2.0, bg="#2c2c2c").pack(pady=4)

    # 角丸なし
    TealBanner(root, text="角丸なし",
               width=250, height=36,
               corner_radius=0, bg="#2c2c2c").pack(pady=4)

    # 外枠なし
    TealBanner(root, text="外枠なし",
               width=250, height=36,
               border_color=None,
               bg="#2c2c2c").pack(pady=4)

    root.mainloop()


if __name__ == "__main__":
    main()
