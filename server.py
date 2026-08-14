import asyncio
import random
import os
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

# ===== СЛОВАРЬ =====
WORDS = [
    ('крокодил', 'Животные'), ('слон', 'Животные'), ('пингвин', 'Животные'), ('зебра', 'Животные'),
    ('лев', 'Животные'), ('тигр', 'Животные'), ('медведь', 'Животные'), ('волк', 'Животные'),
    ('лиса', 'Животные'), ('заяц', 'Животные'), ('белка', 'Животные'), ('ёж', 'Животные'),
    ('мышь', 'Животные'), ('крыса', 'Животные'), ('кот', 'Животные'), ('собака', 'Животные'),
    ('лошадь', 'Животные'), ('корова', 'Животные'), ('свинья', 'Животные'), ('курица', 'Животные'),
    ('петух', 'Животные'), ('утка', 'Животные'), ('гусь', 'Животные'), ('индюк', 'Животные'),
    ('попугай', 'Животные'), ('воробей', 'Животные'), ('голубь', 'Животные'), ('орёл', 'Животные'),
    ('сокол', 'Животные'), ('ястреб', 'Животные'), ('сова', 'Животные'), ('филин', 'Животные'),
    ('летучая мышь', 'Животные'), ('кит', 'Животные'), ('дельфин', 'Животные'), ('акула', 'Животные'),
    ('медуза', 'Животные'), ('осьминог', 'Животные'), ('кальмар', 'Животные'), ('черепаха', 'Животные'),
    ('ящерица', 'Животные'), ('змея', 'Животные'), ('хамелеон', 'Животные'), ('дракон', 'Животные'),
    ('единорог', 'Животные'), ('обезьяна', 'Животные'), ('горилла', 'Животные'), ('шимпанзе', 'Животные'),
    ('лемур', 'Животные'), ('коала', 'Животные'), ('панда', 'Животные'), ('ленивец', 'Животные'),
    ('муравьед', 'Животные'), ('дикобраз', 'Животные'), ('сурикат', 'Животные'), ('гепард', 'Животные'),
    ('пантера', 'Животные'), ('рысь', 'Животные'), ('росомаха', 'Животные'), ('бобр', 'Животные'),
    ('выдра', 'Животные'), ('тюлень', 'Животные'), ('морж', 'Животные'), ('верблюд', 'Животные'),
    ('лама', 'Животные'), ('альпака', 'Животные'), ('олень', 'Животные'), ('лось', 'Животные'),
    ('кабан', 'Животные'), ('носорог', 'Животные'), ('бегемот', 'Животные'), ('ягуар', 'Животные'),
    ('барс', 'Животные'), ('шакал', 'Животные'), ('енот', 'Животные'), ('скунс', 'Животные'),
    ('буйвол', 'Животные'), ('як', 'Животные'), ('мул', 'Животные'), ('осёл', 'Животные'),
    ('страус', 'Животные'), ('фламинго', 'Животные'), ('пеликан', 'Животные'), ('цапля', 'Животные'),
    ('чайка', 'Животные'), ('тукан', 'Животные'), ('дятел', 'Животные'), ('ласточка', 'Животные'),
    ('стриж', 'Животные'), ('манул', 'Животные'), ('сурок', 'Животные'), ('питон', 'Животные'),
    ('игуана', 'Животные'), ('варан', 'Животные'), ('геккон', 'Животные'), ('тритон', 'Животные'),
]

CATEGORY_EMOJIS = {'Животные': '🐾', 'Спорт': '⚽', 'Еда': '🍕', 'Техника': '💻', 'Транспорт': '🚗', 'Действие': '💃'}
AVATARS = ['🐊', '💀', '🍕', '🎉', '👑', '⚓', '😄', '😂', '🤖', '🦁', '🐉', '🍔']

class GameRoom:
    def __init__(self):
        self.players = {}
        self.leader_id = None
        self.current_word = None
        self.category = None
        self.is_active = False
        self.is_timer_active = False
        self.time_limit = 30
        self.time_left = 0
        self.timer_task = None
        self.guessed_history = []
        self.words_pool = []

    async def broadcast(self, message_data, exclude_ws=None):
        for ws in self.players:
            if ws != exclude_ws:
                try: await ws.send_json(message_data)
                except: pass

    def get_player_list(self):
        return [{'id': p['id'], 'emoji': p['emoji'], 'score': p['score'], 'name': p['name']} for p in self.players.values()]

    async def timer_loop(self, starter_ws):
        while self.is_active and self.is_timer_active and self.timer_task:
            await asyncio.sleep(1)
            if not self.is_active or not self.is_timer_active:
                break
            
            self.time_left -= 1
            await self.broadcast({"type": "timer", "time_left": self.time_left})
            
            if self.time_left == 20:
                await self.broadcast({"type": "system", "message": f"💡 Подсказка: Первая буква '{self.current_word[0].upper()}'"})
            if self.time_left == 10:
                await self.broadcast({"type": "system", "message": f"💡 Подсказка: В слове {len(self.current_word)} букв"})
            
            if self.time_left <= 0:
                self.is_active = False
                old_word = self.current_word
                self.current_word = None
                self.leader_id = None
                if self.timer_task:
                    self.timer_task.cancel()
                    self.timer_task = None
                await self.broadcast({"type": "system", "message": f"⏰ Время вышло! Слово было: {old_word}"})
                break

room = GameRoom()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    player_id = random.randint(1000, 9999)
    player_emoji = random.choice(AVATARS)
    default_name = f"{player_emoji} #{player_id}"
    
    room.players[websocket] = {'id': player_id, 'emoji': player_emoji, 'score': 0, 'name': default_name}
    
    await websocket.send_json({"type": "my_info", "id": player_id, "emoji": player_emoji, "name": default_name})
    await room.broadcast({"type": "system", "message": f"Игрок {player_emoji} присоединился к игре!"})
    await room.broadcast({"type": "player_list", "players": room.get_player_list()})

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "set_name":
                new_name = data.get("name", "").strip()[:15]
                if new_name:
                    room.players[websocket]['name'] = new_name
                    await websocket.send_json({"type": "system", "message": f"✅ Ваше имя обновлено: {new_name}"})
                    await room.broadcast({"type": "player_list", "players": room.get_player_list()})

            elif action == "restart_game":
                room.is_active = False
                room.guessed_history = []
                room.words_pool = []
                if room.timer_task:
                    room.timer_task.cancel()
                    room.timer_task = None
                for ws in room.players:
                    room.players[ws]['score'] = 0
                await room.broadcast({"type": "system", "message": "🔄 Игра перезапущена! Счетчики сброшены."})
                await room.broadcast({"type": "player_list", "players": room.get_player_list()})

            elif action == "start_game" or action == "take_lead":
                if room.is_active and room.leader_id:
                    await websocket.send_json({"type": "error", "message": "Игра уже идет!"})
                else:
                    if room.timer_task: room.timer_task.cancel()
                    
                    room.leader_id = player_id
                    chosen_category = data.get("category")
                    
                    if chosen_category and chosen_category in CATEGORY_EMOJIS:
                        filtered = [w for w in WORDS if w[1] == chosen_category]
                        room.words_pool = [w[0] for w in filtered] if filtered else [w[0] for w in WORDS]
                    else:
                        room.words_pool = [w[0] for w in WORDS]
                    
                    room.category = chosen_category if chosen_category in CATEGORY_EMOJIS else "Случайная"
                    
                    if not room.words_pool:
                        room.words_pool = ['крокодил']
                    
                    room.current_word = random.choice(room.words_pool)
                    room.words_pool.remove(room.current_word)
                    
                    room.is_active = True
                    room.is_timer_active = True
                    room.time_left = room.time_limit
                    
                    cat_emoji = CATEGORY_EMOJIS.get(room.category, '')
                    leader_name = room.players[websocket]['name']
                    await websocket.send_json({"type": "your_word", "word": room.current_word})
                    await room.broadcast({
                        "type": "game_start",
                        "leader_id": player_id,
                        "category": room.category,
                        "message": f"{leader_name} стал ведущим! Категория: {room.category} {cat_emoji}"
                    })
                    await room.broadcast({"type": "player_list", "players": room.get_player_list()})
                    room.timer_task = asyncio.create_task(room.timer_loop(websocket))

            elif action == "toggle_timer":
                if room.leader_id == player_id:
                    room.is_timer_active = not room.is_timer_active
                    if room.is_timer_active:
                        if not room.timer_task:
                            room.timer_task = asyncio.create_task(room.timer_loop(websocket))
                    else:
                        if room.timer_task:
                            room.timer_task.cancel()
                            room.timer_task = None
                    await room.broadcast({"type": "timer_status", "status": room.is_timer_active})
                else:
                    await websocket.send_json({"type": "error", "message": "Только ведущий может управлять таймером!"})

            elif action == "skip_word":
                if room.is_active and room.leader_id == player_id:
                    if room.words_pool:
                        if room.timer_task: room.timer_task.cancel()
                        room.current_word = random.choice(room.words_pool)
                        room.words_pool.remove(room.current_word)
                        room.time_left = room.time_limit
                        await room.broadcast({"type": "system", "message": f"⏭ Слово пропущено! Новый раунд."})
                        await websocket.send_json({"type": "your_word", "word": room.current_word})
                        room.timer_task = asyncio.create_task(room.timer_loop(websocket))
                    else:
                        room.is_active = False
                        if room.timer_task: room.timer_task.cancel()
                        await room.broadcast({"type": "system", "message": "🎉 Все слова в этой категории закончились!"})
                else:
                    await websocket.send_json({"type": "error", "message": "Только ведущий может пропустить слово!"})

            elif action == "dev_win":
                if room.is_active and room.leader_id and room.current_word:
                    room.players[websocket]['score'] += 1
                    room.guessed_history.append(room.current_word)
                    if len(room.guessed_history) > 5:
                        room.guessed_history.pop(0)
                    
                    if room.timer_task: room.timer_task.cancel()
                    room.leader_id = player_id
                    
                    winner_name = room.players[websocket]['name']
                    await room.broadcast({
                        "type": "word_guessed",
                        "winner_id": player_id,
                        "winner_emoji": player_emoji,
                        "message": f"🎉 {winner_name} угадал слово! (Dev)"
                    })
                    await room.broadcast({"type": "history", "words": room.guessed_history})
                    
                    if not room.words_pool:
                        room.is_active = False
                        await room.broadcast({"type": "system", "message": "🎉 Все слова угаданы! Игра окончена!"})
                    else:
                        room.current_word = random.choice(room.words_pool)
                        room.words_pool.remove(room.current_word)
                        room.time_left = room.time_limit
                        await websocket.send_json({"type": "your_word", "word": room.current_word})
                        await room.broadcast({"type": "player_list", "players": room.get_player_list()})
                        await room.broadcast({"type": "game_start", "leader_id": player_id, "category": room.category, "message": f"Новый раунд! Ведущий: {winner_name}"})
                        room.timer_task = asyncio.create_task(room.timer_loop(websocket))
                else:
                    await websocket.send_json({"type": "error", "message": "Игра не активна или нет ведущего!"})

            elif action == "guess":
                guess_word = data.get("word", "").strip().lower()
                
                if room.leader_id == player_id:
                    await room.broadcast({"type": "chat", "player_id": player_id, "emoji": player_emoji, "name": room.players[websocket]['name'], "message": guess_word})
                elif room.is_active and room.leader_id and room.current_word:
                    if guess_word == room.current_word:
                        room.players[websocket]['score'] += 1
                        room.guessed_history.append(room.current_word)
                        if len(room.guessed_history) > 5:
                            room.guessed_history.pop(0)
                        
                        if room.timer_task: room.timer_task.cancel()
                        room.leader_id = player_id
                        
                        winner_name = room.players[websocket]['name']
                        await room.broadcast({
                            "type": "word_guessed",
                            "winner_id": player_id,
                            "winner_emoji": player_emoji,
                            "message": f"🎉 {winner_name} угадал слово!"
                        })
                        await room.broadcast({"type": "history", "words": room.guessed_history})

                        if not room.words_pool:
                            room.is_active = False
                            await room.broadcast({"type": "system", "message": "🎉 Все слова угаданы! Игра окончена!"})
                        else:
                            room.current_word = random.choice(room.words_pool)
                            room.words_pool.remove(room.current_word)
                            room.time_left = room.time_limit
                            await websocket.send_json({"type": "your_word", "word": room.current_word})
                            await room.broadcast({"type": "player_list", "players": room.get_player_list()})
                            await room.broadcast({"type": "game_start", "leader_id": player_id, "category": room.category, "message": f"Новый раунд! Ведущий: {winner_name}"})
                            room.timer_task = asyncio.create_task(room.timer_loop(websocket))
                    else:
                        await room.broadcast({"type": "chat", "player_id": player_id, "emoji": player_emoji, "name": room.players[websocket]['name'], "message": guess_word})
                else:
                    await websocket.send_json({"type": "error", "message": "Игра не начата или нет ведущего."})
            
            elif action == "chat":
                await room.broadcast({"type": "chat", "player_id": player_id, "emoji": player_emoji, "name": room.players[websocket]['name'], "message": data.get("message")})

    except WebSocketDisconnect:
        if websocket in room.players: del room.players[websocket]
        await room.broadcast({"type": "system", "message": f"Игрок покинул чат."})
        await room.broadcast({"type": "player_list", "players": room.get_player_list()})
        if room.leader_id == player_id:
            room.leader_id = None
            room.is_active = False
            if room.timer_task: room.timer_task.cancel()
            await room.broadcast({"type": "system", "message": "Ведущий вышел. Игра приостановлена."})