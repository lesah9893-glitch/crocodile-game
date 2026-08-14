import random
import re
from difflib import SequenceMatcher

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="docs"), name="static")
app.mount("/img", StaticFiles(directory="docs/img"), name="img")


@app.get("/")
async def get_index():
    return FileResponse("docs/index.html")


# =========================================================
# СЛОВАРИ
# =========================================================

WORD_BANK = {
    "Животные": [
        "крокодил", "слон", "пингвин", "зебра", "лев", "тигр",
        "медведь", "волк", "лиса", "заяц", "белка", "ёж",
        "мышь", "кот", "собака", "лошадь", "корова", "свинья",
        "утка", "попугай", "орёл", "сова", "кит", "дельфин",
        "акула", "медуза", "осьминог", "черепаха", "змея",
        "обезьяна", "горилла", "панда", "гепард", "енот",
    ],

    "Спорт": [
        "футбол", "хоккей", "баскетбол", "волейбол", "теннис",
        "бокс", "плавание", "биатлон", "лыжи", "сноуборд",
        "скейтборд", "шахматы", "гольф", "бег", "прыжок",
        "карате", "дзюдо", "борьба", "гимнастика", "велоспорт",
        "серфинг", "боулинг", "бильярд", "фигурное катание",
    ],

    "Еда": [
        "пицца", "бургер", "суши", "борщ", "пельмени",
        "макароны", "картошка", "мороженое", "шоколад",
        "торт", "арбуз", "банан", "яблоко", "сыр",
        "колбаса", "бутерброд", "шаурма", "омлет",
        "салат", "суп", "блины", "пончик", "хлеб",
    ],

    "Техника": [
        "компьютер", "телефон", "ноутбук", "телевизор",
        "микрофон", "наушники", "камера", "холодильник",
        "пылесос", "утюг", "чайник", "принтер", "роутер",
        "клавиатура", "мышка", "монитор", "колонка",
        "флешка", "зарядка", "фотоаппарат", "проектор",
    ],

    "Транспорт": [
        "машина", "автобус", "трамвай", "троллейбус",
        "поезд", "самолёт", "вертолёт", "корабль",
        "лодка", "катер", "велосипед", "мотоцикл",
        "самокат", "метро", "такси", "трактор",
        "грузовик", "ракета", "яхта", "подводная лодка",
    ],

    "Действие": [
        "бежать", "прыгать", "танцевать", "петь", "спать",
        "есть", "пить", "смеяться", "плакать", "кричать",
        "читать", "писать", "рисовать", "плавать", "лететь",
        "готовить", "целовать", "обнимать", "чихать",
        "зевать", "копать", "фотографировать", "звонить",
        "махать", "прятаться",
    ],
}


CATEGORY_EMOJIS = {
    "Случайная": "🎲",
    "Животные": "🐾",
    "Спорт": "⚽",
    "Еда": "🍕",
    "Техника": "💻",
    "Транспорт": "🚗",
    "Действие": "💃",
}


AVATARS = [
    "🐊", "💀", "🍕", "🎉", "👑", "⚓",
    "😄", "😂", "🤖", "🦁", "🐉", "🍔"
]


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================

def normalize_word(text: str) -> str:
    text = (text or "").lower().strip()
    text = text.replace("ё", "е")
    text = re.sub(r"[^а-яa-z0-9\s-]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def get_proximity(guess: str, answer: str):
    """
    Только лексическая близость.
    Семантику типа "океан" -> "море" без ИИ надежно не определить.
    Поэтому у ведущего дополнительно есть ручной mark_close.
    """

    guess = normalize_word(guess)
    answer = normalize_word(answer)

    if not guess or not answer:
        return None

    ratio = SequenceMatcher(None, guess, answer).ratio()

    # Очень похожее слово
    if ratio >= 0.76:
        return "hot"

    # Частичное совпадение / довольно похожее
    if ratio >= 0.56:
        return "warm"

    # Совпадает длинный кусок слова
    if len(guess) >= 4 and (guess in answer or answer in guess):
        return "warm"

    return None


# =========================================================
# ИГРОВАЯ КОМНАТА
# =========================================================

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

    # -----------------------------------------------------

    async def broadcast(self, data):
        dead = []

        for ws in list(self.players.keys()):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.players.pop(ws, None)

    # -----------------------------------------------------

    def get_player_list(self):
        return [
            {
                "id": p["id"],
                "emoji": p["emoji"],
                "score": p["score"],
                "name": p["name"],
            }
            for p in self.players.values()
        ]

    # -----------------------------------------------------

    def get_player_by_id(self, player_id):
        for ws, player in self.players.items():
            if player["id"] == player_id:
                return ws, player

        return None, None

    # -----------------------------------------------------

    def get_rankings(self):
        players = self.get_player_list()

        players.sort(
            key=lambda p: (
                -p["score"],
                (p["name"] or "").lower(),
                p["id"],
            )
        )

        return players

    # -----------------------------------------------------

    def build_pool(self, category):
        if category == "Случайная":
            result = []

            for words in WORD_BANK.values():
                result.extend(words)

            return result

        return list(WORD_BANK.get(category, []))

    # -----------------------------------------------------

    def next_word(self):
        # Если все слова закончились — запускаем новый цикл.
        if not self.words_pool:
            self.words_pool = self.build_pool(self.category)

            # Стараемся не повторить последнее слово сразу
            if (
                self.guessed_history
                and len(self.words_pool) > 1
                and self.guessed_history[-1] in self.words_pool
            ):
                self.words_pool.remove(self.guessed_history[-1])

        if not self.words_pool:
            return None

        word = random.choice(self.words_pool)
        self.words_pool.remove(word)

        return word

    # -----------------------------------------------------

    def create_message_id(self):
        self.message_counter += 1
        return f"msg-{self.message_counter}"

    # -----------------------------------------------------

    def remember_message(self, message_id, data):
        self.recent_messages[message_id] = data

        # Не держим память бесконечно
        if len(self.recent_messages) > 150:
            first = next(iter(self.recent_messages))
            del self.recent_messages[first]

    # -----------------------------------------------------

    async def send_rankings(self):
        await self.broadcast({
            "type": "leaderboard",
            "players": self.get_rankings(),
        })

    # -----------------------------------------------------

    async def check_top_leader(self):
        rankings = self.get_rankings()

        if not rankings:
            self.top_leader_id = None
            return

        highest_score = rankings[0]["score"]

        if highest_score <= 0:
            return

        leaders = [
            p for p in rankings
            if p["score"] == highest_score
        ]

        # При ничьей не объявляем нового единственного чемпиона
        if len(leaders) != 1:
            return

        new_top = leaders[0]

        if new_top["id"] != self.top_leader_id:
            old_id = self.top_leader_id
            self.top_leader_id = new_top["id"]

            await self.broadcast({
                "type": "top_leader_changed",
                "player_id": new_top["id"],
                "name": new_top["name"],
                "emoji": new_top["emoji"],
                "score": new_top["score"],
                "previous_id": old_id,
            })

    # -----------------------------------------------------

    async def announce_leader(self, player_id):
        _, player = self.get_player_by_id(player_id)

        if not player:
            return

        await self.broadcast({
            "type": "leader_changed",
            "leader_id": player["id"],
            "name": player["name"],
            "emoji": player["emoji"],
        })

    # -----------------------------------------------------

    async def announce_category(self):
        await self.broadcast({
            "type": "category_changed",
            "category": self.category,
            "emoji": CATEGORY_EMOJIS.get(self.category, "🎲"),
        })

    # -----------------------------------------------------

    async def send_word_to_leader(self):
        ws, _ = self.get_player_by_id(self.leader_id)

        if ws and self.current_word:
            try:
                await ws.send_json({
                    "type": "your_word",
                    "word": self.current_word,
                })
            except Exception:
                pass

    # -----------------------------------------------------

    async def start_round(self, announce_category=False):
        self.current_word = self.next_word()

        if not self.current_word:
            self.is_active = False

            await self.broadcast({
                "type": "system",
                "message": "Не удалось выбрать новое слово."
            })

            return

        self.is_active = True

        _, leader = self.get_player_by_id(self.leader_id)

        if not leader:
            self.is_active = False
            return

        await self.send_word_to_leader()

        await self.broadcast({
            "type": "game_start",
            "leader_id": leader["id"],
            "leader_name": leader["name"],
            "leader_emoji": leader["emoji"],
            "category": self.category,
            "category_emoji": CATEGORY_EMOJIS.get(self.category, "🎲"),
            "message": (
                f"{leader['name']} стал ведущим! "
                f"Категория: {self.category}"
            ),
        })

        await self.announce_leader(leader["id"])

        if announce_category:
            await self.announce_category()

    # -----------------------------------------------------

    async def word_guessed(self, winner_ws, dev=False):
        winner = self.players.get(winner_ws)

        if not winner or not self.current_word:
            return

        solved_word = self.current_word

        winner["score"] += 1

        self.guessed_history.append(solved_word)

        if len(self.guessed_history) > 10:
            self.guessed_history.pop(0)

        # Угадавший автоматически становится ведущим
        self.leader_id = winner["id"]

        await self.broadcast({
            "type": "word_guessed",
            "winner_id": winner["id"],
            "winner_name": winner["name"],
            "winner_emoji": winner["emoji"],
            "word": solved_word,
            "score": winner["score"],
            "message": (
                f"{winner['name']} угадал слово «{solved_word}»!"
                + (" (DEV)" if dev else "")
            ),
        })

        await self.broadcast({
            "type": "history",
            "words": self.guessed_history,
        })

        await self.broadcast({
            "type": "player_list",
            "players": self.get_player_list(),
        })

        await self.check_top_leader()

        # Новый раунд с тем же игроком как ведущим
        await self.start_round(announce_category=False)


room = GameRoom()


# =========================================================
# WEBSOCKET
# =========================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Чтобы ID случайно не совпали
    existing_ids = {
        p["id"]
        for p in room.players.values()
    }

    player_id = random.randint(1000, 9999)

    while player_id in existing_ids:
        player_id = random.randint(1000, 9999)

    player_emoji = random.choice(AVATARS)
    default_name = f"{player_emoji} #{player_id}"

    room.players[websocket] = {
        "id": player_id,
        "emoji": player_emoji,
        "score": 0,
        "name": default_name,
    }

    await websocket.send_json({
        "type": "my_info",
        "id": player_id,
        "emoji": player_emoji,
        "name": default_name,
    })

    await room.broadcast({
        "type": "system",
        "message": f"Игрок {default_name} присоединился к игре!",
    })

    await room.broadcast({
        "type": "player_list",
        "players": room.get_player_list(),
    })

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            player = room.players.get(websocket)

            if not player:
                continue

            player_id = player["id"]

            # =================================================
            # ИМЯ
            # =================================================

            if action == "set_name":
                new_name = data.get("name", "").strip()[:15]

                if new_name:
                    player["name"] = new_name

                    await websocket.send_json({
                        "type": "system",
                        "message": f"✅ Ваше имя: {new_name}",
                    })

                    await room.broadcast({
                        "type": "player_list",
                        "players": room.get_player_list(),
                    })

            # =================================================
            # ПЕРЕЗАПУСК
            # =================================================

            elif action == "restart_game":
                room.is_active = False
                room.leader_id = None
                room.current_word = None
                room.category = None
                room.words_pool = []
                room.guessed_history = []
                room.top_leader_id = None
                room.recent_messages = {}

                for p in room.players.values():
                    p["score"] = 0

                await room.broadcast({
                    "type": "game_reset",
                })

                await room.broadcast({
                    "type": "system",
                    "message": "🔄 Игра перезапущена. Счёт сброшен.",
                })

                await room.broadcast({
                    "type": "history",
                    "words": [],
                })

                await room.broadcast({
                    "type": "player_list",
                    "players": room.get_player_list(),
                })

            # =================================================
            # СТАРТ
            # =================================================

            elif action in ("start_game", "take_lead"):
                if room.is_active and room.leader_id:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Игра уже идёт!",
                    })

                    continue

                chosen_category = data.get("category", "Случайная")

                if chosen_category not in CATEGORY_EMOJIS:
                    chosen_category = "Случайная"

                room.leader_id = player_id
                room.category = chosen_category
                room.words_pool = room.build_pool(chosen_category)

                await room.start_round(announce_category=True)

                await room.broadcast({
                    "type": "player_list",
                    "players": room.get_player_list(),
                })

            # =================================================
            # ПРОПУСК СЛОВА
            # =================================================

            elif action == "skip_word":
                if not room.is_active:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Игра не запущена.",
                    })

                    continue

                if room.leader_id != player_id:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Только ведущий может пропустить слово.",
                    })

                    continue

                old_word = room.current_word

                room.current_word = room.next_word()

                if not room.current_word:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Не удалось выбрать слово.",
                    })

                    continue

                await room.broadcast({
                    "type": "word_skipped",
                    "word": old_word,
                    "leader_id": player_id,
                })

                await room.broadcast({
                    "type": "system",
                    "message": "⏭ Ведущий пропустил слово.",
                })

                await room.send_word_to_leader()

            # =================================================
            # DEV-ПОБЕДА
            # =================================================

            elif action == "dev_win":
                if room.is_active and room.current_word:
                    await room.word_guessed(websocket, dev=True)

            # =================================================
            # РУЧНАЯ ПОМЕТКА "ТЕПЛО / ГОРЯЧО"
            # =================================================

            elif action == "mark_close":
                if room.leader_id != player_id:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Только ведущий может отмечать догадки.",
                    })

                    continue

                message_id = data.get("message_id")
                level = data.get("level", "warm")

                if level not in ("none", "warm", "hot"):
                    level = "warm"

                if message_id not in room.recent_messages:
                    continue

                await room.broadcast({
                    "type": "message_heat",
                    "message_id": message_id,
                    "level": level,
                })

            # =================================================
            # ДОГАДКА / ЧАТ
            # =================================================

            elif action == "guess":
                raw_text = data.get("word", "").strip()

                if not raw_text:
                    continue

                normalized = normalize_word(raw_text)

                # -------------------------
                # /TOP
                # -------------------------

                if normalized in (
                    "/top",
                    "/топ",
                    "топ",
                    "/rating",
                    "/рейтинг",
                ):
                    await room.send_rankings()
                    continue

                # -------------------------
                # Если ведущий пишет в чат
                # -------------------------

                if room.leader_id == player_id:
                    message_id = room.create_message_id()

                    message_data = {
                        "type": "chat",
                        "message_id": message_id,
                        "player_id": player_id,
                        "emoji": player["emoji"],
                        "name": player["name"],
                        "message": raw_text,
                        "proximity": None,
                    }

                    room.remember_message(
                        message_id,
                        message_data,
                    )

                    await room.broadcast(message_data)
                    continue

                # -------------------------
                # Игра активна
                # -------------------------

                if room.is_active and room.leader_id and room.current_word:

                    # ТОЧНОЕ УГАДЫВАНИЕ
                    if normalized == normalize_word(room.current_word):
                        await room.word_guessed(websocket)
                        continue

                    # ОБЫЧНАЯ ДОГАДКА
                    proximity = get_proximity(
                        raw_text,
                        room.current_word,
                    )

                    message_id = room.create_message_id()

                    message_data = {
                        "type": "chat",
                        "message_id": message_id,
                        "player_id": player_id,
                        "emoji": player["emoji"],
                        "name": player["name"],
                        "message": raw_text,
                        "proximity": proximity,
                    }

                    room.remember_message(
                        message_id,
                        message_data,
                    )

                    await room.broadcast(message_data)

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Игра ещё не начата.",
                    })

            # =================================================
            # ОБЫЧНЫЙ ЧАТ
            # =================================================

            elif action == "chat":
                text = data.get("message", "").strip()

                if not text:
                    continue

                message_id = room.create_message_id()

                message_data = {
                    "type": "chat",
                    "message_id": message_id,
                    "player_id": player_id,
                    "emoji": player["emoji"],
                    "name": player["name"],
                    "message": text,
                    "proximity": None,
                }

                room.remember_message(
                    message_id,
                    message_data,
                )

                await room.broadcast(message_data)

    except WebSocketDisconnect:
        leaving_player = room.players.pop(websocket, None)

        await room.broadcast({
            "type": "system",
            "message": "Игрок покинул чат.",
        })

        await room.broadcast({
            "type": "player_list",
            "players": room.get_player_list(),
        })

        if leaving_player and room.leader_id == leaving_player["id"]:
            room.leader_id = None
            room.current_word = None
            room.is_active = False

            await room.broadcast({
                "type": "leader_left",
                "player_id": leaving_player["id"],
            })

            await room.broadcast({
                "type": "system",
                "message": "Ведущий вышел. Выберите нового ведущего.",
            })