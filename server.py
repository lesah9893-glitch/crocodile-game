import asyncio
import random
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Разрешаем кросс-доменные запросы (нужно для работы в ВК)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/img", StaticFiles(directory="static/img"), name="img")
app.mount("/sounds", StaticFiles(directory="static/sounds"), name="sounds")

@app.get("/")
async def get_index():
    return FileResponse("static/index.html")

# ===== СЛОВАРЬ (503 слова) =====
WORDS = [
    # ЖИВОТНЫЕ (96 слов)
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

    # СПОРТ (68 слов)
    ('футбол', 'Спорт'), ('баскетбол', 'Спорт'), ('теннис', 'Спорт'), ('волейбол', 'Спорт'),
    ('хоккей', 'Спорт'), ('бейсбол', 'Спорт'), ('гольф', 'Спорт'), ('регби', 'Спорт'),
    ('крикет', 'Спорт'), ('биатлон', 'Спорт'), ('лыжи', 'Спорт'), ('сноуборд', 'Спорт'),
    ('фигурное катание', 'Спорт'), ('конькобежный спорт', 'Спорт'), ('плавание', 'Спорт'), ('прыжки в воду', 'Спорт'),
    ('синхронное плавание', 'Спорт'), ('гребля', 'Спорт'), ('каноэ', 'Спорт'), ('парусный спорт', 'Спорт'),
    ('бокс', 'Спорт'), ('борьба', 'Спорт'), ('дзюдо', 'Спорт'), ('самбо', 'Спорт'),
    ('карате', 'Спорт'), ('тхэквондо', 'Спорт'), ('фехтование', 'Спорт'), ('тяжёлая атлетика', 'Спорт'),
    ('гимнастика', 'Спорт'), ('акробатика', 'Спорт'), ('бег', 'Спорт'), ('марафон', 'Спорт'),
    ('эстафета', 'Спорт'), ('прыжки в длину', 'Спорт'), ('прыжки в высоту', 'Спорт'), ('метание копья', 'Спорт'),
    ('метание диска', 'Спорт'), ('толкание ядра', 'Спорт'), ('шахматы', 'Спорт'), ('шашки', 'Спорт'),
    ('бильярд', 'Спорт'), ('дартс', 'Спорт'), ('боулинг', 'Спорт'), ('настольный теннис', 'Спорт'),
    ('сквош', 'Спорт'), ('бадминтон', 'Спорт'), ('конный спорт', 'Спорт'), ('велоспорт', 'Спорт'),
    ('триатлон', 'Спорт'), ('кроссфит', 'Спорт'), ('йога', 'Спорт'), ('пилатес', 'Спорт'),
    ('аэробика', 'Спорт'), ('танцы', 'Спорт'), ('брейк-данс', 'Спорт'), ('паркур', 'Спорт'),
    ('сёрфинг', 'Спорт'), ('вейкбординг', 'Спорт'), ('скалолазание', 'Спорт'), ('альпинизм', 'Спорт'),
    ('стрельба', 'Спорт'), ('метание молота', 'Спорт'), ('поло', 'Спорт'), ('скелетон', 'Спорт'),
    ('фристайл', 'Спорт'), ('кёрлинг', 'Спорт'), ('сноукайтинг', 'Спорт'), ('дайвинг', 'Спорт'),

    # ЕДА (95 слов)
    ('пицца', 'Еда'), ('бургер', 'Еда'), ('суши', 'Еда'), ('роллы', 'Еда'),
    ('шашлык', 'Еда'), ('стейк', 'Еда'), ('гуляш', 'Еда'), ('борщ', 'Еда'),
    ('щи', 'Еда'), ('пельмени', 'Еда'), ('вареники', 'Еда'), ('блины', 'Еда'),
    ('оладьи', 'Еда'), ('сырники', 'Еда'), ('творог', 'Еда'), ('сметана', 'Еда'),
    ('кефир', 'Еда'), ('молоко', 'Еда'), ('йогурт', 'Еда'), ('мороженое', 'Еда'),
    ('шоколад', 'Еда'), ('конфеты', 'Еда'), ('печенье', 'Еда'), ('пряник', 'Еда'),
    ('торт', 'Еда'), ('пирожное', 'Еда'), ('капкейк', 'Еда'), ('маффин', 'Еда'),
    ('круассан', 'Еда'), ('багет', 'Еда'), ('хлеб', 'Еда'), ('булка', 'Еда'),
    ('каша', 'Еда'), ('овсянка', 'Еда'), ('гречка', 'Еда'), ('рис', 'Еда'),
    ('макароны', 'Еда'), ('спагетти', 'Еда'), ('лазанья', 'Еда'), ('рагу', 'Еда'),
    ('котлета', 'Еда'), ('бифштекс', 'Еда'), ('фрикаделька', 'Еда'), ('сосиска', 'Еда'),
    ('колбаса', 'Еда'), ('ветчина', 'Еда'), ('бекон', 'Еда'), ('яичница', 'Еда'),
    ('омлет', 'Еда'), ('салат', 'Еда'), ('винегрет', 'Еда'), ('сельдь', 'Еда'),
    ('икра', 'Еда'), ('креветка', 'Еда'), ('лосось', 'Еда'), ('форель', 'Еда'),
    ('тунец', 'Еда'), ('скумбрия', 'Еда'), ('картофель', 'Еда'), ('морковь', 'Еда'),
    ('свёкла', 'Еда'), ('капуста', 'Еда'), ('лук', 'Еда'), ('чеснок', 'Еда'),
    ('перец', 'Еда'), ('огурец', 'Еда'), ('помидор', 'Еда'), ('яблоко', 'Еда'),
    ('банан', 'Еда'), ('апельсин', 'Еда'), ('виноград', 'Еда'), ('арбуз', 'Еда'),
    ('мандарин', 'Еда'), ('лимон', 'Еда'), ('грейпфрут', 'Еда'), ('ананас', 'Еда'),
    ('манго', 'Еда'), ('груша', 'Еда'), ('слива', 'Еда'), ('персик', 'Еда'),
    ('абрикос', 'Еда'), ('вишня', 'Еда'), ('черешня', 'Еда'), ('малина', 'Еда'),
    ('ежевика', 'Еда'), ('клубника', 'Еда'), ('черника', 'Еда'), ('клюква', 'Еда'),
    ('смородина', 'Еда'), ('крыжовник', 'Еда'), ('орех', 'Еда'), ('фисташка', 'Еда'),
    ('миндаль', 'Еда'), ('арахис', 'Еда'), ('манты', 'Еда'), ('хинкали', 'Еда'),

    # ТЕХНИКА (61 слово)
    ('компьютер', 'Техника'), ('телефон', 'Техника'), ('планшет', 'Техника'), ('ноутбук', 'Техника'),
    ('клавиатура', 'Техника'), ('мышь', 'Техника'), ('монитор', 'Техника'), ('принтер', 'Техника'),
    ('сканер', 'Техника'), ('наушники', 'Техника'), ('колонки', 'Техника'), ('микрофон', 'Техника'),
    ('веб-камера', 'Техника'), ('процессор', 'Техника'), ('видеокарта', 'Техника'), ('оперативная память', 'Техника'),
    ('жёсткий диск', 'Техника'), ('флешка', 'Техника'), ('роутер', 'Техника'), ('модем', 'Техника'),
    ('смартфон', 'Техника'), ('умные часы', 'Техника'), ('фитнес-браслет', 'Техника'), ('робот', 'Техника'),
    ('дрон', 'Техника'), ('квадрокоптер', 'Техника'), ('3D-принтер', 'Техника'), ('телевизор', 'Техника'),
    ('проектор', 'Техника'), ('плеер', 'Техника'), ('ресивер', 'Техника'), ('усилитель', 'Техника'),
    ('микшер', 'Техника'), ('синтезатор', 'Техника'), ('тостер', 'Техника'), ('мультиварка', 'Техника'),
    ('микроволновка', 'Техника'), ('холодильник', 'Техника'), ('стиральная машина', 'Техника'), ('пылесос', 'Техника'),
    ('утюг', 'Техника'), ('фен', 'Техника'), ('блендер', 'Техника'), ('миксер', 'Техника'),
    ('кухонный комбайн', 'Техника'), ('кофемашина', 'Техника'), ('чайник', 'Техника'), ('плита', 'Техника'),
    ('духовка', 'Техника'), ('вытяжка', 'Техника'), ('кондиционер', 'Техника'), ('обогреватель', 'Техника'),
    ('вентилятор', 'Техника'), ('счётчик', 'Техника'), ('датчик', 'Техника'), ('ионизатор', 'Техника'),
    ('увлажнитель', 'Техника'), ('осциллограф', 'Техника'), ('мультиметр', 'Техника'), ('паяльник', 'Техника'),
    ('дрель', 'Техника'),

    # ТРАНСПОРТ (50 слов)
    ('самолёт', 'Транспорт'), ('поезд', 'Транспорт'), ('велосипед', 'Транспорт'), ('мотоцикл', 'Транспорт'),
    ('автомобиль', 'Транспорт'), ('автобус', 'Транспорт'), ('трамвай', 'Транспорт'), ('троллейбус', 'Транспорт'),
    ('метро', 'Транспорт'), ('электричка', 'Транспорт'), ('пароход', 'Транспорт'), ('лодка', 'Транспорт'),
    ('яхта', 'Транспорт'), ('катер', 'Транспорт'), ('корабль', 'Транспорт'), ('танкер', 'Транспорт'),
    ('судно', 'Транспорт'), ('теплоход', 'Транспорт'), ('вертолёт', 'Транспорт'), ('дирижабль', 'Транспорт'),
    ('ракета', 'Транспорт'), ('космический корабль', 'Транспорт'), ('спутник', 'Транспорт'), ('экскаватор', 'Транспорт'),
    ('бульдозер', 'Транспорт'), ('кран', 'Транспорт'), ('погрузчик', 'Транспорт'), ('трактор', 'Транспорт'),
    ('комбайн', 'Транспорт'), ('скутер', 'Транспорт'), ('мопед', 'Транспорт'), ('квадроцикл', 'Транспорт'),
    ('гидроцикл', 'Транспорт'), ('сани', 'Транспорт'), ('телега', 'Транспорт'), ('тачка', 'Транспорт'),
    ('вагонетка', 'Транспорт'), ('карета', 'Транспорт'), ('коляска', 'Транспорт'), ('лифт', 'Транспорт'),
    ('эскалатор', 'Транспорт'), ('подвесная канатная дорога', 'Транспорт'), ('фуникулёр', 'Транспорт'),
    ('самокат', 'Транспорт'), ('моноколесо', 'Транспорт'), ('гироскутер', 'Транспорт'), ('сегвей', 'Транспорт'),
    ('канал', 'Транспорт'), ('трубопровод', 'Транспорт'), ('баржа', 'Транспорт'),

    # ДЕЙСТВИЕ (140 слов)
    ('танцевать', 'Действие'), ('прыгать', 'Действие'), ('бегать', 'Действие'), ('летать', 'Действие'),
    ('плавать', 'Действие'), ('ползать', 'Действие'), ('ходить', 'Действие'), ('сидеть', 'Действие'),
    ('лежать', 'Действие'), ('стоять', 'Действие'), ('говорить', 'Действие'), ('петь', 'Действие'),
    ('кричать', 'Действие'), ('шептать', 'Действие'), ('смеяться', 'Действие'), ('плакать', 'Действие'),
    ('улыбаться', 'Действие'), ('хмуриться', 'Действие'), ('зевать', 'Действие'), ('чихать', 'Действие'),
    ('кашлять', 'Действие'), ('моргать', 'Действие'), ('смотреть', 'Действие'), ('слушать', 'Действие'),
    ('нюхать', 'Действие'), ('пробовать', 'Действие'), ('трогать', 'Действие'), ('гладить', 'Действие'),
    ('стучать', 'Действие'), ('нажимать', 'Действие'), ('писать', 'Действие'), ('читать', 'Действие'),
    ('считать', 'Действие'), ('думать', 'Действие'), ('мечтать', 'Действие'), ('вспоминать', 'Действие'),
    ('забывать', 'Действие'), ('любить', 'Действие'), ('ненавидеть', 'Действие'), ('бояться', 'Действие'),
    ('удивляться', 'Действие'), ('радоваться', 'Действие'), ('грустить', 'Действие'), ('злиться', 'Действие'),
    ('стесняться', 'Действие'), ('ждать', 'Действие'), ('искать', 'Действие'), ('находить', 'Действие'),
    ('терять', 'Действие'), ('давать', 'Действие'), ('брать', 'Действие'), ('кидать', 'Действие'),
    ('ловить', 'Действие'), ('открывать', 'Действие'), ('закрывать', 'Действие'), ('включать', 'Действие'),
    ('выключать', 'Действие'), ('поднимать', 'Действие'), ('опускать', 'Действие'), ('тянуть', 'Действие'),
    ('толкать', 'Действие'), ('резать', 'Действие'), ('клеить', 'Действие'), ('рисовать', 'Действие'),
    ('красить', 'Действие'), ('чинить', 'Действие'), ('ломать', 'Действие'), ('собирать', 'Действие'),
    ('строить', 'Действие'), ('разрушать', 'Действие'), ('создавать', 'Действие'), ('уничтожать', 'Действие'),
    ('есть', 'Действие'), ('пить', 'Действие'), ('готовить', 'Действие'), ('жарить', 'Действие'),
    ('варить', 'Действие'), ('печь', 'Действие'), ('тушить', 'Действие'), ('солить', 'Действие'),
    ('перчить', 'Действие'), ('мешать', 'Действие'), ('взбивать', 'Действие'), ('наливать', 'Действие'),
    ('насыпать', 'Действие'), ('нарезать', 'Действие'), ('украшать', 'Действие'), ('сервировать', 'Действие'),
    ('угощать', 'Действие'), ('лечить', 'Действие'), ('спасать', 'Действие'), ('защищать', 'Действие'),
    ('нападать', 'Действие'), ('прятаться', 'Действие'), ('убегать', 'Действие'), ('догонять', 'Действие'),
    ('обгонять', 'Действие'), ('падать', 'Действие'), ('подниматься', 'Действие'), ('спускаться', 'Действие'),
    ('переходить', 'Действие'), ('проползать', 'Действие'), ('пролетать', 'Действие'), ('проплывать', 'Действие'),
    ('путешествовать', 'Действие'), ('гулять', 'Действие'), ('отдыхать', 'Действие'), ('работать', 'Действие'),
    ('учиться', 'Действие'), ('экспериментировать', 'Действие'), ('наблюдать', 'Действие'), ('изучать', 'Действие'),
    ('изобретать', 'Действие'), ('исследовать', 'Действие'), ('решать', 'Действие'), ('загадывать', 'Действие'),
    ('отгадывать', 'Действие'), ('притворяться', 'Действие'), ('шутить', 'Действие'), ('обманывать', 'Действие'),
    ('доверять', 'Действие'), ('дружить', 'Действие'), ('ссориться', 'Действие'), ('мириться', 'Действие'),
    ('советовать', 'Действие'), ('слушаться', 'Действие'), ('помогать', 'Действие'), ('заботиться', 'Действие'),
    ('целовать', 'Действие'), ('обнимать', 'Действие'), ('жалеть', 'Действие'), ('светить', 'Действие'),
    ('греть', 'Действие'), ('охлаждать', 'Действие'), ('обжигать', 'Действие'), ('замерзать', 'Действие'),
    ('таять', 'Действие'), ('испаряться', 'Действие'), ('дремать', 'Действие'), ('просыпаться', 'Действие'),
    ('засыпать', 'Действие'), ('пугать', 'Действие'), ('шевелить', 'Действие'), ('махать', 'Действие'),
    ('качать', 'Действие'), ('вращать', 'Действие'), ('кружиться', 'Действие'), ('парить', 'Действие'),
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

# Для локального запуска (Render использует команду uvicorn)
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)