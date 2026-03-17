#!/usr/bin/env python3
"""Standalone demo to visually test the promotion celebration screen.

Usage:
    python test_promotion_demo.py [段級]

Examples:
    python test_promotion_demo.py 初段
    python test_promotion_demo.py 2段
    python test_promotion_demo.py 5級

If no argument is given, defaults to "2段".
"""
import sys
import os

import pygame

pygame.init()

# --- Parse command-line argument ---
rank = sys.argv[1] if len(sys.argv) > 1 else "2段"

WIN_W, WIN_H = 800, 600
screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.NOFRAME)
pygame.display.set_caption(f"昇段デモ: {rank}")

# Import the PromotionScreen class from the main app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from igo_app_online import PromotionScreen, BG_DARK

promotion = PromotionScreen(WIN_W, WIN_H)
promotion.show(rank)

clock = pygame.time.Clock()
running = True

print(f"昇段デモ起動: {rank}")
print("クリックでアニメーションをリセット、ウィンドウを閉じると終了します。")

while running:
    dt = clock.get_time() / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            # Reset animation on click
            promotion.show(rank)

    promotion.update(dt)

    # Draw dark background (simulating the game board behind)
    screen.fill(BG_DARK)

    # Draw the promotion screen overlay
    promotion.draw(screen)

    pygame.display.flip()
    clock.tick(30)

pygame.quit()
