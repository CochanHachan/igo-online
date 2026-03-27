#!/usr/bin/env python3
"""GlossyButton 実装担当者向けサンプルコード

glossy_button.py と同じフォルダに置いて使用してください。
text と width は動的な値に置き換えてください。

使い方:
    python button_usage_example.py
"""
import tkinter as tk
from glossy_button import GlossyButton


def main():
    root = tk.Tk()
    root.title("GlossyButton 呼び出しサンプル")
    root.configure(bg="#efe5d2")

    # =================================================================
    # デザイン1: ログインボタン（緑）
    # =================================================================

    btn1 = GlossyButton(
        root,
        text="ログイン",                    # ← 動的な文字列に置き換え
        width=180,                          # ← 動的な幅に置き換え
        height=44,                          # ← 動的な高さに置き換え
        # --- デザインパラメータ（固定値） ---
        base_color=(60, 160, 60),           # ボタンの基本色: 緑
        text_color="white",                 # 文字色: 白
        font=("Yu Gothic UI", 13, "bold"),  # フォント
        focus_border_width=3,               # フォーカス縁の太さ
        focus_border_color=None,            # フォーカス縁の色, None=デフォルト青
        depth=1.0,                          # 立体感の強さ (0.0=フラット ～ 2.0=非常に立体的)
        command=None,                       # ← クリック時の処理に置き換え
        bg=root.cget("bg"),
    )
    btn1.pack(pady=(20, 10))

    # =================================================================
    # デザイン2: 取消ボタン（グレー）
    # =================================================================

    btn2 = GlossyButton(
        root,
        text="取消",                        # ← 動的な文字列に置き換え
        width=120,                          # ← 動的な幅に置き換え
        height=36,                          # ← 動的な高さに置き換え
        # --- デザインパラメータ（固定値） ---
        base_color=(140, 140, 140),         # ボタンの基本色: グレー
        text_color="white",                 # 文字色: 白
        font=("Yu Gothic UI", 11, "bold"),  # フォント
        focus_border_width=3,               # フォーカス縁の太さ
        focus_border_color=None,            # フォーカス縁の色, None=デフォルト青
        depth=1.0,                          # 立体感の強さ (0.0=フラット ～ 2.0=非常に立体的)
        command=None,                       # ← クリック時の処理に置き換え
        bg=root.cget("bg"),
    )
    btn2.pack(pady=(5, 20))

    root.mainloop()


if __name__ == "__main__":
    main()
