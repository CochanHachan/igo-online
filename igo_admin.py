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

# Grid table colors (Excel-like blue theme)
HEADER_BG = "#4472C4"
HEADER_FG = "#FFFFFF"
ROW_BG_ODD = "#FFFFFF"
ROW_BG_EVEN = "#D9E2F3"
GRID_COLOR = "#8EA9DB"
CELL_FG = "#000000"


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


class GridTable(tk.Frame):
    """Excel風グリッドライン付きテーブルウィジェット"""

    def __init__(self, parent, columns, col_widths, col_anchors=None):
        super().__init__(parent)
        self.columns = columns
        self.col_widths = col_widths
        self.col_anchors = col_anchors or ["w"] * len(columns)

        # Canvas + scrollbars
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.v_scroll = ttk.Scrollbar(self, orient=tk.VERTICAL,
                                      command=self.canvas.yview)
        self.h_scroll = ttk.Scrollbar(self, orient=tk.HORIZONTAL,
                                      command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set,
                              xscrollcommand=self.h_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Inner frame
        self.inner = tk.Frame(self.canvas, bg=GRID_COLOR)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner,
                                                        anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

        self._draw_header()

    def _on_inner_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        total_w = sum(self.col_widths) + len(self.col_widths) + 1
        width = max(total_w, event.width)
        self.canvas.itemconfig(self.canvas_window, width=width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")

    def _draw_header(self):
        """Draw header row with grid lines."""
        row_frame = tk.Frame(self.inner, bg=GRID_COLOR)
        row_frame.pack(fill=tk.X, padx=1, pady=(1, 0))

        for i, (name, width) in enumerate(zip(self.columns, self.col_widths)):
            px = (0, 1) if i < len(self.columns) - 1 else (0, 0)
            cell = tk.Label(row_frame, text=name, bg=HEADER_BG, fg=HEADER_FG,
                            font=("", 10, "bold"), anchor="center", padx=6, pady=5)
            cell.grid(row=0, column=i, sticky="nsew", padx=px)
            row_frame.grid_columnconfigure(i, minsize=width, weight=0)

    def clear(self):
        """Clear all data rows (keep header)."""
        children = self.inner.winfo_children()
        for child in children[1:]:
            child.destroy()

    def add_row(self, values, row_index=0):
        """Add a data row with grid lines."""
        bg = ROW_BG_ODD if row_index % 2 == 0 else ROW_BG_EVEN

        row_frame = tk.Frame(self.inner, bg=GRID_COLOR)
        row_frame.pack(fill=tk.X, padx=1, pady=(1, 0))

        for i, (val, width) in enumerate(zip(values, self.col_widths)):
            anchor = self.col_anchors[i]
            px = (0, 1) if i < len(values) - 1 else (0, 0)
            cell = tk.Label(row_frame, text=str(val), bg=bg, fg=CELL_FG,
                            font=("", 10), anchor=anchor, padx=6, pady=3)
            cell.grid(row=0, column=i, sticky="nsew", padx=px)
            row_frame.grid_columnconfigure(i, minsize=width, weight=0)

    def add_bottom_border(self):
        """Add bottom border line after last row."""
        border = tk.Frame(self.inner, bg=GRID_COLOR, height=1)
        border.pack(fill=tk.X, padx=1)


class AdminApp:
    def __init__(self, server_url):
        self.server_url = server_url
        self.root = tk.Tk()
        self.root.title("囲碁オンライン 管理者パネル")
        self.root.geometry("850x500")
        self.root.minsize(650, 350)

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

        # Grid table
        table_frame = tk.Frame(self.root, padx=10, pady=5)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("ID", "氏名", "ニックネーム", "棋力", "レーティング", "登録日時")
        col_widths = (50, 140, 140, 90, 100, 180)
        col_anchors = ("center", "w", "w", "center", "center", "w")

        self.grid_table = GridTable(table_frame, columns, col_widths, col_anchors)
        self.grid_table.pack(fill=tk.BOTH, expand=True)

        # Status bar
        self.status_var = tk.StringVar(value="読み込み中...")
        status_bar = tk.Label(self.root, textvariable=self.status_var,
                              font=("", 9), fg="gray", anchor=tk.W, padx=10, pady=4)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def refresh(self):
        """ユーザー一覧をバックグラウンドで再取得して表示"""
        self.status_var.set("読み込み中...（サーバー起動に最大60秒かかる場合があります）")
        self.root.update_idletasks()
        self.grid_table.clear()

        def _fetch_in_bg():
            try:
                users = fetch_users(self.server_url)
                self.root.after(0, lambda: self._update_table(users))
            except Exception as e:
                self.root.after(0, lambda: self._show_error(str(e)))

        threading.Thread(target=_fetch_in_bg, daemon=True).start()

    def _update_table(self, users):
        """UIスレッドでテーブルを更新"""
        self.grid_table.clear()
        for i, u in enumerate(users):
            self.grid_table.add_row((
                u["id"],
                u["name"],
                u["nickname"],
                u.get("skill_level", ""),
                u.get("rating", 1500),
                u.get("created_at", ""),
            ), row_index=i)
        self.grid_table.add_bottom_border()
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
