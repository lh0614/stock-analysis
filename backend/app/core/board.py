"""A-share board classification helpers."""
from __future__ import annotations

BOARD_MAIN = "main"
BOARD_CHINEXT = "chinext"
BOARD_STAR = "star"
BOARD_BSE = "bse"


def classify_board(symbol: str) -> str:
    code = str(symbol).strip().zfill(6)
    if code.startswith("688"):
        return BOARD_STAR
    if code.startswith("300"):
        return BOARD_CHINEXT
    if is_bse_code(code):
        return BOARD_BSE
    return BOARD_MAIN


def is_bse_code(code: str) -> bool:
    if code.startswith("920"):
        return True
    if code.startswith("43"):
        return True
    if len(code) == 6 and code[0] == "8":
        return True
    return False


def is_st_stock(symbol: str, name: str = "") -> bool:
    n = (name or "").upper()
    if "ST" in n or "退" in name:
        return True
    return False


def is_main_board(symbol: str) -> bool:
    return classify_board(symbol) == BOARD_MAIN
