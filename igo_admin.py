#!/usr/bin/env python3
"""
囲碁オンライン 管理者パネル
登録ユーザー一覧を表示するシンプルな管理ツールです。

使い方:
    python igo_admin.py
    python igo_admin.py --server https://app-aiszfyoe.fly.dev
"""

import sys
import urllib.request
import urllib.error
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox

DEFAULT_SERVER = "https://igo-online.onrender.com"


def fetch_users(server_url):
    """サーバーからユーザー一覧を取得"""
    url = f"{server_url}/admin/users"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return data["users"]
            else:
                raise Exception(data.get("error", "不明なエラー"))
    except urllib.error.URLError as e:
        raise Exception(f"サーバーに接続できません: {e}")
    except json.JSONDecodeError:
        raise Exception("サーバーからの応答を解析できません")


class AdminApp:
    def __init__(self, server_url):
        self.server_url = server_url
        self.root = tk.Tk()
        self.root.title("囲碁オンライン 管理者パネル")
        self.root.geometry("800x500")
        self.root.minsize(600, 350)

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Header frame
        header = tk.Frame(self.root, padx=10, pady=8)
        header.pack(fill=tk.X)

        tk.Label(header, text="囲碁オンライン 管理者パネル",
                 font=("", 16, "bold")).pack(side=tk.LEFT)

        refresh_btn = tk.Button(header, text="更新", command=self.refresh,
                                font=("", 11), padx=12, pady=2)
        refresh_btn.pack(side=tk.RIGHT)

        # Server info
        info_frame = tk.Frame(self.root, padx=10)
        info_frame.pack(fill=tk.X)

        self.server_label = tk.Label(info_frame,
                                     text=f"サーバー: {self.server_url}",
                                     font=("", 10), fg="gray")
        self.server_label.pack(side=tk.LEFT)

        self.count_label = tk.Label(info_frame, text="", font=("", 10), fg="gray")
        self.count_label.pack(side=tk.RIGHT)

        # Separator
        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)

        # Table frame
        table_frame = tk.Frame(self.root, padx=10, pady=5)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("id", "name", "nickname", "skill_level", "rating", "created_at")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings",
                                 selectmode="browse")

        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="氏名")
        self.tree.heading("nickname", text="ニックネーム")
        self.tree.heading("skill_level", text="棋力")
        self.tree.heading("rating", text="レーティング")
        self.tree.heading("created_at", text="登録日時")

        self.tree.column("id", width=50, anchor=tk.CENTER)
        self.tree.column("name", width=150)
        self.tree.column("nickname", width=150)
        self.tree.column("skill_level", width=100)
        self.tree.column("rating", width=100, anchor=tk.CENTER)
        self.tree.column("created_at", width=180)

        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Status bar
        self.status_var = tk.StringVar(value="読み込み中...")
        status_bar = tk.Label(self.root, textvariable=self.status_var,
                              font=("", 9), fg="gray", anchor=tk.W, padx=10, pady=4)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def refresh(self):
        """ユーザー一覧をバックグラウンドで再取得して表示"""
        self.status_var.set("読み込み中...（サーバー起動に最大60秒かかる場合があります）")
        self.root.update_idletasks()

        # Clear existing rows
        for item in self.tree.get_children():
            self.tree.delete(item)

        def _fetch_in_bg():
            try:
                users = fetch_users(self.server_url)
                # Schedule UI update on main thread
                self.root.after(0, lambda: self._update_table(users))
            except Exception as e:
                self.root.after(0, lambda: self._show_error(str(e)))

        threading.Thread(target=_fetch_in_bg, daemon=True).start()

    def _update_table(self, users):
        """UIスレッドでテーブルを更新"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        for u in users:
            self.tree.insert("", tk.END, values=(
                u["id"],
                u["name"],
                u["nickname"],
                u.get("skill_level", ""),
                u.get("rating", 1500),
                u.get("created_at", ""),
            ))
        self.count_label.config(text=f"登録ユーザー数: {len(users)}")
        self.status_var.set(f"取得完了 ({len(users)}件)")

    def _show_error(self, error_msg):
        """UIスレッドでエラーを表示"""
        self.count_label.config(text="")
        self.status_var.set(f"エラー: {error_msg}")
        messagebox.showerror("エラー", error_msg)

    def run(self):
        self.root.mainloop()


def main():
    server = DEFAULT_SERVER
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg in ("--server", "-s") and i < len(sys.argv) - 1:
            server = sys.argv[i + 1]
            break
        elif arg.startswith("http"):
            server = arg
            break

    app = AdminApp(server)
    app.run()


if __name__ == "__main__":
    main()
