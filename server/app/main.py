from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uuid
import os
import time as time_module
import asyncio
import sqlite3
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

# Fly.io instance identification
FLY_ALLOC_ID = os.environ.get("FLY_ALLOC_ID", "local")

# --------------- SQLite Database ---------------

# Use /data/app.db for persistent volume on Fly.io, fallback to local
HAS_VOLUME = os.path.isdir("/data")
DB_PATH = "/data/app.db" if HAS_VOLUME else "app.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            nickname TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            skill_level TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Add skill_level column if it doesn't exist (migration for existing DB)
    try:
        conn.execute("ALTER TABLE users ADD COLUMN skill_level TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.commit()
    conn.close()


@app.on_event("startup")
async def startup_event():
    init_db()


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
async def register(req: RegisterRequest, request: Request):
    """Register a new user."""
    # If this machine has no volume, replay to the one that does
    if not HAS_VOLUME and FLY_ALLOC_ID != "local":
        return JSONResponse(content={"status": "replaying"}, headers={"fly-replay": "elsewhere=true"})
    name = req.name.strip()
    nickname = req.nickname.strip()
    password = req.password

    if not name:
        return JSONResponse(status_code=400, content={"ok": False, "error": "\u540d\u524d\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044"})
    if not nickname:
        return JSONResponse(status_code=400, content={"ok": False, "error": "\u30cb\u30c3\u30af\u30cd\u30fc\u30e0\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044"})
    if len(nickname) < 2:
        return JSONResponse(status_code=400, content={"ok": False, "error": "\u30cb\u30c3\u30af\u30cd\u30fc\u30e0\u306f2\u6587\u5b57\u4ee5\u4e0a\u3067\u3059"})
    if not password or len(password) < 4:
        return JSONResponse(status_code=400, content={"ok": False, "error": "\u30d1\u30b9\u30ef\u30fc\u30c9\u306f4\u6587\u5b57\u4ee5\u4e0a\u3067\u3059"})

    skill_level = req.skill_level.strip()

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, nickname, password_hash, skill_level) VALUES (?, ?, ?, ?)",
            (name, nickname, password_hash, skill_level),
        )
        conn.commit()
        return {"ok": True, "nickname": nickname, "name": name, "skill_level": skill_level}
    except sqlite3.IntegrityError:
        return JSONResponse(status_code=409, content={"ok": False, "error": "\u305d\u306e\u30cb\u30c3\u30af\u30cd\u30fc\u30e0\u306f\u65e2\u306b\u4f7f\u308f\u308c\u3066\u3044\u307e\u3059"})
    finally:
        conn.close()


@app.post("/login")
async def login(req: LoginRequest, request: Request):
    """Login with nickname and password."""
    # If this machine has no volume, replay to the one that does
    if not HAS_VOLUME and FLY_ALLOC_ID != "local":
        return JSONResponse(content={"status": "replaying"}, headers={"fly-replay": "elsewhere=true"})
    nickname = req.nickname.strip()
    password = req.password

    if not nickname or not password:
        return JSONResponse(status_code=400, content={"ok": False, "error": "\u30cb\u30c3\u30af\u30cd\u30fc\u30e0\u3068\u30d1\u30b9\u30ef\u30fc\u30c9\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044"})

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, nickname, password_hash, skill_level FROM users WHERE nickname = ?",
            (nickname,),
        ).fetchone()
        if row is None:
            return JSONResponse(status_code=401, content={"ok": False, "error": "\u30cb\u30c3\u30af\u30cd\u30fc\u30e0\u304c\u898b\u3064\u304b\u308a\u307e\u305b\u3093"})
        if not bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
            return JSONResponse(status_code=401, content={"ok": False, "error": "\u30d1\u30b9\u30ef\u30fc\u30c9\u304c\u9055\u3044\u307e\u3059"})
        return {"ok": True, "nickname": row["nickname"], "name": row["name"], "skill_level": row["skill_level"]}
    finally:
        conn.close()


@app.get("/admin/users")
async def admin_users(request: Request):
    """List all registered users (for admin panel)."""
    if not HAS_VOLUME and FLY_ALLOC_ID != "local":
        return JSONResponse(content={"status": "replaying"}, headers={"fly-replay": "elsewhere=true"})
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, name, nickname, skill_level, created_at FROM users ORDER BY id"
        ).fetchall()
        users = [
            {
                "id": r["id"],
                "name": r["name"],
                "nickname": r["nickname"],
                "skill_level": r["skill_level"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
        return {"ok": True, "users": users}
    finally:
        conn.close()


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
waiting_room: Optional[str] = None


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


@app.post("/find_match")
async def find_match(request: Request, name: str = "",
                     main_time: int = 60, byoyomi: int = 30):
    """Find or create a match room."""
    global waiting_room

    if waiting_room and waiting_room in rooms and not rooms[waiting_room].is_full():
        wr = rooms[waiting_room]
        return JSONResponse(content={
            "room_code": waiting_room,
            "instance_id": FLY_ALLOC_ID,
            "status": "joining",
            "main_time": wr.main_time,
            "byoyomi": wr.byoyomi,
        })

    replay_src = request.headers.get("fly-replay-src", "")
    if FLY_ALLOC_ID != "local" and not replay_src:
        return JSONResponse(
            content={"status": "checking_other_instances"},
            headers={"fly-replay": "elsewhere=true"},
        )

    room_code = str(uuid.uuid4())[:8]
    room = Room(room_code, main_time=main_time, byoyomi=byoyomi)
    rooms[room_code] = room
    waiting_room = room_code

    return JSONResponse(content={
        "room_code": room_code,
        "instance_id": FLY_ALLOC_ID,
        "status": "created",
        "main_time": main_time,
        "byoyomi": byoyomi,
    })


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


# --------------- WebSocket ---------------

@app.websocket("/ws/{room_code}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, room_code: str, player_name: str):
    global waiting_room
    await websocket.accept()

    if room_code not in rooms:
        room = Room(room_code)
        rooms[room_code] = room
        waiting_room = room_code

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
        if waiting_room == room_code:
            waiting_room = None
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
            "message": "\u5bfe\u6226\u76f8\u624b\u3092\u5f85\u3063\u3066\u3044\u307e\u3059...",
        })

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "place_stone":
                row, col = data["row"], data["col"]
                if player.color != room.current_player:
                    await player.ws.send_json({"type": "error", "message": "\u76f8\u624b\u306e\u756a\u3067\u3059"})
                    continue
                if not room.started or room.game_over:
                    await player.ws.send_json({"type": "error", "message": "\u5bfe\u6226\u76f8\u624b\u3092\u5f85\u3063\u3066\u3044\u307e\u3059"})
                    continue

                ok, captured, new_ko = try_place_stone(
                    room.board, row, col, player.color, room.ko_point
                )
                if not ok:
                    await player.ws.send_json({"type": "error", "message": "\u305d\u3053\u306b\u306f\u7f6e\u3051\u307e\u305b\u3093"})
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
                    "message": f"{player.name}\u304c\u5207\u65ad\u3057\u307e\u3057\u305f",
                })
            except Exception:
                pass
        room.players = [p for p in room.players if p is not player]
        if len(room.players) == 0:
            rooms.pop(room.room_id, None)
            if waiting_room == room.room_id:
                waiting_room = None
    except Exception:
        pass
