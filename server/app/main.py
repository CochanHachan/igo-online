from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uuid
import os
import time as time_module
import asyncio
import bcrypt
from typing import Optional

app = FastAPI()

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------- Database ---------------
# Use PostgreSQL if DATABASE_URL is set, otherwise fallback to SQLite

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL:
    import psycopg
    import psycopg.rows
    import psycopg.errors

    def get_db():
        conn = psycopg.connect(DATABASE_URL, row_factory=psycopg.rows.dict_row)
        return conn

    _PH = "%s"
    _SERIAL = "SERIAL"
    _INTEGRITY_ERROR = psycopg.errors.UniqueViolation
else:
    import sqlite3

    _db_dir = "/data" if os.path.isdir("/data") else "."
    _DB_PATH = os.path.join(_db_dir, "app.db")

    def get_db():
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    _PH = "?"
    _SERIAL = "INTEGER"
    _INTEGRITY_ERROR = sqlite3.IntegrityError


def init_db():
    conn = get_db()
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS users (
            id {_SERIAL} PRIMARY KEY,
            name TEXT NOT NULL,
            nickname TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            skill_level TEXT NOT NULL DEFAULT '',
            rating INTEGER NOT NULL DEFAULT 1500,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migration: add columns if they don't exist
    if DATABASE_URL:
        for col, defn in [("skill_level", "TEXT NOT NULL DEFAULT ''"),
                          ("rating", "INTEGER NOT NULL DEFAULT 1500")]:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
            except Exception:
                pass
    else:
        for col, defn in [("skill_level", "TEXT NOT NULL DEFAULT ''"),
                          ("rating", "INTEGER NOT NULL DEFAULT 1500")]:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
            except Exception:
                pass
    conn.commit()
    conn.close()


@app.on_event("startup")
async def startup_event():
    init_db()


# --------------- Skill Level Utilities ---------------

SKILL_LEVELS = [
    "10級", "9級", "8級", "7級", "6級",
    "5級", "4級", "3級", "2級", "1級",
    "初段", "2段", "3段", "4段", "5段",
    "6段", "7段", "8段", "9段",
]


def skill_to_num(s: str) -> int:
    """Convert skill level string to numeric index for comparison."""
    try:
        return SKILL_LEVELS.index(s)
    except ValueError:
        return 10


def skill_distance(a: str, b: str) -> int:
    """Return the distance between two skill levels."""
    return abs(skill_to_num(a) - skill_to_num(b))


# --------------- Auth Models ---------------

class RegisterRequest(BaseModel):
    name: str
    nickname: str
    password: str
    skill_level: str = ""


class LoginRequest(BaseModel):
    nickname: str
    password: str


# --------------- Auth Endpoints ---------------

@app.post("/register")
async def register(req: RegisterRequest):
    """Register a new user."""
    name = req.name.strip()
    nickname = req.nickname.strip()
    password = req.password

    if not name:
        return JSONResponse(status_code=400,
                            content={"ok": False, "error": "名前を入力してください"})
    if not nickname:
        return JSONResponse(status_code=400,
                            content={"ok": False, "error": "ニックネームを入力してください"})
    if len(nickname) < 2:
        return JSONResponse(status_code=400,
                            content={"ok": False, "error": "ニックネームは2文字以上です"})
    if not password or len(password) < 4:
        return JSONResponse(status_code=400,
                            content={"ok": False, "error": "パスワードは4文字以上です"})

    skill_level = req.skill_level.strip()
    if skill_level and skill_level not in SKILL_LEVELS:
        return JSONResponse(status_code=400,
                            content={"ok": False, "error": "無効な棋力です"})

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    conn = get_db()
    try:
        conn.execute(
            f"INSERT INTO users (name, nickname, password_hash, skill_level) VALUES ({_PH}, {_PH}, {_PH}, {_PH})",
            (name, nickname, password_hash, skill_level),
        )
        conn.commit()
        return {"ok": True, "nickname": nickname, "name": name, "skill_level": skill_level}
    except _INTEGRITY_ERROR:
        if DATABASE_URL:
            conn.rollback()
        return JSONResponse(status_code=409,
                            content={"ok": False, "error": "そのニックネームは既に使われています"})
    finally:
        conn.close()


@app.post("/login")
async def login(req: LoginRequest):
    """Login with nickname and password."""
    nickname = req.nickname.strip()
    password = req.password

    if not nickname or not password:
        return JSONResponse(status_code=400,
                            content={"ok": False, "error": "ニックネームとパスワードを入力してください"})

    conn = get_db()
    try:
        row = conn.execute(
            f"SELECT name, nickname, password_hash, skill_level FROM users WHERE nickname = {_PH}",
            (nickname,),
        ).fetchone()
        if row is None:
            return JSONResponse(status_code=401,
                                content={"ok": False, "error": "ニックネームが見つかりません"})
        if not bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
            return JSONResponse(status_code=401,
                                content={"ok": False, "error": "パスワードが違います"})
        return {"ok": True, "nickname": row["nickname"], "name": row["name"],
                "skill_level": row["skill_level"]}
    finally:
        conn.close()


@app.get("/admin/users")
async def admin_users():
    """List all registered users (for admin panel)."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, name, nickname, skill_level, rating, created_at FROM users ORDER BY id"
        ).fetchall()
        users = [
            {
                "id": r["id"],
                "name": r["name"],
                "nickname": r["nickname"],
                "skill_level": r["skill_level"],
                "rating": r["rating"],
                "created_at": str(r["created_at"]) if r["created_at"] else "",
            }
            for r in rows
        ]
        return {"ok": True, "users": users}
    finally:
        conn.close()


@app.get("/skill_levels")
async def get_skill_levels():
    """Return the list of valid skill levels."""
    return {"skill_levels": SKILL_LEVELS}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


# --------------- Game Room Management ---------------

class Player:
    def __init__(self, ws: WebSocket, name: str):
        self.ws = ws
        self.name = name
        self.color: Optional[int] = None  # 1=black, 2=white


class Room:
    def __init__(self, room_id: str, main_time: int = 60, byoyomi: int = 30):
        self.room_id = room_id
        self.players: list[Player] = []
        self.board = [[0] * 19 for _ in range(19)]
        self.current_player = 1
        self.ko_point: Optional[tuple[int, int]] = None
        self.move_history: list[dict] = []
        self.started = False
        # Time control
        self.main_time = main_time
        self.byoyomi = byoyomi
        self.player_times = {1: float(main_time), 2: float(main_time)}
        self.player_in_byoyomi = {1: False, 2: False}
        self.player_byoyomi_remaining = {1: float(byoyomi), 2: float(byoyomi)}
        self.turn_start_time: Optional[float] = None
        self.game_over = False
        self.time_task: Optional[asyncio.Task] = None

    def is_full(self):
        return len(self.players) >= 2

    def get_opponent(self, player: Player) -> Optional[Player]:
        for p in self.players:
            if p is not player:
                return p
        return None

    def get_current_times(self) -> dict:
        result = {}
        for color in (1, 2):
            main_t = self.player_times[color]
            in_byo = self.player_in_byoyomi[color]
            byo_rem = self.player_byoyomi_remaining[color]
            if (color == self.current_player and self.turn_start_time
                    and self.started and not self.game_over):
                elapsed = time_module.time() - self.turn_start_time
                if not in_byo:
                    main_t -= elapsed
                    if main_t <= 0:
                        in_byo = True
                        byo_rem = self.byoyomi + main_t
                        main_t = 0
                else:
                    byo_rem -= elapsed
            key = "black" if color == 1 else "white"
            result[f"{key}_main_time"] = round(max(0.0, main_t), 1)
            result[f"{key}_in_byoyomi"] = in_byo
            result[f"{key}_byoyomi_remaining"] = round(max(0.0, byo_rem), 1)
        return result

    def consume_time(self) -> bool:
        if not self.turn_start_time:
            return True
        elapsed = time_module.time() - self.turn_start_time
        cp = self.current_player
        if not self.player_in_byoyomi[cp]:
            self.player_times[cp] -= elapsed
            if self.player_times[cp] <= 0:
                overflow = -self.player_times[cp]
                self.player_times[cp] = 0.0
                self.player_in_byoyomi[cp] = True
                if overflow > self.byoyomi:
                    return False
                self.player_byoyomi_remaining[cp] = float(self.byoyomi)
        else:
            self.player_byoyomi_remaining[cp] -= elapsed
            if self.player_byoyomi_remaining[cp] <= 0:
                return False
            self.player_byoyomi_remaining[cp] = float(self.byoyomi)
        return True

    def start_clock(self):
        self.turn_start_time = time_module.time()


rooms: dict[str, Room] = {}


# --------------- Go Rules (server-side) ---------------

def _neighbors(r: int, c: int):
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < 19 and 0 <= nc < 19:
            yield nr, nc


def _get_group(board: list[list[int]], r: int, c: int):
    color = board[r][c]
    if color == 0:
        return set(), 0
    visited: set[tuple[int, int]] = set()
    stack = [(r, c)]
    liberties: set[tuple[int, int]] = set()
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


def _remove_group(board: list[list[int]], group: set[tuple[int, int]]):
    for r, c in group:
        board[r][c] = 0
    return len(group)


def try_place_stone(board: list[list[int]], row: int, col: int,
                    player: int, ko_point):
    if board[row][col] != 0:
        return False, [], None
    if ko_point is not None and (row, col) == ko_point:
        return False, [], None
    opponent = 2 if player == 1 else 1
    board[row][col] = player
    captured = []
    for nr, nc in _neighbors(row, col):
        if board[nr][nc] == opponent:
            group, liberties = _get_group(board, nr, nc)
            if liberties == 0:
                for gr, gc in group:
                    captured.append((gr, gc, opponent))
                _remove_group(board, group)
    own_group, own_liberties = _get_group(board, row, col)
    if own_liberties == 0:
        board[row][col] = 0
        for gr, gc, clr in captured:
            board[gr][gc] = clr
        return False, [], None
    new_ko = None
    if len(captured) == 1:
        cap_r, cap_c, _ = captured[0]
        own_group2, own_lib2 = _get_group(board, row, col)
        if len(own_group2) == 1 and own_lib2 == 1:
            new_ko = (cap_r, cap_c)
    return True, captured, new_ko


# --------------- Lobby (Match Request System) ---------------

class LobbyUser:
    def __init__(self, ws: WebSocket, nickname: str, name: str, skill_level: str):
        self.ws = ws
        self.nickname = nickname
        self.name = name
        self.skill_level = skill_level
        self.looking = False
        self.main_time = 60
        self.byoyomi = 30
        self.pending_from: Optional[str] = None
        self.waiting_for: Optional[str] = None
        self.declined_set: set[str] = set()
        self.join_time = 0.0


lobby_users: dict[str, LobbyUser] = {}


async def broadcast_lobby_status():
    """Send lobby status to all connected lobby users."""
    count = len(lobby_users)
    looking = sum(1 for u in lobby_users.values() if u.looking)
    msg = {"type": "lobby_status", "online_count": count, "looking_count": looking}
    for user in list(lobby_users.values()):
        try:
            await user.ws.send_json(msg)
        except Exception:
            pass


async def try_match(user: LobbyUser):
    """Try to find a match for the given user."""
    best: Optional[LobbyUser] = None
    best_dist = float("inf")

    for nick, other in lobby_users.items():
        if nick == user.nickname:
            continue
        if not other.looking:
            continue
        if other.pending_from is not None:
            continue
        if other.waiting_for is not None:
            continue
        if nick in user.declined_set or user.nickname in other.declined_set:
            continue

        dist = skill_distance(user.skill_level, other.skill_level)
        if dist < best_dist:
            best = other
            best_dist = dist

    if best is not None:
        best.pending_from = user.nickname
        user.waiting_for = best.nickname
        try:
            await best.ws.send_json({
                "type": "match_request",
                "from_nickname": user.nickname,
                "from_name": user.name,
                "from_skill": user.skill_level,
                "main_time": user.main_time,
                "byoyomi": user.byoyomi,
            })
        except Exception:
            best.pending_from = None
            user.waiting_for = None
            return
        try:
            await user.ws.send_json({
                "type": "match_sent",
                "to_nickname": best.nickname,
                "to_name": best.name,
                "to_skill": best.skill_level,
            })
        except Exception:
            pass
    else:
        try:
            await user.ws.send_json({
                "type": "waiting",
                "message": "対戦相手を探しています...",
            })
        except Exception:
            pass


@app.websocket("/ws/lobby/{nickname}")
async def lobby_websocket(websocket: WebSocket, nickname: str):
    """Lobby WebSocket for match request system."""
    await websocket.accept()

    conn = get_db()
    try:
        row = conn.execute(
            f"SELECT name, skill_level FROM users WHERE nickname = {_PH}",
            (nickname,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        await websocket.send_json({"type": "error",
                                   "message": "ユーザーが見つかりません"})
        await websocket.close()
        return

    user = LobbyUser(websocket, nickname, row["name"], row["skill_level"])
    user.join_time = time_module.time()
    lobby_users[nickname] = user

    await broadcast_lobby_status()

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "request_match":
                user.looking = True
                user.main_time = data.get("main_time", 60)
                user.byoyomi = data.get("byoyomi", 30)
                user.declined_set.clear()
                await broadcast_lobby_status()
                await try_match(user)

            elif msg_type == "cancel_request":
                if user.waiting_for and user.waiting_for in lobby_users:
                    other = lobby_users[user.waiting_for]
                    if other.pending_from == user.nickname:
                        other.pending_from = None
                        try:
                            await other.ws.send_json({"type": "match_cancelled"})
                        except Exception:
                            pass
                user.looking = False
                user.waiting_for = None
                user.pending_from = None
                await broadcast_lobby_status()

            elif msg_type == "accept_match":
                requester_nick = user.pending_from
                if requester_nick and requester_nick in lobby_users:
                    requester = lobby_users[requester_nick]
                    room_code = str(uuid.uuid4())[:8]
                    room = Room(room_code, main_time=requester.main_time,
                                byoyomi=requester.byoyomi)
                    rooms[room_code] = room

                    for target, opponent in [(requester, user), (user, requester)]:
                        try:
                            await target.ws.send_json({
                                "type": "match_accepted",
                                "room_code": room_code,
                                "opponent_name": opponent.name,
                                "opponent_nickname": opponent.nickname,
                                "opponent_skill": opponent.skill_level,
                                "main_time": requester.main_time,
                                "byoyomi": requester.byoyomi,
                            })
                        except Exception:
                            pass

                    requester.looking = False
                    requester.waiting_for = None
                    user.looking = False
                    user.pending_from = None
                    await broadcast_lobby_status()

            elif msg_type == "decline_match":
                requester_nick = user.pending_from
                user.pending_from = None
                if requester_nick and requester_nick in lobby_users:
                    requester = lobby_users[requester_nick]
                    requester.waiting_for = None
                    requester.declined_set.add(user.nickname)
                    user.declined_set.add(requester_nick)
                    try:
                        await requester.ws.send_json({"type": "match_declined",
                                                      "by": user.nickname})
                    except Exception:
                        pass
                    if requester.looking:
                        await try_match(requester)

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if user.waiting_for and user.waiting_for in lobby_users:
            other = lobby_users[user.waiting_for]
            if other.pending_from == user.nickname:
                other.pending_from = None
                try:
                    await other.ws.send_json({"type": "match_cancelled"})
                except Exception:
                    pass
        if user.pending_from and user.pending_from in lobby_users:
            other = lobby_users[user.pending_from]
            other.waiting_for = None
            if other.looking:
                try:
                    await try_match(other)
                except Exception:
                    pass
        if lobby_users.get(nickname) is user:
            lobby_users.pop(nickname, None)
        await broadcast_lobby_status()


# --------------- REST ---------------

@app.get("/rooms")
async def list_rooms():
    room_list = []
    for rid, room in rooms.items():
        room_list.append({
            "room_id": rid,
            "players": len(room.players),
            "started": room.started,
        })
    return {"rooms": room_list}


# --------------- Time checker background task ---------------

async def time_checker(room: Room):
    try:
        while room.started and not room.game_over and len(room.players) == 2:
            await asyncio.sleep(0.5)
            if not room.started or room.game_over:
                break
            times = room.get_current_times()
            cp = room.current_player
            key = "black" if cp == 1 else "white"
            if times[f"{key}_in_byoyomi"] and times[f"{key}_byoyomi_remaining"] <= 0:
                room.game_over = True
                winner = 2 if cp == 1 else 1
                for p in room.players:
                    try:
                        await p.ws.send_json({
                            "type": "time_loss", "loser": cp,
                            "winner": winner, **times,
                        })
                    except Exception:
                        pass
                break
            for p in room.players:
                try:
                    await p.ws.send_json({"type": "time_sync", **times})
                except Exception:
                    pass
    except asyncio.CancelledError:
        pass
    except Exception:
        pass


# --------------- Game WebSocket ---------------

@app.websocket("/ws/{room_code}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, room_code: str, player_name: str):
    await websocket.accept()

    if room_code not in rooms:
        room = Room(room_code)
        rooms[room_code] = room

    room = rooms[room_code]
    player = Player(websocket, player_name)

    if room.is_full():
        await websocket.send_json({"type": "error", "message": "Room is full"})
        await websocket.close()
        return

    room.players.append(player)

    if len(room.players) == 1:
        player.color = 1
    else:
        player.color = 2
        room.started = True

    await player.ws.send_json({
        "type": "assigned",
        "color": player.color,
        "room_id": room.room_id,
        "your_name": player.name,
    })

    if room.started:
        room.start_clock()
        times = room.get_current_times()
        for p in room.players:
            opponent = room.get_opponent(p)
            await p.ws.send_json({
                "type": "game_start",
                "your_color": p.color,
                "opponent_name": opponent.name if opponent else "",
                "current_player": room.current_player,
                "main_time": room.main_time,
                "byoyomi": room.byoyomi,
                **times,
            })
        room.time_task = asyncio.create_task(time_checker(room))
    else:
        await player.ws.send_json({
            "type": "waiting",
            "message": "対戦相手を待っています...",
        })

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "place_stone":
                row, col = data["row"], data["col"]
                if player.color != room.current_player:
                    await player.ws.send_json({"type": "error", "message": "相手の番です"})
                    continue
                if not room.started or room.game_over:
                    await player.ws.send_json({"type": "error", "message": "対戦相手を待っています"})
                    continue

                ok, captured, new_ko = try_place_stone(
                    room.board, row, col, player.color, room.ko_point
                )
                if not ok:
                    await player.ws.send_json({"type": "error", "message": "そこには置けません"})
                    continue

                time_ok = room.consume_time()
                if not time_ok:
                    room.board[row][col] = 0
                    for gr, gc, clr in captured:
                        room.board[gr][gc] = clr
                    room.game_over = True
                    winner = 2 if player.color == 1 else 1
                    times = room.get_current_times()
                    if room.time_task:
                        room.time_task.cancel()
                    for p in room.players:
                        await p.ws.send_json({
                            "type": "time_loss", "loser": player.color,
                            "winner": winner, **times,
                        })
                    continue

                room.ko_point = new_ko
                room.move_history.append({
                    "row": row, "col": col, "color": player.color,
                    "captured": [(r, c, clr) for r, c, clr in captured],
                })
                room.current_player = 2 if room.current_player == 1 else 1
                room.start_clock()

                times = room.get_current_times()
                move_msg = {
                    "type": "move", "row": row, "col": col, "color": player.color,
                    "captured": [[r, c, clr] for r, c, clr in captured],
                    "current_player": room.current_player,
                    "ko_point": list(room.ko_point) if room.ko_point else None,
                    **times,
                }
                for p in room.players:
                    await p.ws.send_json(move_msg)

            elif msg_type == "pass":
                if player.color != room.current_player or room.game_over:
                    continue
                time_ok = room.consume_time()
                if not time_ok:
                    room.game_over = True
                    winner = 2 if player.color == 1 else 1
                    times = room.get_current_times()
                    if room.time_task:
                        room.time_task.cancel()
                    for p in room.players:
                        await p.ws.send_json({
                            "type": "time_loss", "loser": player.color,
                            "winner": winner, **times,
                        })
                    continue
                room.ko_point = None
                room.current_player = 2 if room.current_player == 1 else 1
                room.start_clock()
                times = room.get_current_times()
                for p in room.players:
                    await p.ws.send_json({
                        "type": "pass", "color": player.color,
                        "current_player": room.current_player,
                        **times,
                    })

            elif msg_type == "resign":
                room.game_over = True
                if room.time_task:
                    room.time_task.cancel()
                for p in room.players:
                    await p.ws.send_json({
                        "type": "resign", "color": player.color,
                        "winner": 2 if player.color == 1 else 1,
                    })

    except WebSocketDisconnect:
        room.game_over = True
        if room.time_task:
            room.time_task.cancel()
        opponent = room.get_opponent(player)
        if opponent:
            try:
                await opponent.ws.send_json({
                    "type": "opponent_disconnected",
                    "message": f"{player.name}が切断しました",
                })
            except Exception:
                pass
        room.players = [p for p in room.players if p is not player]
        if len(room.players) == 0:
            rooms.pop(room.room_id, None)
    except Exception:
        pass
