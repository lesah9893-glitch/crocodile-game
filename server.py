import asyncio
import os
import random
import re
from difflib import SequenceMatcher
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "docs"


def env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def text_value(data: dict, key: str, max_length: int) -> str:
    value = data.get(key, "")
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=DOCS_DIR), name="static")
app.mount("/img", StaticFiles(directory=DOCS_DIR / "img"), name="img")

@app.get("/")
async def get_index():
    return FileResponse(DOCS_DIR / "index.html")


@app.get("/vk-bridge.min.js", include_in_schema=False)
async def get_vk_bridge():
    return FileResponse(DOCS_DIR / "vk-bridge.min.js", media_type="text/javascript")

WORD_BANK = {
    "Животные": ["крокодил","слон","пингвин","зебра","лев","тигр","медведь","волк","лиса","заяц","белка","ёж","мышь","кот","собака","лошадь","корова","свинья","утка","попугай","орёл","сова","кит","дельфин","акула","медуза","осьминог","черепаха","змея","обезьяна","горилла","панда","гепард","енот"],
    "Спорт": ["футбол","хоккей","баскетбол","волейбол","теннис","бокс","плавание","биатлон","лыжи","сноуборд","скейтборд","шахматы","гольф","бег","прыжок","карате","дзюдо","борьба","гимнастика","велоспорт","серфинг","боулинг","бильярд","фигурное катание"],
    "Еда": ["пицца","бургер","суши","борщ","пельмени","макароны","картошка","мороженое","шоколад","торт","арбуз","банан","яблоко","сыр","колбаса","бутерброд","шаурма","омлет","салат","суп","блины","пончик","хлеб"],
    "Техника": ["компьютер","телефон","ноутбук","телевизор","микрофон","наушники","камера","холодильник","пылесос","утюг","чайник","принтер","роутер","клавиатура","мышка","монитор","колонка","флешка","зарядка","фотоаппарат","проектор"],
    "Транспорт": ["машина","автобус","трамвай","троллейбус","поезд","самолёт","вертолёт","корабль","лодка","катер","велосипед","мотоцикл","самокат","метро","такси","трактор","грузовик","ракета","яхта","подводная лодка"],
    "Действие": ["бежать","прыгать","танцевать","петь","спать","есть","пить","смеяться","плакать","кричать","читать","писать","рисовать","плавать","лететь","готовить","целовать","обнимать","чихать","зевать","копать","фотографировать","звонить","махать","прятаться"],
}
CATEGORY_EMOJIS = {
    "Случайная":"🎲",
    "Животные":"🐾",
    "Спорт":"⚽",
    "Еда":"🍕",
    "Техника":"💻",
    "Транспорт":"🚗",
    "Действие":"💃",
}
AVATARS = ["🐊","💀","🍕","🎉","👑","⚓","😄","😂","🤖","🦁","🐉","🍔"]
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me-local")
DEV_MODE = env_flag("DEV_MODE")
KICK_THRESHOLD = 0.60

def normalize_word(text: str) -> str:
    text = (text or "").lower().strip().replace("ё","е")
    text = re.sub(r"[^а-яa-z0-9\s-]","",text)
    return re.sub(r"\s+"," ",text)

def get_proximity(guess: str, answer: str):
    guess = normalize_word(guess)
    answer = normalize_word(answer)
    if not guess or not answer:
        return None
    ratio = SequenceMatcher(None, guess, answer).ratio()
    if ratio >= 0.76:
        return "hot"
    if ratio >= 0.56:
        return "warm"
    if len(guess) >= 4 and (guess in answer or answer in guess):
        return "warm"
    return None

class GameRoom:
    def __init__(self):
        self.players = {}
        self.leader_id = None
        self.current_word = None
        self.category = None
        self.is_active = False
        self.guessed_history = []
        self.words_pool = []
        self.message_counter = 0
        self.recent_messages = {}
        self.top_leader_id = None
        self.kick_vote = None

    async def broadcast(self, data):
        sockets = list(self.players)
        if not sockets:
            return
        results = await asyncio.gather(
            *(ws.send_json(data) for ws in sockets),
            return_exceptions=True,
        )
        dead = [ws for ws, result in zip(sockets, results) if isinstance(result, Exception)]
        for ws in dead:
            self.players.pop(ws, None)
        if dead:
            await self.cleanup_empty_room()

    async def send_to(self, ws, data):
        try:
            await ws.send_json(data)
        except Exception:
            pass

    async def cleanup_empty_room(self):
        if self.players:
            return
        self.reset_state()

    def reset_state(self):
        self.leader_id = None
        self.current_word = None
        self.category = None
        self.is_active = False
        self.guessed_history = []
        self.words_pool = []
        self.recent_messages = {}
        self.top_leader_id = None
        self.kick_vote = None

    def get_player_list(self):
        return [{
            "id": p["id"],
            "emoji": p["emoji"],
            "score": p["score"],
            "name": p["name"],
            "spectator": p.get("spectator", False),
        } for p in self.players.values()]

    def get_player_by_id(self, player_id):
        try:
            player_id = int(player_id)
        except (TypeError, ValueError):
            return None, None
        for ws, player in self.players.items():
            if player["id"] == player_id:
                return ws, player
        return None, None

    def get_rankings(self):
        players = self.get_player_list()
        players.sort(key=lambda p: (-p["score"], (p["name"] or "").lower(), p["id"]))
        return players

    def build_pool(self, category):
        if category == "Случайная":
            result = []
            for words in WORD_BANK.values():
                result.extend(words)
            return result
        return list(WORD_BANK.get(category, []))

    def next_word(self):
        if not self.words_pool:
            self.words_pool = self.build_pool(self.category)
            if self.guessed_history and len(self.words_pool) > 1 and self.guessed_history[-1] in self.words_pool:
                self.words_pool.remove(self.guessed_history[-1])
        if not self.words_pool:
            return None
        word = random.choice(self.words_pool)
        self.words_pool.remove(word)
        return word

    def create_message_id(self):
        self.message_counter += 1
        return f"msg-{self.message_counter}"

    def remember_message(self, message_id, data):
        self.recent_messages[message_id] = data
        if len(self.recent_messages) > 150:
            first = next(iter(self.recent_messages))
            del self.recent_messages[first]

    async def send_rankings(self, ws=None):
        payload = {"type":"leaderboard","players":self.get_rankings()}
        if ws is None:
            await self.broadcast(payload)
        else:
            await self.send_to(ws, payload)

    async def check_top_leader(self):
        rankings = self.get_rankings()
        if not rankings:
            self.top_leader_id = None
            return
        highest_score = rankings[0]["score"]
        if highest_score <= 0:
            return
        leaders = [p for p in rankings if p["score"] == highest_score]
        if len(leaders) != 1:
            return
        new_top = leaders[0]
        if new_top["id"] != self.top_leader_id:
            old_id = self.top_leader_id
            self.top_leader_id = new_top["id"]
            await self.broadcast({
                "type":"top_leader_changed",
                "player_id":new_top["id"],
                "name":new_top["name"],
                "emoji":new_top["emoji"],
                "score":new_top["score"],
                "previous_id":old_id,
            })

    async def announce_leader(self, player_id):
        _, player = self.get_player_by_id(player_id)
        if not player:
            return
        await self.broadcast({
            "type":"leader_changed",
            "leader_id":player["id"],
            "name":player["name"],
            "emoji":player["emoji"],
        })

    async def announce_category(self):
        await self.broadcast({
            "type":"category_changed",
            "category":self.category,
            "emoji":CATEGORY_EMOJIS.get(self.category,"🎲"),
        })

    async def send_word_to_leader(self):
        ws, _ = self.get_player_by_id(self.leader_id)
        if ws and self.current_word:
            await self.send_to(ws, {"type":"your_word","word":self.current_word})

    async def promote_spectators(self):
        promoted = []
        for player in self.players.values():
            if player.get("spectator"):
                player["spectator"] = False
                promoted.append(player["id"])
        if promoted:
            await self.broadcast({"type":"spectators_promoted","player_ids":promoted})
            await self.broadcast({"type":"player_list","players":self.get_player_list()})

    async def start_round(self, announce_category=False):
        self.current_word = self.next_word()
        if not self.current_word:
            self.is_active = False
            await self.broadcast({"type":"system","message":"Не удалось выбрать новое слово."})
            await self.broadcast({"type":"round_stopped"})
            return
        self.is_active = True
        _, leader = self.get_player_by_id(self.leader_id)
        if not leader:
            self.is_active = False
            await self.broadcast({"type":"round_stopped"})
            return
        leader["spectator"] = False
        await self.send_word_to_leader()
        await self.broadcast({
            "type":"game_start",
            "leader_id":leader["id"],
            "leader_name":leader["name"],
            "leader_emoji":leader["emoji"],
            "category":self.category,
            "category_emoji":CATEGORY_EMOJIS.get(self.category,"🎲"),
            "message":f"{leader['name']} стал ведущим! Категория: {self.category}",
        })
        await self.announce_leader(leader["id"])
        if announce_category:
            await self.announce_category()

    async def word_guessed(self, winner_ws, dev=False):
        winner = self.players.get(winner_ws)
        if not winner or not self.current_word or winner.get("spectator"):
            return
        solved_word = self.current_word
        winner["score"] += 1
        self.guessed_history.append(solved_word)
        if len(self.guessed_history) > 10:
            self.guessed_history.pop(0)
        self.leader_id = winner["id"]
        await self.broadcast({
            "type":"word_guessed",
            "winner_id":winner["id"],
            "winner_name":winner["name"],
            "winner_emoji":winner["emoji"],
            "word":solved_word,
            "score":winner["score"],
            "message":f"{winner['name']} угадал слово «{solved_word}»!" + (" (DEV)" if dev else ""),
        })
        await self.broadcast({"type":"history","words":self.guessed_history})
        await self.promote_spectators()
        await self.broadcast({"type":"player_list","players":self.get_player_list()})
        await self.check_top_leader()
        await self.start_round(announce_category=False)

    async def emit_chat(self, player, text, proximity=None, admin_injected=False):
        message_id = self.create_message_id()
        data = {
            "type":"chat",
            "message_id":message_id,
            "player_id":player["id"],
            "emoji":player["emoji"],
            "name":player["name"],
            "message":text,
            "proximity":proximity,
            "admin_injected":admin_injected,
        }
        self.remember_message(message_id, data)
        await self.broadcast(data)

    async def broadcast_vote_state(self):
        if not self.kick_vote:
            await self.broadcast({"type":"kick_vote_closed"})
            return
        target_ws, target = self.get_player_by_id(self.kick_vote["target_id"])
        if not target:
            self.kick_vote = None
            await self.broadcast({"type":"kick_vote_closed"})
            return
        eligible = [p["id"] for p in self.players.values() if p["id"] != target["id"]]
        yes_count = len(self.kick_vote["yes"] & set(eligible))
        no_count = len(self.kick_vote["no"] & set(eligible))
        needed = max(1, int(len(eligible) * KICK_THRESHOLD + 0.999999))
        await self.broadcast({
            "type":"kick_vote_state",
            "target_id":target["id"],
            "target_name":target["name"],
            "reason":self.kick_vote.get("reason",""),
            "yes":yes_count,
            "no":no_count,
            "eligible":len(eligible),
            "needed":needed,
        })
        if eligible and yes_count >= needed:
            await self.kick_player(target["id"], reason="Голосование игроков")

    async def kick_player(self, target_id, reason=""):
        ws, target = self.get_player_by_id(target_id)
        if not ws or not target:
            return False
        was_leader = self.leader_id == target["id"]
        await self.send_to(ws, {"type":"kicked","reason":reason or "Вы были удалены из игры."})
        try:
            await ws.close(code=4001)
        except Exception:
            pass
        self.players.pop(ws, None)
        if self.kick_vote and self.kick_vote.get("target_id") == target["id"]:
            self.kick_vote = None
        if was_leader:
            self.leader_id = None
            self.current_word = None
            self.is_active = False
        await self.broadcast({"type":"system","message":f"Игрок {target['name']} покинул эфир."})
        await self.broadcast({"type":"player_list","players":self.get_player_list()})
        if was_leader:
            await self.broadcast({"type":"leader_left","player_id":target["id"]})
            await self.broadcast({"type":"round_stopped"})
        await self.cleanup_empty_room()
        return True

room = GameRoom()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    existing_ids = {p["id"] for p in room.players.values()}
    player_id = random.randint(1000,9999)
    while player_id in existing_ids:
        player_id = random.randint(1000,9999)
    player_emoji = random.choice(AVATARS)
    default_name = f"{player_emoji} #{player_id}"
    spectator = bool(room.is_active and room.leader_id and room.current_word)
    room.players[websocket] = {
        "id":player_id,
        "emoji":player_emoji,
        "score":0,
        "name":default_name,
        "spectator":spectator,
        "is_admin":False,
    }
    await websocket.send_json({
        "type":"my_info",
        "id":player_id,
        "emoji":player_emoji,
        "name":default_name,
        "spectator":spectator,
    })
    if room.is_active and room.leader_id:
        _, leader = room.get_player_by_id(room.leader_id)
        await websocket.send_json({
            "type":"game_state",
            "active":True,
            "leader_id":room.leader_id,
            "leader_name":leader["name"] if leader else "",
            "category":room.category,
            "category_emoji":CATEGORY_EMOJIS.get(room.category,"🎲"),
            "spectator":spectator,
        })
    await room.broadcast({"type":"system","message":f"Игрок {default_name} присоединился к игре!"})
    await room.broadcast({"type":"player_list","players":room.get_player_list()})

    try:
        while True:
            try:
                data = await websocket.receive_json()
            except (WebSocketDisconnect, RuntimeError):
                break
            except (TypeError, ValueError):
                await websocket.send_json({"type":"error","message":"Сообщение должно быть корректным JSON."})
                continue
            if not isinstance(data, dict):
                await websocket.send_json({"type":"error","message":"Некорректный формат сообщения."})
                continue
            action = data.get("action")
            if not isinstance(action, str):
                await websocket.send_json({"type":"error","message":"Не указано действие."})
                continue
            player = room.players.get(websocket)
            if not player:
                continue
            player_id = player["id"]

            if action == "ping":
                await websocket.send_json({"type":"pong"})
                continue

            if action == "set_name":
                new_name = text_value(data, "name", 15)
                if new_name:
                    player["name"] = new_name
                    await websocket.send_json({"type":"system","message":f"✅ Ваше имя: {new_name}"})
                    await room.broadcast({"type":"player_list","players":room.get_player_list()})
                    if room.leader_id == player_id:
                        await room.announce_leader(player_id)
                continue

            if action == "get_top":
                await room.send_rankings(websocket)
                continue

            if action == "restart_game":
                room.reset_state()
                for p in room.players.values():
                    p["score"] = 0
                    p["spectator"] = False
                await room.broadcast({"type":"game_reset"})
                await room.broadcast({"type":"system","message":"🔄 Игра перезапущена. Счёт сброшен."})
                await room.broadcast({"type":"history","words":[]})
                await room.broadcast({"type":"player_list","players":room.get_player_list()})
                await room.broadcast({"type":"round_stopped"})
                continue

            if action in ("start_game","take_lead"):
                if room.is_active and room.leader_id:
                    await websocket.send_json({"type":"error","message":"Игра уже идёт!"})
                    continue
                if player.get("spectator"):
                    await websocket.send_json({"type":"error","message":"Наблюдатель сможет войти в игру после завершения текущего раунда."})
                    continue
                chosen_category = data.get("category","Случайная")
                if chosen_category not in CATEGORY_EMOJIS:
                    chosen_category = "Случайная"
                room.leader_id = player_id
                room.category = chosen_category
                room.words_pool = room.build_pool(chosen_category)
                await room.start_round(announce_category=True)
                await room.broadcast({"type":"player_list","players":room.get_player_list()})
                continue

            if action == "skip_word":
                if not room.is_active:
                    await websocket.send_json({"type":"error","message":"Игра не запущена."})
                    continue
                if room.leader_id != player_id:
                    await websocket.send_json({"type":"error","message":"Только ведущий может пропустить слово."})
                    continue
                old_word = room.current_word
                room.current_word = room.next_word()
                if not room.current_word:
                    await websocket.send_json({"type":"error","message":"Не удалось выбрать слово."})
                    continue
                await room.broadcast({"type":"word_skipped","word":old_word,"leader_id":player_id})
                await room.broadcast({"type":"system","message":"⏭ Ведущий пропустил слово."})
                await room.send_word_to_leader()
                continue

            if action == "stop_round":
                if room.leader_id != player_id:
                    await websocket.send_json({"type":"error","message":"Только ведущий может завершить раунд."})
                    continue
                room.is_active = False
                room.leader_id = None
                room.current_word = None
                await room.promote_spectators()
                await room.broadcast({"type":"system","message":"Раунд завершён. Можно выбрать нового ведущего."})
                await room.broadcast({"type":"round_stopped"})
                continue

            if action == "dev_win":
                if not DEV_MODE:
                    await websocket.send_json({"type":"error","message":"Режим разработчика отключён."})
                elif room.is_active and room.current_word and not player.get("spectator"):
                    await room.word_guessed(websocket, dev=True)
                continue

            if action == "mark_close":
                if room.leader_id != player_id:
                    await websocket.send_json({"type":"error","message":"Только ведущий может отмечать догадки."})
                    continue
                message_id = data.get("message_id")
                level = data.get("level","warm")
                if level not in ("none","warm","hot"):
                    level = "warm"
                if message_id in room.recent_messages:
                    await room.broadcast({"type":"message_heat","message_id":message_id,"level":level})
                continue

            if action == "start_kick_vote":
                target_id = data.get("target_id")
                reason = text_value(data, "reason", 120)
                _, target = room.get_player_by_id(target_id)
                if not target or target["id"] == player_id:
                    await websocket.send_json({"type":"error","message":"Нельзя начать это голосование."})
                    continue
                if room.kick_vote:
                    await websocket.send_json({"type":"error","message":"Голосование уже идёт."})
                    continue
                room.kick_vote = {
                    "target_id":target["id"],
                    "reason":reason,
                    "yes":{player_id},
                    "no":set(),
                }
                await room.broadcast_vote_state()
                continue

            if action == "vote_kick":
                if not room.kick_vote:
                    await websocket.send_json({"type":"error","message":"Сейчас нет голосования."})
                    continue
                target_id = room.kick_vote["target_id"]
                if player_id == target_id:
                    await websocket.send_json({"type":"error","message":"Нельзя голосовать в голосовании против себя."})
                    continue
                vote = data.get("vote")
                room.kick_vote["yes"].discard(player_id)
                room.kick_vote["no"].discard(player_id)
                if vote == "yes":
                    room.kick_vote["yes"].add(player_id)
                elif vote == "no":
                    room.kick_vote["no"].add(player_id)
                await room.broadcast_vote_state()
                continue

            if action == "admin_login":
                password = text_value(data, "password", 256)
                if password == ADMIN_PASSWORD:
                    player["is_admin"] = True
                    await websocket.send_json({"type":"admin_auth","ok":True})
                else:
                    await websocket.send_json({"type":"admin_auth","ok":False,"message":"Неверный пароль."})
                continue

            if action.startswith("admin_"):
                if not player.get("is_admin"):
                    await websocket.send_json({"type":"error","message":"Требуется вход администратора."})
                    continue

                if action == "admin_get_state":
                    await websocket.send_json({
                        "type":"admin_state",
                        "players":room.get_player_list(),
                        "leader_id":room.leader_id,
                        "current_word":room.current_word,
                        "category":room.category,
                        "is_active":room.is_active,
                    })
                    continue

                if action == "admin_set_word":
                    word = text_value(data, "word", 60)
                    if not word:
                        await websocket.send_json({"type":"error","message":"Введите слово."})
                        continue
                    room.current_word = word
                    room.is_active = True
                    await room.send_word_to_leader()
                    await room.broadcast({"type":"admin_word_changed"})
                    await websocket.send_json({"type":"admin_ok","action":"set_word"})
                    continue

                if action == "admin_set_leader":
                    target_id = data.get("target_id")
                    _, target = room.get_player_by_id(target_id)
                    if not target:
                        await websocket.send_json({"type":"error","message":"Игрок не найден."})
                        continue
                    target["spectator"] = False
                    room.leader_id = target["id"]
                    if not room.category:
                        room.category = "Случайная"
                    if not room.current_word:
                        room.words_pool = room.build_pool(room.category)
                        room.current_word = room.next_word()
                    room.is_active = bool(room.current_word)
                    await room.announce_leader(target["id"])
                    await room.send_word_to_leader()
                    await room.broadcast({"type":"player_list","players":room.get_player_list()})
                    await websocket.send_json({"type":"admin_ok","action":"set_leader"})
                    continue

                if action == "admin_say_as":
                    target_id = data.get("target_id")
                    text = text_value(data, "message", 500)
                    _, target = room.get_player_by_id(target_id)
                    if not target or not text:
                        await websocket.send_json({"type":"error","message":"Игрок или сообщение не найдены."})
                        continue
                    await room.emit_chat(target, text, proximity=None, admin_injected=True)
                    await websocket.send_json({"type":"admin_ok","action":"say_as"})
                    continue

                if action == "admin_emoji_as":
                    target_id = data.get("target_id")
                    emoji = text_value(data, "emoji", 16)
                    _, target = room.get_player_by_id(target_id)
                    if not target or not emoji:
                        await websocket.send_json({"type":"error","message":"Игрок или смайлик не найдены."})
                        continue
                    await room.emit_chat(target, emoji, proximity=None, admin_injected=True)
                    await websocket.send_json({"type":"admin_ok","action":"emoji_as"})
                    continue

                if action == "admin_kick":
                    target_id = data.get("target_id")
                    reason = text_value(data, "reason", 120)
                    try:
                        target_id = int(target_id)
                    except (TypeError, ValueError):
                        await websocket.send_json({"type":"error","message":"Некорректный ID игрока."})
                        continue
                    if target_id == player_id:
                        await websocket.send_json({"type":"error","message":"Нельзя кикнуть себя из этой сессии."})
                        continue
                    ok = await room.kick_player(target_id, reason=reason or "Удалён администратором")
                    if not ok:
                        await websocket.send_json({"type":"error","message":"Игрок не найден."})
                    else:
                        await websocket.send_json({"type":"admin_ok","action":"kick"})
                    continue

            if action == "guess":
                raw_text = text_value(data, "word", 500)
                if not raw_text:
                    continue
                normalized = normalize_word(raw_text)
                if normalized in ("/top","/топ","топ","/rating","/рейтинг"):
                    await room.send_rankings(websocket)
                    continue
                if player.get("spectator"):
                    await websocket.send_json({
                        "type":"spectator_notice",
                        "message":"Вы наблюдаете за текущим раундом. После отгадки сможете писать и угадывать.",
                    })
                    continue
                if room.leader_id == player_id:
                    await room.emit_chat(player, raw_text, proximity=None)
                    continue
                if room.is_active and room.leader_id and room.current_word:
                    if normalized == normalize_word(room.current_word):
                        await room.word_guessed(websocket)
                        continue
                    await room.emit_chat(player, raw_text, proximity=get_proximity(raw_text,room.current_word))
                else:
                    await websocket.send_json({"type":"error","message":"Игра ещё не начата."})
                continue

            if action == "chat":
                text = text_value(data, "message", 500)
                if not text:
                    continue
                if player.get("spectator"):
                    await websocket.send_json({
                        "type":"spectator_notice",
                        "message":"Вы наблюдаете за текущим раундом. После отгадки сможете писать.",
                    })
                    continue
                await room.emit_chat(player, text, proximity=None)

    except WebSocketDisconnect:
        pass
    finally:
        leaving_player = room.players.pop(websocket,None)
        if leaving_player:
            if room.kick_vote:
                room.kick_vote["yes"].discard(leaving_player["id"])
                room.kick_vote["no"].discard(leaving_player["id"])
                if room.kick_vote.get("target_id") == leaving_player["id"]:
                    room.kick_vote = None
                elif room.kick_vote:
                    await room.broadcast_vote_state()
            await room.broadcast({"type":"system","message":"Игрок покинул чат."})
            await room.broadcast({"type":"player_list","players":room.get_player_list()})
            if room.leader_id == leaving_player["id"]:
                room.leader_id = None
                room.current_word = None
                room.is_active = False
                await room.promote_spectators()
                await room.broadcast({"type":"leader_left","player_id":leaving_player["id"]})
                await room.broadcast({"type":"system","message":"Ведущий вышел. Выберите нового ведущего."})
                await room.broadcast({"type":"round_stopped"})
        await room.cleanup_empty_room()
