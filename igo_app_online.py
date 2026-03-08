#!/usr/bin/env python3
"""Go online client - WebSocket connection to server for network play"""
import pygame
import pygame.gfxdraw
import sys
import math
import json
import threading
import asyncio
import websockets
import queue
import urllib.request
import urllib.error
import time as time_module

pygame.init()

BOARD_SIZE = 19
MENU_BAR_HEIGHT = 26
INFO_BAR_HEIGHT = 40
BUTTON_BAR_HEIGHT = 46
CLOCK_PANEL_WIDTH = 110
STAR_POINTS = [
    (3, 3), (3, 9), (3, 15),
    (9, 3), (9, 9), (9, 15),
    (15, 3), (15, 9), (15, 15),
]
INIT_BOARD_PX = 620
INIT_W = INIT_BOARD_PX + CLOCK_PANEL_WIDTH * 2
INIT_H = INIT_BOARD_PX + MENU_BAR_HEIGHT + INFO_BAR_HEIGHT + BUTTON_BAR_HEIGHT
BG_DARK = (44, 44, 44)
WHITE = (255, 255, 255)
LINE_COLOR = (26, 26, 26)
BUTTON_COLOR = (68, 68, 68)
BUTTON_HOVER = (100, 100, 100)
INPUT_BG = (60, 60, 60)
INPUT_ACTIVE = (80, 80, 120)
GREEN = (80, 200, 80)
RED = (200, 80, 80)
YELLOW = (220, 200, 60)
MENU_BG = (245, 245, 245)
MENU_HOVER_BG = (200, 216, 240)
MENU_BORDER = (200, 200, 200)
MENU_TEXT = (0, 0, 0)
MENU_TEXT_DISABLED = (160, 160, 160)
CLOCK_BG = (30, 45, 65)
CLOCK_ACTIVE = (25, 60, 50)
CLOCK_DANGER = (90, 30, 30)
CLOCK_BORDER = (60, 80, 110)
CLOCK_ICON = (180, 200, 220)

# Time control presets: (label, main_time_seconds, byoyomi_seconds)
TIME_PRESETS = [
    ("1\u5206+30\u79d2", 60, 30),
    ("10\u5206+30\u79d2", 600, 30),
]

def _clamp(v):
    return max(0, min(255, int(v)))

# --------------- Go rules engine (client-side for display) ---------------

def _neighbors(r, c):
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE:
            yield nr, nc

def _get_group(board, r, c):
    color = board[r][c]
    if color == 0:
        return set(), 0
    visited = set()
    stack = [(r, c)]
    liberties = set()
    while stack:
        cr, cc = stack.pop()
        if (cr, cc) in visited:
            continue
        visited.add((cr, cc))
        for nr, nc in _neighbors(cr, cc):
            if board[nr][nc] == color and (nr, nc) not in visited:
                stack.append((nr, nc))
            elif board[nr][nc] == 0:
                liberties.add((nr, nc))
    return visited, len(liberties)

# --------------- Stone rendering ---------------

_SS = 3

def create_stone_surface(color, diameter):
    if diameter < 4:
        diameter = 4
    big_diam = diameter * _SS
    big_size = big_diam + 2 * _SS
    big_r = big_diam // 2
    bcx, bcy = big_size // 2, big_size // 2
    big = pygame.Surface((big_size, big_size), pygame.SRCALPHA)
    base_col = (20, 20, 20, 255) if color == "black" else (210, 210, 210, 255)
    pygame.gfxdraw.filled_circle(big, bcx, bcy, big_r, base_col)
    light_ox = -0.35
    light_oy = -0.35
    steps = max(big_r, 36)
    for i in range(steps, 0, -1):
        t = i / steps
        cr = max(1, int(big_r * t))
        if color == "black":
            base = 18 + 30 * (1.0 - t)
            ldist = math.sqrt((t - light_ox * t) ** 2 + (t - light_oy * t) ** 2)
            hl = max(0, 1.0 - ldist / 0.8) ** 2.0
            val = base + hl * 75
            edge_dark = max(0, t - 0.7) / 0.3
            val = val * (1.0 - edge_dark * 0.45)
            c = _clamp(val)
            draw_color = (c, c, c, 255)
        else:
            base = 245 - 60 * (t ** 1.2)
            ldist = math.sqrt((t - light_ox * t) ** 2 + (t - light_oy * t) ** 2)
            spec = max(0, 1.0 - ldist / 0.7) ** 2.5
            val = base + spec * 35
            edge_dark = max(0, t - 0.6) / 0.4
            val = val - edge_dark * 30
            c = _clamp(val)
            draw_color = (c, c, c, 255)
        off_x = int(-light_ox * (1.0 - t) * big_r * 0.15)
        off_y = int(-light_oy * (1.0 - t) * big_r * 0.15)
        pygame.gfxdraw.filled_circle(big, bcx + off_x, bcy + off_y, cr, draw_color)
    hl_x = bcx + int(-light_ox * big_r * 0.4)
    hl_y = bcy + int(-light_oy * big_r * 0.4)
    hl_r = max(1, int(big_r * 0.25))
    for i in range(hl_r, 0, -1):
        t2 = 1.0 - (i / hl_r)
        if color == "black":
            val = _clamp(50 + t2 * 60)
            pygame.gfxdraw.filled_circle(big, hl_x, hl_y, i, (val, val, val, 255))
        else:
            val = _clamp(230 + t2 * 25)
            pygame.gfxdraw.filled_circle(big, hl_x, hl_y, i, (val, val, val, 255))
    final_size = diameter + 2
    small = pygame.transform.smoothscale(big, (final_size, final_size))
    return small

# --------------- Layout ---------------

class Layout:
    def __init__(self, win_w, win_h):
        usable_w = win_w - CLOCK_PANEL_WIDTH * 2
        board_area = min(usable_w, win_h - MENU_BAR_HEIGHT - INFO_BAR_HEIGHT - BUTTON_BAR_HEIGHT)
        board_area = max(board_area, 100)
        self.margin = max(6, int(board_area * 0.03))
        self.cell_size = (board_area - self.margin * 2) / (BOARD_SIZE - 1)
        self.stone_diam = max(4, round(self.cell_size) + 1)
        self.board_px = int(self.margin * 2 + self.cell_size * (BOARD_SIZE - 1))
        self.star_radius = max(2, int(self.cell_size * 0.1))
        self.win_w = win_w
        self.win_h = win_h
        self.offset_x = (win_w - self.board_px) // 2
        self.offset_y = MENU_BAR_HEIGHT + INFO_BAR_HEIGHT
        # Clock panel positions
        self.clock_left_x = self.offset_x - CLOCK_PANEL_WIDTH
        self.clock_right_x = self.offset_x + self.board_px
        self.clock_y = self.offset_y
        self.clock_h = self.board_px

    def grid_to_screen(self, row, col):
        x = self.offset_x + self.margin + round(col * self.cell_size)
        y = self.offset_y + self.margin + round(row * self.cell_size)
        return x, y

    def screen_to_grid(self, mx, my):
        bx = mx - self.offset_x - self.margin
        by = my - self.offset_y - self.margin
        col = round(bx / self.cell_size)
        row = round(by / self.cell_size)
        return int(row), int(col)

# --------------- Drawing functions ---------------

def draw_wood_background(screen, layout):
    ox = layout.offset_x
    oy = layout.offset_y
    bpx = layout.board_px
    for y in range(bpx):
        variation = math.sin(y * 0.018) * 9 + math.sin(y * 0.047) * 5
        r_val = max(0, min(255, int(220 + variation)))
        g_val = max(0, min(255, int(179 + variation * 0.7)))
        b_val = max(0, min(255, int(92 + variation * 0.3)))
        pygame.draw.line(screen, (r_val, g_val, b_val), (ox, oy + y), (ox + bpx, oy + y))

def draw_board(screen, board, black_stone, white_stone, layout):
    m = layout.margin
    cs = layout.cell_size
    n = BOARD_SIZE
    ox = layout.offset_x
    oy = layout.offset_y
    for i in range(n):
        y_pos = oy + m + round(i * cs)
        pygame.draw.line(screen, LINE_COLOR, (ox + m, y_pos), (ox + m + round((n-1)*cs), y_pos), 1)
        x_pos = ox + m + round(i * cs)
        pygame.draw.line(screen, LINE_COLOR, (x_pos, oy + m), (x_pos, oy + m + round((n-1)*cs)), 1)
    pygame.draw.rect(screen, LINE_COLOR, (ox + m, oy + m, int((n-1)*cs), int((n-1)*cs)), 2)
    for (r, c) in STAR_POINTS:
        x, y = layout.grid_to_screen(r, c)
        pygame.draw.circle(screen, LINE_COLOR, (x, y), layout.star_radius)
    for r in range(n):
        for c in range(n):
            if board[r][c] != 0:
                x, y = layout.grid_to_screen(r, c)
                stone = black_stone if board[r][c] == 1 else white_stone
                screen.blit(stone, (x - stone.get_width()//2, y - stone.get_height()//2))

class Button:
    def __init__(self, rect, text, font):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.hovered = False
    def draw(self, screen):
        color = BUTTON_HOVER if self.hovered else BUTTON_COLOR
        pygame.draw.rect(screen, color, self.rect, border_radius=6)
        ts = self.font.render(self.text, True, WHITE)
        tr = ts.get_rect(center=self.rect.center)
        screen.blit(ts, tr)
    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)
    def update_hover(self, pos):
        self.hovered = self.rect.collidepoint(pos)


# --------------- Menu Bar ---------------

class MenuBar:
    def __init__(self, font, win_w):
        self.font = font
        self.win_w = win_w
        self.items = [
            ("\u30b2\u30fc\u30e0", ["\u30d1\u30b9", "\u6295\u4e86", "\u7d42\u4e86"]),
            ("\u8a2d\u5b9a", ["\u6301\u3061\u6642\u9593: 1\u5206+30\u79d2", "\u6301\u3061\u6642\u9593: 10\u5206+30\u79d2"]),
            ("\u30d8\u30eb\u30d7", ["\u30d0\u30fc\u30b8\u30e7\u30f3\u60c5\u5831"]),
        ]
        self.open_menu = -1  # which top-level menu is open (-1 = none)
        self.hover_item = -1  # which dropdown item is hovered
        self._build_rects()

    def _build_rects(self):
        self.top_rects = []
        x = 0
        for label, _ in self.items:
            w = self.font.size(label)[0] + 24
            self.top_rects.append(pygame.Rect(x, 0, w, MENU_BAR_HEIGHT))
            x += w
        self.dropdown_rects = []
        for i, (_, sub_items) in enumerate(self.items):
            rects = []
            max_w = max(self.font.size(s)[0] for s in sub_items) + 30
            max_w = max(max_w, self.top_rects[i].w)
            dy = MENU_BAR_HEIGHT
            for j, sub in enumerate(sub_items):
                rects.append(pygame.Rect(self.top_rects[i].x, dy + j * 28, max_w, 28))
            self.dropdown_rects.append(rects)

    def update_width(self, win_w):
        self.win_w = win_w

    def handle_click(self, pos):
        """Returns (menu_idx, item_idx) or None."""
        mx, my = pos
        # Check dropdown items first if menu is open
        if self.open_menu >= 0:
            for j, rect in enumerate(self.dropdown_rects[self.open_menu]):
                if rect.collidepoint(mx, my):
                    result = (self.open_menu, j)
                    self.open_menu = -1
                    return result
        # Check top-level items
        for i, rect in enumerate(self.top_rects):
            if rect.collidepoint(mx, my):
                if self.open_menu == i:
                    self.open_menu = -1
                else:
                    self.open_menu = i
                return None
        # Click outside closes menu
        if self.open_menu >= 0:
            self.open_menu = -1
        return None

    def handle_motion(self, pos):
        mx, my = pos
        self.hover_item = -1
        if self.open_menu >= 0:
            for i, rect in enumerate(self.top_rects):
                if rect.collidepoint(mx, my) and i != self.open_menu:
                    self.open_menu = i
                    break
            for j, rect in enumerate(self.dropdown_rects[self.open_menu]):
                if rect.collidepoint(mx, my):
                    self.hover_item = j
                    break

    def draw_bar(self, screen, time_preset_idx):
        """Draw only the menu bar (top-level items). Call draw_dropdown separately last."""
        pygame.draw.rect(screen, MENU_BG, (0, 0, self.win_w, MENU_BAR_HEIGHT))
        pygame.draw.line(screen, MENU_BORDER, (0, MENU_BAR_HEIGHT - 1), (self.win_w, MENU_BAR_HEIGHT - 1))
        for i, (label, _) in enumerate(self.items):
            rect = self.top_rects[i]
            if self.open_menu == i:
                pygame.draw.rect(screen, MENU_HOVER_BG, rect)
            ts = self.font.render(label, True, MENU_TEXT)
            screen.blit(ts, ts.get_rect(center=rect.center))
        self._time_preset_idx = time_preset_idx

    def draw_dropdown(self, screen):
        """Draw the dropdown menu. Must be called LAST so it appears on top."""
        if self.open_menu < 0:
            return
        mi = self.open_menu
        time_preset_idx = self._time_preset_idx
        _, sub_items = self.items[mi]
        rects = self.dropdown_rects[mi]
        if rects:
            union = rects[0].unionall(rects[1:]) if len(rects) > 1 else rects[0]
            shadow = union.inflate(4, 4).move(2, 2)
            shadow_surf = pygame.Surface((shadow.w, shadow.h), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, 60))
            screen.blit(shadow_surf, shadow.topleft)
            pygame.draw.rect(screen, MENU_BG, union)
            pygame.draw.rect(screen, MENU_BORDER, union, 1)
        for j, (sub, rect) in enumerate(zip(sub_items, rects)):
            if self.hover_item == j:
                pygame.draw.rect(screen, MENU_HOVER_BG, rect)
            display = sub
            if mi == 1 and j < len(TIME_PRESETS):
                if j == time_preset_idx:
                    display = "\u2714 " + sub
            ts = self.font.render(display, True, MENU_TEXT)
            screen.blit(ts, (rect.x + 8, rect.y + 4))

    def draw(self, screen, time_preset_idx):
        """Legacy: draw bar + dropdown together."""
        self.draw_bar(screen, time_preset_idx)
        self.draw_dropdown(screen)

    def is_in_menu_area(self, pos):
        mx, my = pos
        if my < MENU_BAR_HEIGHT:
            return True
        if self.open_menu >= 0:
            for rect in self.dropdown_rects[self.open_menu]:
                if rect.collidepoint(mx, my):
                    return True
        return False


# --------------- Clock Display (AI Shogi style) ---------------

def format_time_hms(seconds):
    """Format seconds as H:MM:SS (AI Shogi style)."""
    s = max(0, int(seconds))
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h}:{m:02d}:{sec:02d}"

def draw_clock_icon(screen, cx, cy, radius, color):
    """Draw a small clock/stopwatch icon."""
    pygame.draw.circle(screen, color, (cx, cy), radius, 2)
    # Hour hand
    pygame.draw.line(screen, color, (cx, cy), (cx, cy - radius + 3), 2)
    # Minute hand
    pygame.draw.line(screen, color, (cx, cy), (cx + radius - 4, cy), 2)
    # Center dot
    pygame.draw.circle(screen, color, (cx, cy), 2)

def draw_clock_panel(screen, font, small_font, layout, side, player_name,
                     main_time, in_byoyomi, byoyomi_remaining,
                     is_active, my_color_is_this):
    """Draw a clock panel in AI Shogi style on the left or right side."""
    if side == "left":
        px = max(0, layout.clock_left_x)
        pw = layout.offset_x - px
    else:
        px = layout.clock_right_x
        pw = min(layout.win_w, px + CLOCK_PANEL_WIDTH) - px

    py = layout.clock_y + 20
    ph = min(200, layout.clock_h - 40)

    if pw < 30:
        return

    # Background color based on state
    if is_active:
        if in_byoyomi and byoyomi_remaining < 10:
            bg = CLOCK_DANGER
        else:
            bg = CLOCK_ACTIVE
    else:
        bg = CLOCK_BG

    panel_rect = pygame.Rect(px + 2, py, pw - 4, ph)

    # Draw panel with gradient effect (top lighter, bottom darker)
    for i in range(ph):
        t = i / max(1, ph - 1)
        r_val = max(0, min(255, int(bg[0] + 15 * (1 - t))))
        g_val = max(0, min(255, int(bg[1] + 15 * (1 - t))))
        b_val = max(0, min(255, int(bg[2] + 15 * (1 - t))))
        pygame.draw.line(screen, (r_val, g_val, b_val),
                         (panel_rect.x, panel_rect.y + i),
                         (panel_rect.x + panel_rect.w, panel_rect.y + i))
    # Rounded border
    pygame.draw.rect(screen, CLOCK_BORDER, panel_rect, 2, border_radius=6)

    cx = panel_rect.centerx
    cy = py + 16

    # Stone indicator (small label box like AI Shogi "先"/"後")
    label_w = 24
    label_h = 20
    label_rect = pygame.Rect(cx - label_w // 2, cy - label_h // 2, label_w, label_h)
    if side == "left":
        stone_bg = (20, 20, 20)
        stone_border = (80, 80, 80)
        stone_text_color = (240, 240, 240)
    else:
        stone_bg = (220, 220, 220)
        stone_border = (160, 160, 160)
        stone_text_color = (20, 20, 20)
    pygame.draw.rect(screen, stone_bg, label_rect, border_radius=3)
    pygame.draw.rect(screen, stone_border, label_rect, 1, border_radius=3)
    # "先"/"後" style label
    label_char = "\u25cf" if side == "left" else "\u25cb"
    lbl_surf = small_font.render(label_char, True, stone_text_color)
    screen.blit(lbl_surf, lbl_surf.get_rect(center=label_rect.center))

    cy += 18

    # Player name
    name_text = small_font.render(player_name[:10], True, (220, 230, 240))
    screen.blit(name_text, name_text.get_rect(center=(cx, cy)))
    cy += 20

    # Clock icon + main time (AI Shogi style)
    icon_r = 8
    icon_cx = panel_rect.x + 14
    icon_cy = cy
    draw_clock_icon(screen, icon_cx, icon_cy, icon_r, CLOCK_ICON)

    # Main time display in H:MM:SS
    if not in_byoyomi:
        time_str = format_time_hms(main_time)
        if main_time <= 10:
            time_color = (255, 80, 80)
        elif main_time <= 30:
            time_color = (255, 200, 80)
        else:
            time_color = WHITE
    else:
        time_str = "0:00:00"
        time_color = (120, 120, 120)
    time_surf = font.render(time_str, True, time_color)
    time_x = icon_cx + icon_r + 6
    screen.blit(time_surf, (time_x, cy - time_surf.get_height() // 2))
    cy += 28

    # Byoyomi section
    if in_byoyomi:
        byo_label = small_font.render("\u79d2\u8aad\u307f", True, YELLOW)
        screen.blit(byo_label, byo_label.get_rect(center=(cx, cy)))
        cy += 18
        byo_str = format_time_hms(byoyomi_remaining)
        if byoyomi_remaining < 10:
            byo_color = (255, 80, 80)
        else:
            byo_color = YELLOW
        # Clock icon for byoyomi
        draw_clock_icon(screen, icon_cx, cy, icon_r, byo_color)
        byo_surf = font.render(byo_str, True, byo_color)
        screen.blit(byo_surf, (time_x, cy - byo_surf.get_height() // 2))
    else:
        byo_label = small_font.render("\u79d2\u8aad\u307f", True, (90, 100, 110))
        screen.blit(byo_label, byo_label.get_rect(center=(cx, cy)))
        cy += 18
        byo_surf = small_font.render("--:--", True, (90, 100, 110))
        screen.blit(byo_surf, byo_surf.get_rect(center=(cx, cy)))


# --------------- WebSocket client (runs in background thread) ---------------

class NetworkClient:
    def __init__(self):
        self.recv_queue = queue.Queue()
        self.send_queue = queue.Queue()
        self.connected = False
        self.running = False
        self.thread = None
        self.loop = None
        self.my_color = None
        self.room_id = None
        self.opponent_name = ""
        self.error_msg = ""
        self.time_control = (60, 30)  # (main_time, byoyomi)

    def connect(self, server_url, player_name):
        self.running = True
        self.error_msg = ""
        self.thread = threading.Thread(
            target=self._run_loop, args=(server_url, player_name), daemon=True
        )
        self.thread.start()

    def _find_match(self, server_url, player_name):
        """Call /find_match HTTP endpoint to get room_code and instance_id."""
        http_url = server_url.replace("wss://", "https://").replace("ws://", "http://")
        mt, byo = self.time_control
        url = f"{http_url}/find_match?name={player_name}&main_time={mt}&byoyomi={byo}"
        req = urllib.request.Request(url, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                return data.get("room_code"), data.get("instance_id")
        except Exception as e:
            self.error_msg = f"Matchmaking failed: {e}"
            return None, None

    def disconnect(self):
        self.running = False
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)

    def send(self, msg):
        self.send_queue.put(msg)

    def _run_loop(self, server_url, player_name):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._ws_handler(server_url, player_name))
        except Exception as e:
            self.error_msg = str(e)
            self.connected = False
        finally:
            self.running = False

    async def _ws_handler(self, server_url, player_name):
        room_code, instance_id = self._find_match(server_url, player_name)
        if not room_code:
            self.connected = False
            return

        url = f"{server_url}/ws/{room_code}/{player_name}"
        extra_headers = {}
        if instance_id and instance_id != "local":
            extra_headers["fly-force-instance-id"] = instance_id

        try:
            async with websockets.connect(url, additional_headers=extra_headers) as ws:
                self.connected = True
                recv_task = asyncio.create_task(self._recv_loop(ws))
                send_task = asyncio.create_task(self._send_loop(ws))
                done, pending = await asyncio.wait(
                    [recv_task, send_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
                self.connected = False
        except Exception as e:
            self.error_msg = f"Connection failed: {e}"
            self.connected = False

    async def _recv_loop(self, ws):
        try:
            async for message in ws:
                data = json.loads(message)
                self.recv_queue.put(data)
                if not self.running:
                    break
        except websockets.exceptions.ConnectionClosed:
            self.recv_queue.put({"type": "connection_closed"})

    async def _send_loop(self, ws):
        while self.running:
            try:
                msg = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.send_queue.get(timeout=0.1)
                )
                await ws.send(json.dumps(msg))
            except queue.Empty:
                continue
            except Exception:
                break

# --------------- Connection Screen ---------------

def connection_screen(screen, font, btn_font):
    clock = pygame.time.Clock()
    server_url = "wss://app-aiszfyoe.fly.dev"
    player_name = "Player"
    active_field = 0
    cursor_blink = 0
    time_preset_idx = 0  # default: 1min + 30sec

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            elif event.type == pygame.VIDEORESIZE:
                nw = max(500, event.w)
                nh = max(400, event.h)
                screen = pygame.display.set_mode((nw, nh), pygame.RESIZABLE)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                w, h = screen.get_size()
                cx = w // 2
                field_x = cx - 180
                if field_x <= mx <= field_x + 360:
                    if h // 2 - 60 <= my <= h // 2 - 25:
                        active_field = 0
                    elif h // 2 + 10 <= my <= h // 2 + 45:
                        active_field = 1
                # Time preset buttons
                for ti, (label, mt, byo) in enumerate(TIME_PRESETS):
                    bx = cx - 100 + ti * 120
                    btn_r = pygame.Rect(bx, h // 2 + 60, 110, 32)
                    if btn_r.collidepoint(mx, my):
                        time_preset_idx = ti
                # Connect button
                connect_rect = pygame.Rect(cx - 80, h // 2 + 110, 160, 40)
                if connect_rect.collidepoint(mx, my):
                    return (server_url, player_name, time_preset_idx)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    active_field = 1 - active_field
                elif event.key == pygame.K_RETURN:
                    return (server_url, player_name, time_preset_idx)
                elif event.key == pygame.K_BACKSPACE:
                    if active_field == 0:
                        server_url = server_url[:-1]
                    else:
                        player_name = player_name[:-1]
                else:
                    ch = event.unicode
                    if ch and ch.isprintable():
                        if active_field == 0:
                            server_url += ch
                        else:
                            player_name += ch

        w, h = screen.get_size()
        cx = w // 2
        screen.fill(BG_DARK)

        title = font.render("Go Online", True, WHITE)
        screen.blit(title, title.get_rect(center=(cx, h // 2 - 150)))

        subtitle = btn_font.render("Connect to server for online play", True, (180, 180, 180))
        screen.blit(subtitle, subtitle.get_rect(center=(cx, h // 2 - 120)))

        lbl1 = btn_font.render("Server URL:", True, WHITE)
        screen.blit(lbl1, (cx - 180, h // 2 - 100))
        field_rect1 = pygame.Rect(cx - 180, h // 2 - 80, 360, 35)
        color1 = INPUT_ACTIVE if active_field == 0 else INPUT_BG
        pygame.draw.rect(screen, color1, field_rect1, border_radius=4)
        pygame.draw.rect(screen, WHITE, field_rect1, 1, border_radius=4)
        cursor_blink = (cursor_blink + 1) % 60
        url_text = server_url + ("|" if active_field == 0 and cursor_blink < 30 else "")
        ts1 = btn_font.render(url_text, True, WHITE)
        screen.blit(ts1, (field_rect1.x + 8, field_rect1.y + 8))

        lbl2 = btn_font.render("Player Name:", True, WHITE)
        screen.blit(lbl2, (cx - 180, h // 2 - 30))
        field_rect2 = pygame.Rect(cx - 180, h // 2 - 10, 360, 35)
        color2 = INPUT_ACTIVE if active_field == 1 else INPUT_BG
        pygame.draw.rect(screen, color2, field_rect2, border_radius=4)
        pygame.draw.rect(screen, WHITE, field_rect2, 1, border_radius=4)
        name_text = player_name + ("|" if active_field == 1 and cursor_blink < 30 else "")
        ts2 = btn_font.render(name_text, True, WHITE)
        screen.blit(ts2, (field_rect2.x + 8, field_rect2.y + 8))

        # Time control selection
        tc_label = btn_font.render("\u6301\u3061\u6642\u9593:", True, WHITE)
        screen.blit(tc_label, (cx - 180, h // 2 + 40))
        for ti, (label, mt, byo) in enumerate(TIME_PRESETS):
            bx = cx - 100 + ti * 120
            btn_r = pygame.Rect(bx, h // 2 + 60, 110, 32)
            if ti == time_preset_idx:
                pygame.draw.rect(screen, MENU_HOVER_BG, btn_r, border_radius=5)
                pygame.draw.rect(screen, GREEN, btn_r, 2, border_radius=5)
            else:
                pygame.draw.rect(screen, BUTTON_COLOR, btn_r, border_radius=5)
                pygame.draw.rect(screen, MENU_BORDER, btn_r, 1, border_radius=5)
            tl = btn_font.render(label, True, WHITE)
            screen.blit(tl, tl.get_rect(center=btn_r.center))

        # Connect button
        connect_rect = pygame.Rect(cx - 80, h // 2 + 110, 160, 40)
        mx_h, my_h = pygame.mouse.get_pos()
        btn_color = GREEN if connect_rect.collidepoint(mx_h, my_h) else (60, 160, 60)
        pygame.draw.rect(screen, btn_color, connect_rect, border_radius=6)
        btn_text = font.render("Connect", True, WHITE)
        screen.blit(btn_text, btn_text.get_rect(center=connect_rect.center))

        pygame.display.flip()
        clock.tick(30)



# --------------- Main Game ---------------

def main():
    screen = pygame.display.set_mode((INIT_W, INIT_H), pygame.RESIZABLE)
    pygame.display.set_caption("Go Online")
    font = None
    btn_font = None
    small_font = None
    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/usr/share/fonts/truetype/takao-gothic/TakaoPGothic.ttf",
    ]
    for fp in font_paths:
        try:
            font = pygame.font.Font(fp, 18)
            btn_font = pygame.font.Font(fp, 14)
            small_font = pygame.font.Font(fp, 12)
            break
        except Exception:
            continue
    if font is None:
        font = pygame.font.SysFont("notosanscjk,notosansjp,notosans,sans", 18)
        btn_font = pygame.font.SysFont("notosanscjk,notosansjp,notosans,sans", 14)
        small_font = pygame.font.SysFont("notosanscjk,notosansjp,notosans,sans", 12)

    result = connection_screen(screen, font, btn_font)
    if result is None:
        pygame.quit()
        sys.exit()
    server_url, player_name, time_preset_idx = result

    net = NetworkClient()
    _, main_time_cfg, byoyomi_cfg = TIME_PRESETS[time_preset_idx]
    net.time_control = (main_time_cfg, byoyomi_cfg)
    net.connect(server_url, player_name)

    layout = Layout(INIT_W, INIT_H)
    print("Generating stones...")
    black_stone = create_stone_surface("black", layout.stone_diam)
    white_stone = create_stone_surface("white", layout.stone_diam)
    cached_diam = layout.stone_diam
    print("Done")

    board = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
    current_player = 1
    my_color = None
    opponent_name = ""
    game_started = False
    status_msg = "Connecting..."
    status_color = YELLOW
    game_over = False

    # Time state
    black_main_time = float(main_time_cfg)
    white_main_time = float(main_time_cfg)
    black_in_byoyomi = False
    white_in_byoyomi = False
    black_byoyomi_remaining = float(byoyomi_cfg)
    white_byoyomi_remaining = float(byoyomi_cfg)
    last_time_sync = time_module.time()
    game_main_time = main_time_cfg
    game_byoyomi = byoyomi_cfg

    menu_bar = MenuBar(btn_font, INIT_W)

    def make_online_buttons(lay, bf):
        btn_y = lay.win_h - BUTTON_BAR_HEIGHT + 6
        w = lay.win_w
        return [
            Button((15, btn_y, 90, 34), "Pass", bf),
            Button((w - 105, btn_y, 90, 34), "Resign", bf),
        ]

    buttons = make_online_buttons(layout, btn_font)
    clock = pygame.time.Clock()
    running = True
    version_popup = False

    while running:
        now = time_module.time()

        # Process network messages
        while not net.recv_queue.empty():
            msg = net.recv_queue.get_nowait()
            msg_type = msg.get("type")

            if msg_type == "assigned":
                my_color = msg["color"]
                net.my_color = my_color
                net.room_id = msg["room_id"]
                color_name = "Black" if my_color == 1 else "White"
                status_msg = f"You are {color_name}. Room: {msg['room_id']}"
                status_color = WHITE

            elif msg_type == "waiting":
                status_msg = "Waiting for opponent..."
                status_color = YELLOW

            elif msg_type == "game_start":
                game_started = True
                opponent_name = msg.get("opponent_name", "")
                current_player = msg["current_player"]
                my_color = msg["your_color"]
                game_main_time = msg.get("main_time", main_time_cfg)
                game_byoyomi = msg.get("byoyomi", byoyomi_cfg)
                color_name = "Black" if my_color == 1 else "White"
                status_msg = f"Game started! You ({color_name}) vs {opponent_name}"
                status_color = GREEN
                black_main_time = msg.get("black_main_time", float(game_main_time))
                white_main_time = msg.get("white_main_time", float(game_main_time))
                black_in_byoyomi = msg.get("black_in_byoyomi", False)
                white_in_byoyomi = msg.get("white_in_byoyomi", False)
                black_byoyomi_remaining = msg.get("black_byoyomi_remaining", float(game_byoyomi))
                white_byoyomi_remaining = msg.get("white_byoyomi_remaining", float(game_byoyomi))
                last_time_sync = now

            elif msg_type == "time_sync":
                black_main_time = msg.get("black_main_time", black_main_time)
                white_main_time = msg.get("white_main_time", white_main_time)
                black_in_byoyomi = msg.get("black_in_byoyomi", black_in_byoyomi)
                white_in_byoyomi = msg.get("white_in_byoyomi", white_in_byoyomi)
                black_byoyomi_remaining = msg.get("black_byoyomi_remaining", black_byoyomi_remaining)
                white_byoyomi_remaining = msg.get("white_byoyomi_remaining", white_byoyomi_remaining)
                last_time_sync = now

            elif msg_type == "move":
                row, col = msg["row"], msg["col"]
                color = msg["color"]
                board[row][col] = color
                for cap in msg.get("captured", []):
                    cr, cc, _ = cap
                    board[cr][cc] = 0
                current_player = msg["current_player"]
                black_main_time = msg.get("black_main_time", black_main_time)
                white_main_time = msg.get("white_main_time", white_main_time)
                black_in_byoyomi = msg.get("black_in_byoyomi", black_in_byoyomi)
                white_in_byoyomi = msg.get("white_in_byoyomi", white_in_byoyomi)
                black_byoyomi_remaining = msg.get("black_byoyomi_remaining", black_byoyomi_remaining)
                white_byoyomi_remaining = msg.get("white_byoyomi_remaining", white_byoyomi_remaining)
                last_time_sync = now
                if current_player == my_color:
                    status_msg = "Your turn"
                    status_color = GREEN
                else:
                    status_msg = "Opponent's turn..."
                    status_color = YELLOW

            elif msg_type == "pass":
                current_player = msg["current_player"]
                black_main_time = msg.get("black_main_time", black_main_time)
                white_main_time = msg.get("white_main_time", white_main_time)
                black_in_byoyomi = msg.get("black_in_byoyomi", black_in_byoyomi)
                white_in_byoyomi = msg.get("white_in_byoyomi", white_in_byoyomi)
                black_byoyomi_remaining = msg.get("black_byoyomi_remaining", black_byoyomi_remaining)
                white_byoyomi_remaining = msg.get("white_byoyomi_remaining", white_byoyomi_remaining)
                last_time_sync = now
                pass_color_name = "Black" if msg["color"] == 1 else "White"
                if current_player == my_color:
                    status_msg = f"{pass_color_name} passed. Your turn"
                    status_color = GREEN
                else:
                    status_msg = f"{pass_color_name} passed. Opponent's turn..."
                    status_color = YELLOW

            elif msg_type == "resign":
                game_over = True
                winner = msg["winner"]
                winner_name = "Black" if winner == 1 else "White"
                status_msg = f"{winner_name} wins! (resignation)"
                status_color = GREEN if winner == my_color else RED

            elif msg_type == "time_loss":
                game_over = True
                winner = msg["winner"]
                loser = msg["loser"]
                black_main_time = msg.get("black_main_time", 0)
                white_main_time = msg.get("white_main_time", 0)
                black_in_byoyomi = msg.get("black_in_byoyomi", True)
                white_in_byoyomi = msg.get("white_in_byoyomi", True)
                black_byoyomi_remaining = msg.get("black_byoyomi_remaining", 0)
                white_byoyomi_remaining = msg.get("white_byoyomi_remaining", 0)
                winner_name = "Black" if winner == 1 else "White"
                loser_name = "Black" if loser == 1 else "White"
                status_msg = f"{loser_name} time expired! {winner_name} wins!"
                status_color = GREEN if winner == my_color else RED

            elif msg_type == "error":
                status_msg = msg["message"]
                status_color = RED

            elif msg_type == "opponent_disconnected":
                status_msg = msg["message"]
                status_color = RED
                game_over = True

            elif msg_type == "connection_closed":
                status_msg = "Disconnected from server"
                status_color = RED

        if net.error_msg and not net.connected:
            status_msg = net.error_msg
            status_color = RED

        # Client-side time interpolation for smooth display
        if game_started and not game_over:
            elapsed = now - last_time_sync
            if current_player == 1:
                if not black_in_byoyomi:
                    disp_black_main = max(0, black_main_time - elapsed)
                    disp_black_byo = black_in_byoyomi
                    disp_black_byo_rem = black_byoyomi_remaining
                    if disp_black_main <= 0:
                        disp_black_byo = True
                        disp_black_byo_rem = max(0, game_byoyomi + disp_black_main)
                        disp_black_main = 0
                else:
                    disp_black_main = 0
                    disp_black_byo = True
                    disp_black_byo_rem = max(0, black_byoyomi_remaining - elapsed)
                disp_white_main = white_main_time
                disp_white_byo = white_in_byoyomi
                disp_white_byo_rem = white_byoyomi_remaining
            else:
                if not white_in_byoyomi:
                    disp_white_main = max(0, white_main_time - elapsed)
                    disp_white_byo = white_in_byoyomi
                    disp_white_byo_rem = white_byoyomi_remaining
                    if disp_white_main <= 0:
                        disp_white_byo = True
                        disp_white_byo_rem = max(0, game_byoyomi + disp_white_main)
                        disp_white_main = 0
                else:
                    disp_white_main = 0
                    disp_white_byo = True
                    disp_white_byo_rem = max(0, white_byoyomi_remaining - elapsed)
                disp_black_main = black_main_time
                disp_black_byo = black_in_byoyomi
                disp_black_byo_rem = black_byoyomi_remaining
        else:
            disp_black_main = black_main_time
            disp_white_main = white_main_time
            disp_black_byo = black_in_byoyomi
            disp_white_byo = white_in_byoyomi
            disp_black_byo_rem = black_byoyomi_remaining
            disp_white_byo_rem = white_byoyomi_remaining

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                nw = max(500, event.w)
                nh = max(400, event.h)
                screen = pygame.display.set_mode((nw, nh), pygame.RESIZABLE)
                layout = Layout(nw, nh)
                menu_bar.update_width(nw)
                buttons = make_online_buttons(layout, btn_font)
                if layout.stone_diam != cached_diam:
                    black_stone = create_stone_surface("black", layout.stone_diam)
                    white_stone = create_stone_surface("white", layout.stone_diam)
                    cached_diam = layout.stone_diam
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                # Menu bar handling
                if menu_bar.is_in_menu_area(pos):
                    action = menu_bar.handle_click(pos)
                    if action:
                        mi, ii = action
                        if mi == 0:  # Game menu
                            if ii == 0 and game_started and current_player == my_color and not game_over:
                                net.send({"type": "pass"})
                            elif ii == 1 and game_started and not game_over:
                                net.send({"type": "resign"})
                            elif ii == 2:
                                running = False
                        elif mi == 1:  # Settings - time control
                            if ii < len(TIME_PRESETS) and not game_started:
                                time_preset_idx = ii
                                _, mt, byo = TIME_PRESETS[ii]
                                net.time_control = (mt, byo)
                        elif mi == 2:  # Help
                            if ii == 0:
                                version_popup = not version_popup
                    continue
                else:
                    menu_bar.open_menu = -1
                    version_popup = False

                if game_over:
                    continue
                mx, my_pos = pos
                clicked_btn = False
                for i, btn in enumerate(buttons):
                    if btn.is_clicked((mx, my_pos)):
                        clicked_btn = True
                        if i == 0:  # Pass
                            if game_started and current_player == my_color:
                                net.send({"type": "pass"})
                        elif i == 1:  # Resign
                            if game_started:
                                net.send({"type": "resign"})
                        break
                if not clicked_btn and game_started and current_player == my_color:
                    row, col = layout.screen_to_grid(mx, my_pos)
                    if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
                        net.send({"type": "place_stone", "row": row, "col": col})
            elif event.type == pygame.MOUSEMOTION:
                menu_bar.handle_motion(event.pos)
                for btn in buttons:
                    btn.update_hover(event.pos)

        # Draw
        screen.fill(BG_DARK)

        # Menu bar (bar only - dropdown drawn last for z-order)
        menu_bar.draw_bar(screen, time_preset_idx)

        # Info bar with status
        info_y = MENU_BAR_HEIGHT
        pygame.draw.rect(screen, BG_DARK, (0, info_y, layout.win_w, INFO_BAR_HEIGHT))
        if game_started and not game_over:
            if current_player == my_color:
                info_text = font.render("Your turn", True, GREEN)
            else:
                info_text = font.render("Opponent's turn...", True, YELLOW)
            cxp = layout.win_w // 2 - info_text.get_width() // 2 - 18
            cyp = info_y + INFO_BAR_HEIGHT // 2
            if current_player == 1:
                pygame.draw.circle(screen, (30, 30, 30), (cxp, cyp), 8)
                pygame.draw.circle(screen, (80, 80, 80), (cxp - 2, cyp - 2), 3)
            else:
                pygame.draw.circle(screen, (230, 230, 230), (cxp, cyp), 8)
                pygame.draw.circle(screen, (255, 255, 255), (cxp - 2, cyp - 2), 3)
        else:
            info_text = font.render(status_msg, True, status_color)
        text_rect = info_text.get_rect(center=(layout.win_w // 2, info_y + INFO_BAR_HEIGHT // 2))
        screen.blit(info_text, text_rect)

        # Board
        draw_wood_background(screen, layout)
        draw_board(screen, board, black_stone, white_stone, layout)

        # Clock panels
        black_name = player_name if my_color == 1 else opponent_name
        white_name = player_name if my_color == 2 else opponent_name
        if not black_name:
            black_name = "Black"
        if not white_name:
            white_name = "White"

        draw_clock_panel(screen, font, small_font, layout, "left",
                         black_name, disp_black_main, disp_black_byo,
                         disp_black_byo_rem, current_player == 1 and game_started,
                         my_color == 1)
        draw_clock_panel(screen, font, small_font, layout, "right",
                         white_name, disp_white_main, disp_white_byo,
                         disp_white_byo_rem, current_player == 2 and game_started,
                         my_color == 2)

        # Button bar
        btn_bar_y = layout.win_h - BUTTON_BAR_HEIGHT
        pygame.draw.rect(screen, BG_DARK, (0, btn_bar_y, layout.win_w, BUTTON_BAR_HEIGHT))
        for btn in buttons:
            btn.draw(screen)

        # Color indicator bottom center
        if my_color:
            color_label = "You: Black" if my_color == 1 else "You: White"
            cl_text = btn_font.render(color_label, True, WHITE)
            cl_rect = cl_text.get_rect(center=(layout.win_w // 2, btn_bar_y + 23))
            screen.blit(cl_text, cl_rect)

        # Version popup
        if version_popup:
            popup_w, popup_h = 280, 100
            popup_x = (layout.win_w - popup_w) // 2
            popup_y = (layout.win_h - popup_h) // 2
            popup_rect = pygame.Rect(popup_x, popup_y, popup_w, popup_h)
            pygame.draw.rect(screen, (50, 50, 50), popup_rect, border_radius=8)
            pygame.draw.rect(screen, (100, 100, 100), popup_rect, 2, border_radius=8)
            v1 = font.render("Go Online v1.0", True, WHITE)
            v2 = btn_font.render("Powered by FastAPI + WebSocket", True, (180, 180, 180))
            screen.blit(v1, v1.get_rect(center=(popup_x + popup_w // 2, popup_y + 35)))
            screen.blit(v2, v2.get_rect(center=(popup_x + popup_w // 2, popup_y + 65)))

        # Menu dropdown drawn LAST so it appears on top of everything
        menu_bar.draw_dropdown(screen)

        pygame.display.flip()
        clock.tick(30)

    net.disconnect()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
