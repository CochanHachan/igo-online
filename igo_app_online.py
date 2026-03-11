#!/usr/bin/env python3
"""Go online client - WebSocket connection to server for network play"""
import pygame
import pygame.gfxdraw
import pygame.freetype
import sys
import math
import json
import threading
import asyncio
import websockets
import queue
import urllib.request
import urllib.error
import urllib.parse
import time as time_module
import base64
import io
import os
import pathlib

pygame.init()
pygame.freetype.init()

# --- Embedded clock panel reference image (AI Shogi style) ---
_CLOCK_PANEL_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAMoAAABgCAIAAADTgHp3AAABRUlEQVR4nO3cwQnDMBAAQSlcGSkn5aVnu4pFIGYq8GM5nRyT/f99FzRmPc/pZ+Ban9MPwM3kRUhehORFaJbNnszs00/AxRyOhORFSF6ErPaETC9Cbo6ETC9C8iJktSdkehGSFyE3R0KzLF9kHI6E3BwJmV6E5EVIXoS8mCBktSfkcCQkL0LyIiQvQrOt9mRML0LyIiQvQvIi5K09Ib85EvIxNCG7FyF5EZIXITdHQqYXIS8mCJlehORFyGpPyPQiJC9Cbo6ETC9CVntCphcheRGSFyE3R0I+hibk5kjI7kVIXoTkRUhehPy/FyHTi5C8CMmLkLwIeWtPyE/ahByOhORFSF6ErPaETC9Cbo6EfAxNyOFISF6E3BwJmV6E5EXIiwlCphchqz0h04uQvAjJi5CbIyGrPSGHIyF5EZIXIXkRcnMk9AK7bxjq+ki3cAAAAABJRU5ErkJggg=="

# Lazy-loaded after display is created (convert_alpha needs a display surface)
_clock_panel_base = None
_clock_panel_cache = {}

def _get_clock_panel_scaled(w, h):
    """Return the clock panel image scaled to (w, h), cached.

    The base surface is lazily loaded on first call (requires display to exist).
    """
    global _clock_panel_base
    if _clock_panel_base is None:
        raw = base64.b64decode(_CLOCK_PANEL_PNG_B64)
        buf = io.BytesIO(raw)
        _clock_panel_base = pygame.image.load(buf, "panel.png").convert_alpha()
    key = (w, h)
    if key not in _clock_panel_cache:
        _clock_panel_cache[key] = pygame.transform.smoothscale(_clock_panel_base, (w, h))
    return _clock_panel_cache[key]

BOARD_SIZE = 19
MENU_BAR_HEIGHT = 26
INFO_BAR_HEIGHT = 40
BUTTON_BAR_HEIGHT = 46
CLOCK_PANEL_WIDTH = 240
CLOCK_PANEL_GAP = 8  # gap between board edge and clock panel
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
# Clock panel text/icon colors (panel background uses embedded image)
CLOCK_ICON = (225, 215, 200)    # light icon color
CLOCK_TEXT = (245, 238, 225)    # white/cream text
CLOCK_TIME_TEXT = (255, 255, 255)  # bright white time

# Time control presets: (label, main_time_seconds, byoyomi_seconds)
TIME_PRESETS = [
    ("1\u5206+30\u79d2", 60, 30),
    ("10\u5206+30\u79d2", 600, 30),
]

class _FreetypeMenuFont:
    """Wrapper around pygame.freetype.Font to mimic pygame.font.Font API.

    pygame.font.Font cannot select a face index within TTC files, so it always
    loads face 0 (e.g. 'Yu Gothic Regular' instead of 'Yu Gothic UI Regular').
    This wrapper uses pygame.freetype which supports font_index, while exposing
    the same render() / size() interface expected by MenuBar.
    """

    def __init__(self, ft_font: pygame.freetype.Font):
        self._ft = ft_font

    def render(self, text: str, antialias: bool, color: tuple, background: object = None) -> pygame.Surface:
        surf, _rect = self._ft.render(text, fgcolor=color)
        return surf

    def size(self, text: str) -> tuple:
        rect = self._ft.get_rect(text)
        return (rect.width, rect.height)


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
        usable_w = win_w - (CLOCK_PANEL_WIDTH + CLOCK_PANEL_GAP) * 2
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
        # Clock panel positions (with gap from board)
        self.clock_left_x = self.offset_x - CLOCK_PANEL_GAP - CLOCK_PANEL_WIDTH
        self.clock_right_x = self.offset_x + self.board_px + CLOCK_PANEL_GAP
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
            ("\u30d5\u30a1\u30a4\u30eb(F)", ["\u65b0\u898f\u5bfe\u5c40", "\u68cb\u8b5c\u3092\u958b\u304f", "\u68cb\u8b5c\u306e\u4fdd\u5b58", "\u7d42\u4e86"]),
            ("\u7de8\u96c6(E)", ["\u4e00\u624b\u623b\u3059", "\u3084\u308a\u76f4\u3057", "\u30b3\u30d4\u30fc", "\u8cbc\u308a\u4ed8\u3051"]),
            ("\u8868\u793a(V)", ["\u5ea7\u6a19\u8868\u793a", "\u6700\u7d42\u624b\u8868\u793a"]),
            ("\u5bfe\u5c40(P)", ["\u30d1\u30b9", "\u6295\u4e86", "\u4e2d\u65ad"]),
            ("\u5b9a\u77f3(J)", ["\u5b9a\u77f3\u4e00\u89a7"]),
            ("\u5c40\u9762\u7de8\u96c6(B)", ["\u5c40\u9762\u7de8\u96c6"]),
            ("\u30c4\u30fc\u30eb(T)", ["\u6301\u3061\u6642\u9593: 1\u5206+30\u79d2", "\u6301\u3061\u6642\u9593: 10\u5206+30\u79d2"]),
            ("\u30d8\u30eb\u30d7(H)", ["\u30d0\u30fc\u30b8\u30e7\u30f3\u60c5\u5831"]),
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
            if mi == 6 and j < len(TIME_PRESETS):
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
    return f"{h:02d}:{m:02d}:{sec:02d}"

def draw_clock_icon(screen, cx, cy, radius, color):
    """Draw a small stopwatch icon with anti-aliased circles — bold/thick style."""
    # Use a 4x supersampled surface for smooth, bold rendering
    scale = 4
    sr = radius * scale
    sz = (radius + 5) * 2 * scale
    tmp = pygame.Surface((sz, sz), pygame.SRCALPHA)
    tcx = sz // 2
    tcy = sz // 2 + 2 * scale
    lw = max(2, scale)  # line width at supersampled scale (bold)

    # Thick circle outline — fill a ring
    outer_r = sr
    inner_r = max(1, sr - lw * 2)
    for ri in range(inner_r, outer_r + 1):
        pygame.gfxdraw.aacircle(tmp, tcx, tcy, ri, color)
    # Also fill to make it solid
    pygame.gfxdraw.filled_circle(tmp, tcx, tcy, outer_r, color)
    # Cut out the interior to form a ring (transparent center)
    interior = max(1, sr - lw * 2 - 1)
    pygame.gfxdraw.filled_circle(tmp, tcx, tcy, interior, (0, 0, 0, 0))

    # Top bar (thick)
    bar_w = lw * 2
    pygame.draw.line(tmp, color, (tcx - 4 * scale, tcy - sr - 2 * scale),
                     (tcx + 4 * scale, tcy - sr - 2 * scale), bar_w)
    # Hands (thick)
    pygame.draw.line(tmp, color, (tcx, tcy), (tcx, tcy - sr + 4 * scale), bar_w)
    pygame.draw.line(tmp, color, (tcx, tcy), (tcx + sr - 5 * scale, tcy), bar_w)
    # Center dot (bold)
    dot_r = max(2, lw)
    pygame.gfxdraw.aacircle(tmp, tcx, tcy, dot_r, color)
    pygame.gfxdraw.filled_circle(tmp, tcx, tcy, dot_r, color)

    # Scale down with smoothscale for anti-aliasing
    final_sz = sz // scale
    small = pygame.transform.smoothscale(tmp, (final_sz, final_sz))
    screen.blit(small, (cx - final_sz // 2, cy - final_sz // 2 + 1))


def _draw_stone_icon(surface, cx, cy, radius, color):
    """Draw a small go stone icon with natural gloss using radial gradient on a mask."""
    # Use 4x supersampled surface for smooth edges
    scale = 4
    sr = radius * scale
    sz = (radius + 2) * 2 * scale
    tcx = sz // 2
    tcy = sz // 2

    # Base stone surface
    tmp = pygame.Surface((sz, sz), pygame.SRCALPHA)

    if color == "black":
        # Draw base stone
        pygame.gfxdraw.aacircle(tmp, tcx, tcy, sr, (30, 30, 30, 255))
        pygame.gfxdraw.filled_circle(tmp, tcx, tcy, sr, (30, 30, 30, 255))
        # Gloss overlay: draw a radial gradient on a separate surface, then mask
        gloss = pygame.Surface((sz, sz), pygame.SRCALPHA)
        hl_cx = tcx - int(sr * 0.28)
        hl_cy = tcy - int(sr * 0.28)
        hl_r = int(sr * 0.55)
        for i in range(hl_r, 0, -1):
            t = 1.0 - (i / hl_r)  # 0 at edge, 1 at center
            val = int(30 + t * 60)  # 30 -> 90
            a = int(t * t * 180)    # quadratic falloff for soft edge
            pygame.gfxdraw.filled_circle(gloss, hl_cx, hl_cy, i, (val, val, val, a))
        # Mask gloss to stone circle
        mask = pygame.Surface((sz, sz), pygame.SRCALPHA)
        pygame.gfxdraw.filled_circle(mask, tcx, tcy, sr, (255, 255, 255, 255))
        gloss.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        tmp.blit(gloss, (0, 0))
    else:
        # Draw base white stone — slightly smaller radius to match black stone visual size
        wr = sr - scale * 3
        for i in range(wr, 0, -1):
            t = i / wr  # 1.0 at edge, 0.0 at center
            val = int(240 - t * 20)  # 220 at edge -> 240 at center
            pygame.gfxdraw.filled_circle(tmp, tcx, tcy, i, (val, val, val, 255))
        pygame.gfxdraw.aacircle(tmp, tcx, tcy, wr, (210, 210, 210, 255))
        # Gloss highlight
        gloss = pygame.Surface((sz, sz), pygame.SRCALPHA)
        hl_cx = tcx - int(sr * 0.24)
        hl_cy = tcy - int(sr * 0.24)
        hl_r = int(wr * 0.5)
        for i in range(hl_r, 0, -1):
            t = 1.0 - (i / hl_r)
            val = int(235 + t * 20)  # 235 -> 255
            a = int(t * t * 160)
            pygame.gfxdraw.filled_circle(gloss, hl_cx, hl_cy, i, (val, val, val, a))
        mask = pygame.Surface((sz, sz), pygame.SRCALPHA)
        pygame.gfxdraw.filled_circle(mask, tcx, tcy, wr, (255, 255, 255, 255))
        gloss.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        tmp.blit(gloss, (0, 0))

    # Scale down with smoothscale for anti-aliasing
    final_sz = sz // scale
    small = pygame.transform.smoothscale(tmp, (final_sz, final_sz))
    surface.blit(small, (cx - final_sz // 2, cy - final_sz // 2))


def _draw_3d_wood_panel(screen, rect):
    """Draw a warm wood panel with subtle 3D edge — natural look, no heavy border.

    Structure:
      - 1px thin dark edge
      - 1px subtle highlight on top/left, shadow on bottom/right
      - Smooth warm brown gradient fill
    """
    x, y, w, h = rect.x, rect.y, rect.width, rect.height

    # 1px thin dark border
    pygame.draw.rect(screen, (90, 45, 20), rect, 1)

    # Subtle 1px bevel just inside the border
    # Top highlight
    pygame.draw.line(screen, (165, 90, 55), (x + 1, y + 1), (x + w - 2, y + 1))
    # Left highlight
    pygame.draw.line(screen, (160, 85, 50), (x + 1, y + 1), (x + 1, y + h - 2))
    # Bottom shadow
    pygame.draw.line(screen, (100, 42, 18), (x + 1, y + h - 2), (x + w - 2, y + h - 2))
    # Right shadow
    pygame.draw.line(screen, (105, 45, 20), (x + w - 2, y + 1), (x + w - 2, y + h - 2))

    # Main gradient fill (inside the 2px frame)
    ix = x + 2
    iy = y + 2
    iw = w - 4
    ih = h - 4
    for row in range(ih):
        t = row / max(1, ih - 1)
        # Warm brown: top (142, 66, 30) -> bottom (152, 58, 26)
        r = int(142 + t * 10)
        g = int(66 - t * 8)
        b = int(30 - t * 4)
        pygame.draw.line(screen, (r, g, b), (ix, iy + row), (ix + iw - 1, iy + row))


def _draw_icon_box(screen, cx, cy, size, stone_color):
    """Draw a go stone icon without background box — just the stone on the panel."""
    stone_r = max(5, size // 2 - 1)
    _draw_stone_icon(screen, cx, cy, stone_r, stone_color)


def draw_clock_panel(screen, font, small_font, clock_font, clock_name_font,
                     layout, side, player_name, main_time, in_byoyomi,
                     byoyomi_remaining, is_active, my_color_is_this):
    """Draw the clock panel with warm wood background (AI Shogi style).

    Layout matching reference:
      Row 1: [icon box]  Player Name       (small, regular weight)
      Row 2: [clock icon]     HH:MM:SS    (larger, right-positioned)
    """
    if side == "left":
        px = max(0, layout.clock_left_x)
        pw = layout.offset_x - CLOCK_PANEL_GAP - px
    else:
        px = layout.clock_right_x
        pw = min(layout.win_w, px + CLOCK_PANEL_WIDTH) - px

    # Panel aspect ratio matching reference (218 x 109 ~ 1:0.5)
    aspect = 109.0 / 218.0
    ph = max(70, int(pw * aspect))
    ph = min(ph, layout.clock_h - 10)
    py = layout.clock_y + (layout.clock_h - ph) // 2

    if pw < 40:
        return

    panel_rect = pygame.Rect(px, py, pw, ph)

    # Draw the wood panel background
    _draw_3d_wood_panel(screen, panel_rect)

    # Content area (inside the thin frame)
    cx0 = panel_rect.x + 4
    cy0 = panel_rect.y + 4
    cw = pw - 8
    ch = ph - 8

    # --- Row 1: Icon box + Player name (upper portion) ---
    row1_cy = cy0 + int(ch * 0.28)
    box_size = max(18, int(ch * 0.36))
    box_cx = cx0 + 18 + box_size // 2
    stone_color = "black" if side == "left" else "white"
    _draw_icon_box(screen, box_cx, row1_cy, box_size, stone_color)

    # Player name: left-aligned, slightly left of center
    text_left_x = cx0 + 18 + box_size + 10
    max_name_w = panel_rect.right - text_left_x - 4
    name_display = player_name
    while clock_name_font.size(name_display)[0] > max_name_w and len(name_display) > 3:
        name_display = name_display[:-1]
    name_surf = clock_name_font.render(name_display, True, CLOCK_TEXT)
    screen.blit(name_surf, name_surf.get_rect(midleft=(text_left_x, row1_cy)))

    # --- Row 2: Clock icon + Time (lower portion) ---
    row2_cy = cy0 + int(ch * 0.68)
    icon_r = max(9, int(ch * 0.13))
    draw_clock_icon(screen, box_cx, row2_cy, icon_r, CLOCK_ICON)

    # Time display: left-aligned with player name
    if in_byoyomi:
        time_str = format_time_hms(byoyomi_remaining)
        if byoyomi_remaining < 10:
            time_color = (255, 100, 80)
        else:
            time_color = CLOCK_TIME_TEXT
    else:
        time_str = format_time_hms(main_time)
        if main_time <= 10:
            time_color = (255, 100, 80)
        elif main_time <= 30:
            time_color = (255, 200, 80)
        else:
            time_color = CLOCK_TIME_TEXT
    time_surf = clock_font.render(time_str, True, time_color)
    screen.blit(time_surf, time_surf.get_rect(midleft=(text_left_x, row2_cy + 2)))


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
        encoded_name = urllib.parse.quote(player_name, safe="")
        url = f"{http_url}/find_match?name={encoded_name}&main_time={mt}&byoyomi={byo}"
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

        url = f"{server_url}/ws/{room_code}/{urllib.parse.quote(player_name, safe='')}"
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

# --------------- Credential Storage ---------------

_CRED_FILE = pathlib.Path.home() / ".igo_credentials.json"


def _load_credentials():
    """Load saved credentials from file. Returns dict or None."""
    try:
        if _CRED_FILE.exists():
            data = json.loads(_CRED_FILE.read_text(encoding="utf-8"))
            if data.get("nickname") and data.get("password"):
                return data
    except Exception:
        pass
    return None


def _save_credentials(nickname, password, name=""):
    """Save credentials to file for auto-login."""
    try:
        _CRED_FILE.write_text(json.dumps({
            "nickname": nickname,
            "password": password,
            "name": name,
        }, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _clear_credentials():
    """Remove saved credentials."""
    try:
        if _CRED_FILE.exists():
            _CRED_FILE.unlink()
    except Exception:
        pass


def _http_post_json(url, data):
    """Send a POST request with JSON body and return parsed response."""
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"ok": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# --------------- Auth Screen (Register / Login) ---------------

def _draw_text_field(screen, font, rect, text, active, cursor_blink, ime_text=""):
    """Draw a text input field with optional IME composition underline."""
    color = INPUT_ACTIVE if active else INPUT_BG
    pygame.draw.rect(screen, color, rect, border_radius=4)
    pygame.draw.rect(screen, WHITE, rect, 1, border_radius=4)
    ime_show = ime_text if active else ""
    cursor = "|" if active and cursor_blink < 30 and not ime_show else ""
    display_text = text + ime_show + cursor
    ts = font.render(display_text, True, WHITE)
    screen.blit(ts, (rect.x + 8, rect.y + 8))
    if ime_show:
        comp_x = rect.x + 8 + font.size(text)[0]
        comp_w = font.size(ime_show)[0]
        comp_y = rect.y + 30
        pygame.draw.line(screen, YELLOW, (comp_x, comp_y), (comp_x + comp_w, comp_y), 2)


def _draw_password_field(screen, font, rect, text, active, cursor_blink, ime_text=""):
    """Draw a password field (shows dots instead of text)."""
    color = INPUT_ACTIVE if active else INPUT_BG
    pygame.draw.rect(screen, color, rect, border_radius=4)
    pygame.draw.rect(screen, WHITE, rect, 1, border_radius=4)
    ime_show = ime_text if active else ""
    cursor = "|" if active and cursor_blink < 30 and not ime_show else ""
    masked = "\u25cf" * len(text) + ime_show + cursor
    ts = font.render(masked, True, WHITE)
    screen.blit(ts, (rect.x + 8, rect.y + 8))


def auth_screen(screen, font, btn_font, server_base_url):
    """Login / Registration screen. Returns (nickname, name) or None if quit."""
    clock = pygame.time.Clock()
    http_url = server_base_url.replace("wss://", "https://").replace("ws://", "http://")

    # Try auto-login with saved credentials
    saved = _load_credentials()
    if saved:
        result = _http_post_json(f"{http_url}/login", {
            "nickname": saved["nickname"],
            "password": saved["password"],
        })
        if result.get("ok"):
            return (result["nickname"], result.get("name", saved.get("name", "")))
        # Saved credentials invalid, clear them
        _clear_credentials()

    # State
    mode = "login"  # "login" or "register"
    # Register fields: name, nickname, password, skill_level
    reg_name = ""
    reg_nickname = ""
    reg_password = ""
    reg_skill_level = ""
    # Login fields: nickname, password
    login_nickname = ""
    login_password = ""
    # UI state
    active_field = 0  # which field is focused
    cursor_blink = 0
    ime_composing = ""
    save_creds = True  # checkbox: save credentials
    message = ""  # status/error message
    message_color = RED
    message_timer = 0

    LINK_COLOR = (100, 180, 255)
    LINK_HOVER_COLOR = (140, 210, 255)

    pygame.key.start_text_input()

    def get_fields():
        if mode == "register":
            return [reg_name, reg_nickname, reg_password, reg_skill_level]
        else:
            return [login_nickname, login_password]

    def set_field(idx, val):
        nonlocal reg_name, reg_nickname, reg_password, reg_skill_level, login_nickname, login_password
        if mode == "register":
            if idx == 0: reg_name = val
            elif idx == 1: reg_nickname = val
            elif idx == 2: reg_password = val
            elif idx == 3: reg_skill_level = val
        else:
            if idx == 0: login_nickname = val
            elif idx == 1: login_password = val

    def field_count():
        return 4 if mode == "register" else 2

    def commit_ime():
        """Commit any pending IME composition text to the current field."""
        nonlocal ime_composing
        if ime_composing:
            fields = get_fields()
            if active_field < len(fields):
                set_field(active_field, fields[active_field] + ime_composing)
            ime_composing = ""

    def switch_field(new_idx):
        """Switch active field, committing any IME composition first."""
        nonlocal active_field
        commit_ime()
        active_field = new_idx

    def do_login():
        """Attempt login and return result tuple or None."""
        nonlocal message, message_color, message_timer
        commit_ime()
        if not login_nickname.strip() or not login_password:
            message = "\u30cb\u30c3\u30af\u30cd\u30fc\u30e0\u3068\u30d1\u30b9\u30ef\u30fc\u30c9\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044"
            message_color = RED
            message_timer = 120
            return None
        result = _http_post_json(f"{http_url}/login", {
            "nickname": login_nickname, "password": login_password,
        })
        if result.get("ok"):
            if save_creds:
                _save_credentials(login_nickname, login_password, result.get("name", ""))
            pygame.key.stop_text_input()
            return (result["nickname"], result.get("name", ""))
        else:
            message = result.get("error", "\u30ed\u30b0\u30a4\u30f3\u5931\u6557")
            message_color = RED
            message_timer = 120
            return None

    def do_register():
        """Attempt registration and switch to login on success."""
        nonlocal mode, active_field, ime_composing, message, message_color, message_timer
        nonlocal login_nickname, login_password
        commit_ime()
        if not reg_name.strip() or not reg_nickname.strip() or not reg_password:
            message = "\u6c0f\u540d\u30fb\u30cb\u30c3\u30af\u30cd\u30fc\u30e0\u30fb\u30d1\u30b9\u30ef\u30fc\u30c9\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044"
            message_color = RED
            message_timer = 120
            return
        result = _http_post_json(f"{http_url}/register", {
            "name": reg_name, "nickname": reg_nickname, "password": reg_password,
            "skill_level": reg_skill_level,
        })
        if result.get("ok"):
            # Carry credentials to login screen
            login_nickname = reg_nickname
            login_password = reg_password
            mode = "login"
            active_field = 0
            ime_composing = ""
            message = "\u767b\u9332\u6210\u529f\uff01\u30ed\u30b0\u30a4\u30f3\u3057\u3066\u304f\u3060\u3055\u3044"
            message_color = GREEN
            message_timer = 180
        else:
            message = result.get("error", "\u767b\u9332\u5931\u6557")
            message_color = RED
            message_timer = 120

    while True:
        was_composing = bool(ime_composing)
        ime_confirmed = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.key.stop_text_input()
                return None
            elif event.type == pygame.VIDEORESIZE:
                nw = max(500, event.w)
                nh = max(400, event.h)
                screen = pygame.display.set_mode((nw, nh), pygame.RESIZABLE)
            elif event.type == pygame.TEXTINPUT:
                fields = get_fields()
                if active_field < len(fields):
                    set_field(active_field, fields[active_field] + event.text)
                if ime_composing or was_composing:
                    ime_confirmed = True
                ime_composing = ""
            elif event.type == pygame.TEXTEDITING:
                ime_composing = event.text
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    switch_field((active_field + 1) % field_count())
                elif event.key == pygame.K_RETURN:
                    if ime_composing or ime_confirmed or was_composing:
                        commit_ime()
                    else:
                        commit_ime()
                        if mode == "login":
                            login_result = do_login()
                            if login_result is not None:
                                return login_result
                        else:
                            do_register()
                elif event.key == pygame.K_BACKSPACE:
                    if not ime_composing:
                        fields = get_fields()
                        if active_field < len(fields):
                            set_field(active_field, fields[active_field][:-1])
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                w, h = screen.get_size()
                cx = w // 2
                # Field clicks
                base_y = 130 if mode == "login" else 100
                for fi in range(field_count()):
                    field_rect = pygame.Rect(cx - 160, base_y + fi * 70 + 22, 320, 35)
                    if field_rect.collidepoint(mx, my):
                        if fi != active_field:
                            switch_field(fi)
                # --- Login mode click targets ---
                if mode == "login":
                    # Save checkbox
                    cb_y = base_y + 2 * 70 + 5
                    cb_rect = pygame.Rect(cx - 160, cb_y, 20, 20)
                    if cb_rect.collidepoint(mx, my):
                        save_creds = not save_creds
                    # Login button
                    login_btn_y = cb_y + 40
                    login_btn_rect = pygame.Rect(cx - 80, login_btn_y, 160, 40)
                    if login_btn_rect.collidepoint(mx, my):
                        login_result = do_login()
                        if login_result is not None:
                            return login_result
                    # Registration link
                    link_text_str = "\u30a2\u30ab\u30a6\u30f3\u30c8\u3092\u304a\u6301\u3061\u3067\u306a\u3044\u65b9\u306f\u3053\u3061\u3089\u304b\u3089\u767b\u9332\u3057\u3066\u304f\u3060\u3055\u3044\u3002"
                    link_w, link_h = btn_font.size(link_text_str)
                    link_y = login_btn_y + 60
                    link_rect = pygame.Rect(cx - link_w // 2, link_y, link_w, link_h)
                    if link_rect.collidepoint(mx, my):
                        commit_ime()
                        mode = "register"
                        active_field = 0
                        ime_composing = ""
                        message = ""
                # --- Register mode click targets ---
                else:
                    # Register button
                    reg_btn_y = base_y + 4 * 70 + 10
                    reg_btn_rect = pygame.Rect(cx - 80, reg_btn_y, 160, 40)
                    if reg_btn_rect.collidepoint(mx, my):
                        do_register()
                    # Back to login link
                    back_text_str = "\u30ed\u30b0\u30a4\u30f3\u753b\u9762\u306b\u623b\u308b"
                    back_w, back_h = btn_font.size(back_text_str)
                    back_y = reg_btn_y + 55
                    back_rect = pygame.Rect(cx - back_w // 2, back_y, back_w, back_h)
                    if back_rect.collidepoint(mx, my):
                        commit_ime()
                        mode = "login"
                        active_field = 0
                        ime_composing = ""
                        message = ""

        # --- Draw ---
        w, h = screen.get_size()
        cx = w // 2
        screen.fill(BG_DARK)
        cursor_blink = (cursor_blink + 1) % 60
        mx_h, my_h = pygame.mouse.get_pos()

        # Title
        title = font.render("\u56f2\u7881\u30aa\u30f3\u30e9\u30a4\u30f3", True, WHITE)
        screen.blit(title, title.get_rect(center=(cx, 40)))

        if mode == "login":
            # --- LOGIN SCREEN ---
            subtitle = btn_font.render("\u30ed\u30b0\u30a4\u30f3", True, (200, 200, 200))
            screen.blit(subtitle, subtitle.get_rect(center=(cx, 75)))

            base_y = 130
            labels = ["\u30cb\u30c3\u30af\u30cd\u30fc\u30e0:", "\u30d1\u30b9\u30ef\u30fc\u30c9:"]
            fields = [login_nickname, login_password]
            for fi, (label, val) in enumerate(zip(labels, fields)):
                lbl = btn_font.render(label, True, WHITE)
                screen.blit(lbl, (cx - 160, base_y + fi * 70))
                field_rect = pygame.Rect(cx - 160, base_y + fi * 70 + 22, 320, 35)
                is_pw = (fi == 1)
                if is_pw:
                    _draw_password_field(screen, btn_font, field_rect, val,
                                         active_field == fi, cursor_blink,
                                         ime_composing if active_field == fi else "")
                else:
                    _draw_text_field(screen, btn_font, field_rect, val,
                                     active_field == fi, cursor_blink,
                                     ime_composing if active_field == fi else "")

            # Save checkbox
            cb_y = base_y + 2 * 70 + 5
            cb_rect = pygame.Rect(cx - 160, cb_y, 20, 20)
            pygame.draw.rect(screen, INPUT_BG, cb_rect, border_radius=3)
            pygame.draw.rect(screen, WHITE, cb_rect, 1, border_radius=3)
            if save_creds:
                pygame.draw.line(screen, GREEN, (cb_rect.x + 4, cb_rect.y + 10),
                                 (cb_rect.x + 8, cb_rect.y + 16), 2)
                pygame.draw.line(screen, GREEN, (cb_rect.x + 8, cb_rect.y + 16),
                                 (cb_rect.x + 16, cb_rect.y + 4), 2)
            cb_label = btn_font.render("\u30ed\u30b0\u30a4\u30f3\u60c5\u5831\u3092\u4fdd\u5b58", True, (200, 200, 200))
            screen.blit(cb_label, (cb_rect.right + 8, cb_y + 2))

            # Login button
            login_btn_y = cb_y + 40
            login_btn_rect = pygame.Rect(cx - 80, login_btn_y, 160, 40)
            btn_color = GREEN if login_btn_rect.collidepoint(mx_h, my_h) else (60, 160, 60)
            pygame.draw.rect(screen, btn_color, login_btn_rect, border_radius=6)
            login_btn_text = font.render("\u30ed\u30b0\u30a4\u30f3", True, WHITE)
            screen.blit(login_btn_text, login_btn_text.get_rect(center=login_btn_rect.center))

            # Registration link
            link_y = login_btn_y + 60
            link_text_str = "\u30a2\u30ab\u30a6\u30f3\u30c8\u3092\u304a\u6301\u3061\u3067\u306a\u3044\u65b9\u306f\u3053\u3061\u3089\u304b\u3089\u767b\u9332\u3057\u3066\u304f\u3060\u3055\u3044\u3002"
            link_w, link_h = btn_font.size(link_text_str)
            link_rect = pygame.Rect(cx - link_w // 2, link_y, link_w, link_h)
            is_hover = link_rect.collidepoint(mx_h, my_h)
            lc = LINK_HOVER_COLOR if is_hover else LINK_COLOR
            link_surf = btn_font.render(link_text_str, True, lc)
            screen.blit(link_surf, link_rect.topleft)
            # Underline
            pygame.draw.line(screen, lc,
                             (link_rect.x, link_rect.bottom),
                             (link_rect.right, link_rect.bottom), 1)

            # Message
            if message and message_timer > 0:
                msg_surf = btn_font.render(message, True, message_color)
                screen.blit(msg_surf, msg_surf.get_rect(center=(cx, link_y + 40)))
                message_timer -= 1

        else:
            # --- REGISTER SCREEN ---
            subtitle = btn_font.render("\u65b0\u898f\u767b\u9332", True, (200, 200, 200))
            screen.blit(subtitle, subtitle.get_rect(center=(cx, 75)))

            base_y = 100
            labels = ["\u6c0f\u540d:", "\u30cb\u30c3\u30af\u30cd\u30fc\u30e0:", "\u30d1\u30b9\u30ef\u30fc\u30c9:", "\u68cb\u529b:"]
            fields = [reg_name, reg_nickname, reg_password, reg_skill_level]
            for fi, (label, val) in enumerate(zip(labels, fields)):
                lbl = btn_font.render(label, True, WHITE)
                screen.blit(lbl, (cx - 160, base_y + fi * 70))
                field_rect = pygame.Rect(cx - 160, base_y + fi * 70 + 22, 320, 35)
                is_pw = (fi == 2)
                if is_pw:
                    _draw_password_field(screen, btn_font, field_rect, val,
                                         active_field == fi, cursor_blink,
                                         ime_composing if active_field == fi else "")
                else:
                    _draw_text_field(screen, btn_font, field_rect, val,
                                     active_field == fi, cursor_blink,
                                     ime_composing if active_field == fi else "")

            # Hint for skill level
            hint_text = "\u4f8b: \u521d\u6bb5\u30015\u7d1a\u306a\u3069\uff08\u4efb\u610f\uff09"
            hint_surf = btn_font.render(hint_text, True, (120, 120, 120))
            hint_field_rect = pygame.Rect(cx - 160, base_y + 3 * 70 + 22, 320, 35)
            screen.blit(hint_surf, (hint_field_rect.right + 8, hint_field_rect.y + 8))

            # Register button
            reg_btn_y = base_y + 4 * 70 + 10
            reg_btn_rect = pygame.Rect(cx - 80, reg_btn_y, 160, 40)
            btn_color = GREEN if reg_btn_rect.collidepoint(mx_h, my_h) else (60, 160, 60)
            pygame.draw.rect(screen, btn_color, reg_btn_rect, border_radius=6)
            reg_btn_text = font.render("\u767b\u9332", True, WHITE)
            screen.blit(reg_btn_text, reg_btn_text.get_rect(center=reg_btn_rect.center))

            # Back to login link
            back_y = reg_btn_y + 55
            back_text_str = "\u30ed\u30b0\u30a4\u30f3\u753b\u9762\u306b\u623b\u308b"
            back_w, back_h = btn_font.size(back_text_str)
            back_rect = pygame.Rect(cx - back_w // 2, back_y, back_w, back_h)
            is_hover = back_rect.collidepoint(mx_h, my_h)
            bc = LINK_HOVER_COLOR if is_hover else LINK_COLOR
            back_surf = btn_font.render(back_text_str, True, bc)
            screen.blit(back_surf, back_rect.topleft)
            pygame.draw.line(screen, bc,
                             (back_rect.x, back_rect.bottom),
                             (back_rect.right, back_rect.bottom), 1)

            # Message
            if message and message_timer > 0:
                msg_surf = btn_font.render(message, True, message_color)
                screen.blit(msg_surf, msg_surf.get_rect(center=(cx, back_y + 40)))
                message_timer -= 1

        pygame.display.flip()
        clock.tick(30)


# --------------- Connection Screen ---------------

def connection_screen(screen, font, btn_font, nickname="Player"):
    clock = pygame.time.Clock()
    server_url = "wss://igo-online.onrender.com"
    player_name = nickname
    active_field = 0
    cursor_blink = 0
    time_preset_idx = 0  # default: 1min + 30sec
    ime_composing = ""  # IME composition string (before confirmation)

    # Enable text input for IME support (Japanese kanji input etc.)
    pygame.key.start_text_input()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.key.stop_text_input()
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
                    pygame.key.stop_text_input()
                    return (server_url, player_name, time_preset_idx)
            elif event.type == pygame.TEXTINPUT:
                # IME confirmed text or direct ASCII input
                if active_field == 0:
                    server_url += event.text
                else:
                    player_name += event.text
                ime_composing = ""
            elif event.type == pygame.TEXTEDITING:
                # IME composing (e.g. showing候補 before Enter)
                ime_composing = event.text
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    active_field = 1 - active_field
                elif event.key == pygame.K_RETURN:
                    if not ime_composing:
                        pygame.key.stop_text_input()
                        return (server_url, player_name, time_preset_idx)
                elif event.key == pygame.K_BACKSPACE:
                    if not ime_composing:
                        if active_field == 0:
                            server_url = server_url[:-1]
                        else:
                            player_name = player_name[:-1]

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
        ime_show_0 = ime_composing if active_field == 0 else ""
        cursor_0 = "|" if active_field == 0 and cursor_blink < 30 and not ime_show_0 else ""
        url_text = server_url + ime_show_0 + cursor_0
        ts1 = btn_font.render(url_text, True, WHITE)
        screen.blit(ts1, (field_rect1.x + 8, field_rect1.y + 8))
        # Underline IME composing text
        if ime_show_0:
            comp_x = field_rect1.x + 8 + btn_font.size(server_url)[0]
            comp_w = btn_font.size(ime_show_0)[0]
            comp_y = field_rect1.y + 30
            pygame.draw.line(screen, YELLOW, (comp_x, comp_y), (comp_x + comp_w, comp_y), 2)

        lbl2 = btn_font.render("Player Name:", True, WHITE)
        screen.blit(lbl2, (cx - 180, h // 2 - 30))
        field_rect2 = pygame.Rect(cx - 180, h // 2 - 10, 360, 35)
        color2 = INPUT_ACTIVE if active_field == 1 else INPUT_BG
        pygame.draw.rect(screen, color2, field_rect2, border_radius=4)
        pygame.draw.rect(screen, WHITE, field_rect2, 1, border_radius=4)
        ime_show_1 = ime_composing if active_field == 1 else ""
        cursor_1 = "|" if active_field == 1 and cursor_blink < 30 and not ime_show_1 else ""
        name_text = player_name + ime_show_1 + cursor_1
        ts2 = btn_font.render(name_text, True, WHITE)
        screen.blit(ts2, (field_rect2.x + 8, field_rect2.y + 8))
        # Underline IME composing text
        if ime_show_1:
            comp_x = field_rect2.x + 8 + btn_font.size(player_name)[0]
            comp_w = btn_font.size(ime_show_1)[0]
            comp_y = field_rect2.y + 30
            pygame.draw.line(screen, YELLOW, (comp_x, comp_y), (comp_x + comp_w, comp_y), 2)

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
    # General font paths (for game text, clock, etc.)
    font_paths = [
        # Windows standard fonts
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/YuGothM.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
        # Linux fonts
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/usr/share/fonts/truetype/takao-gothic/TakaoPGothic.ttf",
    ]
    for fp in font_paths:
        try:
            font = pygame.font.Font(fp, 18)
            btn_font = pygame.font.Font(fp, 14)
            small_font = pygame.font.Font(fp, 13)
            clock_font = pygame.font.Font(fp, 29)
            clock_name_font = pygame.font.Font(fp, 26)
            break
        except Exception:
            continue
    if font is None:
        font = pygame.font.SysFont("meiryo,yugothic,msgothic,notosanscjk,sans", 18)
        btn_font = pygame.font.SysFont("meiryo,yugothic,msgothic,notosanscjk,sans", 14)
        small_font = pygame.font.SysFont("meiryo,yugothic,msgothic,notosanscjk,sans", 13)
        clock_font = pygame.font.SysFont("meiryo,yugothic,msgothic,notosanscjk,sans", 29)
        clock_name_font = pygame.font.SysFont("meiryo,yugothic,msgothic,notosanscjk,sans", 26)

    # Menu font: Yu Gothic UI (standard Windows menu font)
    # pygame.font cannot select face index in TTC files, so use pygame.freetype
    # which supports font_index to pick the UI variant (face 1 in YuGothR.ttc)
    menu_font = None
    _ft_menu_candidates = [
        ("C:/Windows/Fonts/YuGothR.ttc", 1, 13),   # Yu Gothic UI Regular
        ("C:/Windows/Fonts/meiryo.ttc", 2, 13),     # Meiryo UI Regular
        ("C:/Windows/Fonts/msgothic.ttc", 2, 12),   # MS UI Gothic
    ]
    for _fp, _fi, _sz in _ft_menu_candidates:
        try:
            _ft = pygame.freetype.Font(_fp, size=_sz, font_index=_fi)
            menu_font = _FreetypeMenuFont(_ft)
            break
        except Exception:
            continue
    if menu_font is None:
        menu_font = pygame.font.SysFont("yugothicui,meiryoui,msuigothic,notosanscjk,sans", 13)

    # Auth screen (register / login)
    server_base_url = "wss://igo-online.onrender.com"
    auth_result = auth_screen(screen, font, btn_font, server_base_url)
    if auth_result is None:
        pygame.quit()
        sys.exit()
    auth_nickname, auth_name = auth_result

    result = connection_screen(screen, font, btn_font, auth_nickname)
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

    menu_bar = MenuBar(menu_font, INIT_W)

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
                        if mi == 0:  # File menu
                            if ii == 3:  # Exit
                                running = False
                        elif mi == 1:  # Edit menu
                            pass  # Not implemented in online mode
                        elif mi == 2:  # View menu
                            pass  # Not implemented yet
                        elif mi == 3:  # Game menu (対局)
                            if ii == 0 and game_started and current_player == my_color and not game_over:
                                net.send({"type": "pass"})
                            elif ii == 1 and game_started and not game_over:
                                net.send({"type": "resign"})
                        elif mi == 4:  # Joseki
                            pass  # Not implemented yet
                        elif mi == 5:  # Board edit
                            pass  # Not implemented yet
                        elif mi == 6:  # Tools - time control
                            if ii < len(TIME_PRESETS) and not game_started:
                                time_preset_idx = ii
                                _, mt, byo = TIME_PRESETS[ii]
                                net.time_control = (mt, byo)
                        elif mi == 7:  # Help
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

        draw_clock_panel(screen, font, small_font, clock_font, clock_name_font,
                         layout, "left",
                         black_name, disp_black_main, disp_black_byo,
                         disp_black_byo_rem, current_player == 1 and game_started,
                         my_color == 1)
        draw_clock_panel(screen, font, small_font, clock_font, clock_name_font,
                         layout, "right",
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
