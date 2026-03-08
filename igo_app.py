#!/usr/bin/env python3
import pygame
import pygame.gfxdraw
import sys
import math
import copy

pygame.init()

BOARD_SIZE = 19
INFO_BAR_HEIGHT = 40
BUTTON_BAR_HEIGHT = 46
STAR_POINTS = [
    (3, 3), (3, 9), (3, 15),
    (9, 3), (9, 9), (9, 15),
    (15, 3), (15, 9), (15, 15),
]
INIT_BOARD_PX = 620
INIT_W = INIT_BOARD_PX
INIT_H = INIT_BOARD_PX + INFO_BAR_HEIGHT + BUTTON_BAR_HEIGHT
BG_DARK = (44, 44, 44)
WHITE = (255, 255, 255)
LINE_COLOR = (26, 26, 26)
BUTTON_COLOR = (68, 68, 68)
BUTTON_HOVER = (100, 100, 100)
COLORKEY = (255, 0, 255)

def _clamp(v):
    return max(0, min(255, int(v)))

# --------------- Go rules engine ---------------

def _neighbors(r, c):
    """Return valid neighboring positions on the board."""
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE:
            yield nr, nc

def _get_group(board, r, c):
    """Flood-fill to find all stones connected to (r,c) of the same color.
    Returns (group_set, liberties_count)."""
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

def _remove_group(board, group):
    """Remove all stones in a group from the board. Returns count removed."""
    for r, c in group:
        board[r][c] = 0
    return len(group)

def _board_hash(board):
    """Create a hashable representation of the board state."""
    return tuple(tuple(row) for row in board)

def try_place_stone(board, row, col, player, ko_point):
    """Try to place a stone. Returns (success, captured_list, new_ko_point)
    or (False, None, None) if the move is illegal.
    captured_list is a list of (row, col, color) tuples for undo support.
    new_ko_point is the point forbidden on the next move (or None)."""
    if board[row][col] != 0:
        return False, None, None

    # Ko check: cannot play at the ko point
    if ko_point is not None and (row, col) == ko_point:
        return False, None, None

    opponent = 2 if player == 1 else 1

    # Place the stone tentatively
    board[row][col] = player
    captured = []

    # Check all neighboring opponent groups for capture
    for nr, nc in _neighbors(row, col):
        if board[nr][nc] == opponent:
            group, liberties = _get_group(board, nr, nc)
            if liberties == 0:
                for gr, gc in group:
                    captured.append((gr, gc, opponent))
                _remove_group(board, group)

    # Check if the placed stone's own group has liberties (suicide check)
    own_group, own_liberties = _get_group(board, row, col)
    if own_liberties == 0:
        # Suicide: revert everything
        board[row][col] = 0
        for gr, gc, color in captured:
            board[gr][gc] = color
        return False, None, None

    # Determine new ko point: if exactly 1 stone captured and the placed
    # stone's group is size 1 with exactly 1 liberty (the captured point),
    # then the captured point becomes the ko point.
    new_ko = None
    if len(captured) == 1:
        cap_r, cap_c, _ = captured[0]
        own_group2, own_lib2 = _get_group(board, row, col)
        if len(own_group2) == 1 and own_lib2 == 1:
            new_ko = (cap_r, cap_c)

    return True, captured, new_ko

# --------------- end rules engine ---------------

_SS = 3  # supersampling factor for antialiased stones

def create_stone_surface(color, diameter):
    """Create glossy 3D stone with smooth antialiased edges.
    Renders at _SS× resolution then downscales with smoothscale."""
    if diameter < 4:
        diameter = 4
    # Work at _SS× resolution for antialiasing
    big_diam = diameter * _SS
    big_size = big_diam + 2 * _SS
    big_r = big_diam // 2
    bcx, bcy = big_size // 2, big_size // 2
    # Use per-pixel alpha surface (transparent background)
    big = pygame.Surface((big_size, big_size), pygame.SRCALPHA)
    # Draw filled base circle
    base_col = (20, 20, 20, 255) if color == "black" else (210, 210, 210, 255)
    pygame.gfxdraw.filled_circle(big, bcx, bcy, big_r, base_col)
    # Draw gradient with concentric circles for 3D glossy effect
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
    # Draw specular highlight
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
    # Downscale with smoothscale for antialiased edges
    final_size = diameter + 2
    small = pygame.transform.smoothscale(big, (final_size, final_size))
    return small

class Layout:
    def __init__(self, win_w, win_h):
        board_area = min(win_w, win_h - INFO_BAR_HEIGHT - BUTTON_BAR_HEIGHT)
        board_area = max(board_area, 100)
        self.margin = max(6, int(board_area * 0.03))
        self.cell_size = (board_area - self.margin * 2) / (BOARD_SIZE - 1)
        self.stone_diam = max(4, round(self.cell_size) + 1)
        self.board_px = int(self.margin * 2 + self.cell_size * (BOARD_SIZE - 1))
        self.star_radius = max(2, int(self.cell_size * 0.1))
        self.win_w = win_w
        self.win_h = win_h
        self.offset_x = (win_w - self.board_px) // 2
        self.offset_y = INFO_BAR_HEIGHT
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

def draw_info_bar(screen, current_player, font, win_w):
    pygame.draw.rect(screen, BG_DARK, (0, 0, win_w, INFO_BAR_HEIGHT))
    if current_player == 1:
        text = font.render("黒の番です", True, WHITE)
        cxp = win_w // 2 - text.get_width() // 2 - 18
        cyp = INFO_BAR_HEIGHT // 2
        pygame.draw.circle(screen, (30, 30, 30), (cxp, cyp), 8)
        pygame.draw.circle(screen, (80, 80, 80), (cxp - 2, cyp - 2), 3)
    else:
        text = font.render("白の番です", True, WHITE)
        cxp = win_w // 2 - text.get_width() // 2 - 18
        cyp = INFO_BAR_HEIGHT // 2
        pygame.draw.circle(screen, (230, 230, 230), (cxp, cyp), 8)
        pygame.draw.circle(screen, (255, 255, 255), (cxp - 2, cyp - 2), 3)
    text_rect = text.get_rect(center=(win_w // 2, INFO_BAR_HEIGHT // 2))
    screen.blit(text, text_rect)

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

def make_buttons(layout, btn_font):
    btn_y = layout.win_h - BUTTON_BAR_HEIGHT + 6
    w = layout.win_w
    return [
        Button((15, btn_y, 100, 34), "一手戻す", btn_font),
        Button((w // 2 - 45, btn_y, 90, 34), "パス", btn_font),
        Button((w - 115, btn_y, 100, 34), "リセット", btn_font),
    ]

def main():
    screen = pygame.display.set_mode((INIT_W, INIT_H), pygame.RESIZABLE)
    pygame.display.set_caption("囲碁 - Go Game")
    font = None
    btn_font = None
    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/usr/share/fonts/truetype/takao-gothic/TakaoPGothic.ttf",
    ]
    for fp in font_paths:
        try:
            font = pygame.font.Font(fp, 18)
            btn_font = pygame.font.Font(fp, 15)
            break
        except Exception:
            continue
    if font is None:
        font = pygame.font.SysFont("notosanscjk,notosansjp,notosans,sans", 18)
        btn_font = pygame.font.SysFont("notosanscjk,notosansjp,notosans,sans", 15)
    layout = Layout(INIT_W, INIT_H)
    print("Generating stones...")
    black_stone = create_stone_surface("black", layout.stone_diam)
    white_stone = create_stone_surface("white", layout.stone_diam)
    cached_diam = layout.stone_diam
    print("Done")
    board = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
    current_player = 1
    move_history = []  # list of (row, col, captured_list, old_ko_point)
    ko_point = None  # point forbidden by ko rule
    captured_black = 0  # white's prisoners
    captured_white = 0  # black's prisoners
    buttons = make_buttons(layout, btn_font)
    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                nw = max(300, event.w)
                nh = max(300, event.h)
                screen = pygame.display.set_mode((nw, nh), pygame.RESIZABLE)
                layout = Layout(nw, nh)
                buttons = make_buttons(layout, btn_font)
                if layout.stone_diam != cached_diam:
                    black_stone = create_stone_surface("black", layout.stone_diam)
                    white_stone = create_stone_surface("white", layout.stone_diam)
                    cached_diam = layout.stone_diam
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                clicked_btn = False
                for i, btn in enumerate(buttons):
                    if btn.is_clicked((mx, my)):
                        clicked_btn = True
                        if i == 0:
                            if move_history:
                                r, c, cap_list, old_ko = move_history.pop()
                                board[r][c] = 0
                                # Restore captured stones
                                for gr, gc, color in cap_list:
                                    board[gr][gc] = color
                                    if color == 1:
                                        captured_black -= 1
                                    else:
                                        captured_white -= 1
                                ko_point = old_ko
                                current_player = 2 if current_player == 1 else 1
                        elif i == 1:
                            ko_point = None  # pass clears ko
                            current_player = 2 if current_player == 1 else 1
                        elif i == 2:
                            board = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
                            current_player = 1
                            move_history.clear()
                            ko_point = None
                            captured_black = 0
                            captured_white = 0
                        break
                if not clicked_btn:
                    row, col = layout.screen_to_grid(mx, my)
                    if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
                        old_ko = ko_point
                        ok, cap_list, new_ko = try_place_stone(
                            board, row, col, current_player, ko_point
                        )
                        if ok:
                            move_history.append((row, col, cap_list, old_ko))
                            ko_point = new_ko
                            for _, _, color in cap_list:
                                if color == 1:
                                    captured_black += 1
                                else:
                                    captured_white += 1
                            current_player = 2 if current_player == 1 else 1
            elif event.type == pygame.MOUSEMOTION:
                for btn in buttons:
                    btn.update_hover(event.pos)
        screen.fill(BG_DARK)
        draw_wood_background(screen, layout)
        draw_info_bar(screen, current_player, font, layout.win_w)
        draw_board(screen, board, black_stone, white_stone, layout)
        pygame.draw.rect(screen, BG_DARK, (0, layout.win_h - BUTTON_BAR_HEIGHT, layout.win_w, BUTTON_BAR_HEIGHT))
        for btn in buttons:
            btn.draw(screen)
        pygame.display.flip()
        clock.tick(30)
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
