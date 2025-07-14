"""
Kim Milyoner Olmak İster - Telegram Bot
---------------------------------------
Gruplarda oynanabilen, "Kim Milyoner Olmak İster" formatında bir yarışma botu.
Her soru için 30 saniyelik zaman sınırı vardır.
"""

import telebot
from telebot import types
import random
import time
import logging
import sqlite3
from datetime import datetime
import threading
import os
import json

# Bot tokeninizi buraya ekleyin
TOKEN = "bot_tokeninizi_buraya_ekleyin"
bot = telebot.TeleBot(TOKEN)

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("milyoner_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Soru dosyalarının bulunduğu dizin
QUESTIONS_DIR = "questions"

# Veritabanı fonksiyonları
def get_db():
    conn = sqlite3.connect('milyoner_bot.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Kullanıcı tablosu
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        games_played INTEGER DEFAULT 0,
        total_rounds_passed INTEGER DEFAULT 0,
        total_correct_answers INTEGER DEFAULT 0,
        total_wins INTEGER DEFAULT 0,
        join_date TEXT
    )
    ''')
    
    # Gruplar tablosu
    c.execute('''
    CREATE TABLE IF NOT EXISTS groups (
        group_id INTEGER PRIMARY KEY,
        group_name TEXT,
        games_played INTEGER DEFAULT 0,
        join_date TEXT
    )
    ''')
    
    # Oyun oturumları tablosu
    c.execute('''
    CREATE TABLE IF NOT EXISTS game_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        admin_id INTEGER,
        start_time TEXT,
        end_time TEXT DEFAULT NULL,
        total_rounds INTEGER,
        current_round INTEGER DEFAULT 0,
        status TEXT DEFAULT "waiting",
        winner_id INTEGER DEFAULT NULL,
        FOREIGN KEY (group_id) REFERENCES groups(group_id),
        FOREIGN KEY (admin_id) REFERENCES users(user_id),
        FOREIGN KEY (winner_id) REFERENCES users(user_id)
    )
    ''')
    
    # Oyun katılımcıları tablosu
    c.execute('''
    CREATE TABLE IF NOT EXISTS game_participants (
        game_id INTEGER,
        user_id INTEGER,
        join_time TEXT,
        eliminated_round INTEGER DEFAULT NULL,
        eliminated_reason TEXT DEFAULT NULL,
        FOREIGN KEY (game_id) REFERENCES game_sessions(id),
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        PRIMARY KEY (game_id, user_id)
    )
    ''')
    
    conn.commit()
    conn.close()

# Soruları yükleme fonksiyonu
def load_questions():
    questions = {}
    for level in range(1, 11):
        file_path = os.path.join(QUESTIONS_DIR, f"level_{level}.json")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                questions[level] = json.load(f)
            logger.info(f"Level {level} için {len(questions[level])} soru yüklendi")
        except FileNotFoundError:
            logger.error(f"{file_path} dosyası bulunamadı!")
            questions[level] = []
        except json.JSONDecodeError:
            logger.error(f"{file_path} dosyası geçersiz JSON formatında!")
            questions[level] = []
    
    return questions

# Soruları başlangıçta yükle
questions_db = load_questions()

# Kullanıcı kayıt fonksiyonu
def register_user(user):
    user_id = user.id
    username = user.username
    first_name = user.first_name
    last_name = user.last_name if user.last_name else ""
    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db()
    c = conn.cursor()
    
    # Kullanıcı var mı kontrol et
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user_record = c.fetchone()
    
    if not user_record:
        c.execute('''
        INSERT INTO users (user_id, username, first_name, last_name, join_date)
        VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, join_date))
    else:
        c.execute('''
        UPDATE users SET username = ?, first_name = ?, last_name = ?
        WHERE user_id = ?
        ''', (username, first_name, last_name, user_id))
    
    conn.commit()
    conn.close()

# Grup kayıt fonksiyonu
def register_group(chat):
    group_id = chat.id
    group_name = chat.title
    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db()
    c = conn.cursor()
    
    # Grup var mı kontrol et
    c.execute("SELECT * FROM groups WHERE group_id = ?", (group_id,))
    group_record = c.fetchone()
    
    if not group_record:
        c.execute('''
        INSERT INTO groups (group_id, group_name, join_date)
        VALUES (?, ?, ?)
        ''', (group_id, group_name, join_date))
    else:
        c.execute('''
        UPDATE groups SET group_name = ?
        WHERE group_id = ?
        ''', (group_name, group_id))
    
    conn.commit()
    conn.close()

# Grup yöneticisi kontrolü
def is_admin(chat_id, user_id):
    try:
        chat_member = bot.get_chat_member(chat_id, user_id)
        return chat_member.status in ['creator', 'administrator']
    except Exception as e:
        logger.error(f"Admin kontrolü hatası: {e}")
        return False

# Aktif oyunlar
active_games = {}

# Zamanlayıcı ve sürelerin takibi için
answer_timers = {}

# Bot komutları
@bot.message_handler(commands=['start', 'help', 'yardim'])
def start_command(message):
    register_user(message.from_user)
    
    if message.chat.type in ['group', 'supergroup']:
        register_group(message.chat)
        
        welcome_text = (
            "🎮 *Kim Milyoner Olmak İster - Grup Yarışma Botu*\n\n"
            "Grup Komutları:\n"
            "/yeniyarisma - Yeni bir yarışma başlat (sadece yöneticiler)\n"
            "/katil - Mevcut yarışmaya katıl\n"
            "/baslat - Yarışmayı başlat (sadece yaratıcı yönetici)\n"
            "/iptal - Yarışmayı iptal et (sadece yaratıcı yönetici)\n"
            "/durum - Yarışmanın mevcut durumunu göster\n\n"
            "Oyun hakkında:\n"
            "- Yarışma rauntlar halinde ilerler\n"
            "- Her rauntta kullanıcılara özel mesaj ile sorular gönderilir\n"
            "- Her soru için 30 saniye süre vardır\n"
            "- 2 yanlış cevap veren oyuncular elenir\n"
            "- Son oyuncu kalana kadar devam eder\n\n"
            "İyi eğlenceler! 🎯"
        )
    else:
        welcome_text = (
            "🎮 *Kim Milyoner Olmak İster - Bot*\n\n"
            "Bu bot grup yarışmaları için tasarlanmıştır.\n"
            "Lütfen beni bir gruba ekleyin ve orada /start komutunu kullanın.\n\n"
            "Özel sohbette şu komutları kullanabilirsiniz:\n"
            "/istatistik - Oyun istatistiklerinizi görüntüleyin"
        )
    
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=['yeniyarisma'])
def new_game_command(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "Bu komut sadece gruplarda kullanılabilir.")
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Yönetici kontrolü
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu sadece grup yöneticileri kullanabilir.")
        return
    
    register_user(message.from_user)
    register_group(message.chat)
    
    # Zaten aktif oyun var mı kontrol et
    if chat_id in active_games:
        bot.reply_to(message, "Bu grupta zaten aktif bir yarışma var. Önce onu iptal edin veya bitirin.")
        return
    
    # Komutta raunt sayısı belirtilmiş mi kontrol et
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        rounds = int(args[1])
        if rounds < 3 or rounds > 15:
            bot.reply_to(message, "Raunt sayısı 3 ile 15 arasında olmalıdır.")
            return
    else:
        rounds = 10  # Varsayılan raunt sayısı
    
    # Yeni oyun oturumu oluştur
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''
    INSERT INTO game_sessions (group_id, admin_id, start_time, total_rounds, status)
    VALUES (?, ?, ?, ?, ?)
    ''', (chat_id, user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), rounds, "waiting"))
    
    game_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # Aktif oyun verisini oluştur
    active_games[chat_id] = {
        "id": game_id,
        "admin_id": user_id,
        "total_rounds": rounds,
        "current_round": 0,
        "status": "waiting",
        "participants": {},
        "eliminated": {},
        "questions_asked": [],
        "round_results": {}
    }
    
    # Katılım butonu
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Yarışmaya Katıl", callback_data=f"join_game:{game_id}"))
    
    game_message = (
        f"🎮 *Yeni Yarışma Başlatıldı!*\n\n"
        f"Toplam Raunt: {rounds}\n"
        f"Yarışmacılar: 0\n\n"
        f"Katılmak için aşağıdaki butona tıklayın veya /katil komutunu kullanın.\n"
        f"Yarışma sahibi: {message.from_user.first_name}\n\n"
        f"Yeterince katılımcı olduğunda, yarışma sahibi /baslat komutu ile yarışmayı başlatabilir."
    )
    
    sent_message = bot.send_message(chat_id, game_message, reply_markup=markup, parse_mode="Markdown")
    
    # Mesaj ID'sini kaydet
    active_games[chat_id]["announcement_message_id"] = sent_message.message_id

@bot.message_handler(commands=['katil'])
def join_game_command(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "Bu komut sadece gruplarda kullanılabilir.")
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Aktif oyun var mı kontrol et
    if chat_id not in active_games:
        bot.reply_to(message, "Bu grupta aktif bir yarışma bulunmuyor. /yeniyarisma komutu ile yeni bir yarışma başlatabilirsiniz.")
        return
    
    game = active_games[chat_id]
    
    # Oyun durumu kontrol et
    if game["status"] != "waiting":
        bot.reply_to(message, "Yarışma kayıtları kapanmış veya yarışma zaten başlamış.")
        return
    
    # Kullanıcı zaten katılmış mı kontrol et
    if user_id in game["participants"]:
        bot.reply_to(message, "Zaten bu yarışmaya katıldınız.")
        return
    
    register_user(message.from_user)
    
    # Kullanıcıyı oyuna ekle
    game["participants"][user_id] = {
        "name": message.from_user.first_name,
        "username": message.from_user.username,
        "wrong_answers": 0,
        "correct_answers": 0,
        "current_question": None,
        "answered": False
    }
    
    # Veritabanına ekle
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''
    INSERT INTO game_participants (game_id, user_id, join_time)
    VALUES (?, ?, ?)
    ''', (game["id"], user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    conn.commit()
    conn.close()
    
    # Duyuru mesajını güncelle
    try:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Yarışmaya Katıl", callback_data=f"join_game:{game['id']}"))
        
        game_message = (
            f"🎮 *Yeni Yarışma Başlatıldı!*\n\n"
            f"Toplam Raunt: {game['total_rounds']}\n"
            f"Yarışmacılar: {len(game['participants'])}\n\n"
            f"Katılmak için aşağıdaki butona tıklayın veya /katil komutunu kullanın.\n"
            f"Yarışma sahibi: {bot.get_chat_member(chat_id, game['admin_id']).user.first_name}\n\n"
            f"Yeterince katılımcı olduğunda, yarışma sahibi /baslat komutu ile yarışmayı başlatabilir."
        )
        
        bot.edit_message_text(
            game_message,
            chat_id,
            game["announcement_message_id"],
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Mesaj güncelleme hatası: {e}")
    
    # Özel mesaj ile bilgilendir
    try:
        bot.send_message(
            user_id,
            f"*{message.chat.title}* grubundaki yarışmaya başarıyla katıldınız.\n\n"
            f"Yarışma başladığında, sorular size özel mesaj olarak gelecektir.\n"
            f"Her soru için 30 saniye süreniz olacaktır.\n"
            f"Lütfen bu sohbeti kapatmayın.",
            parse_mode="Markdown"
        )
        
        bot.reply_to(message, f"{message.from_user.first_name} yarışmaya katıldı! Toplam katılımcı: {len(game['participants'])}")
    except Exception as e:
        bot.reply_to(
            message,
            f"{message.from_user.first_name} yarışmaya katıldı, ancak özel mesaj gönderilemedi.\n"
            f"Lütfen önce botla özel sohbet başlatın: @{bot.get_me().username}"
        )

@bot.message_handler(commands=['baslat'])
def start_game_command(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "Bu komut sadece gruplarda kullanılabilir.")
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Aktif oyun var mı kontrol et
    if chat_id not in active_games:
        bot.reply_to(message, "Bu grupta aktif bir yarışma bulunmuyor. /yeniyarisma komutu ile yeni bir yarışma başlatabilirsiniz.")
        return
    
    game = active_games[chat_id]
    
    # Yarışmayı sadece oluşturan admin başlatabilir
    if user_id != game["admin_id"]:
        bot.reply_to(message, "Yarışmayı sadece oluşturan yönetici başlatabilir.")
        return
    
    # Oyun durumu kontrol et
    if game["status"] != "waiting":
        bot.reply_to(message, "Yarışma zaten başlamış veya iptal edilmiş.")
        return
    
    # Yeterli katılımcı var mı kontrol et
    if len(game["participants"]) < 2:
        bot.reply_to(message, "Yarışmayı başlatmak için en az 2 katılımcı gerekiyor.")
        return
    
    # Oyunu başlat
    game["status"] = "active"
    game["current_round"] = 1
    
    # Veritabanını güncelle
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''
    UPDATE game_sessions SET status = ?, current_round = ?
    WHERE id = ?
    ''', ("active", 1, game["id"]))
    
    conn.commit()
    conn.close()
    
    # Yarışma başlangıç duyurusu
    bot.send_message(
        chat_id,
        f"🎮 *Yarışma Başlıyor!*\n\n"
        f"Toplam {len(game['participants'])} yarışmacı ile 1. raunt başlıyor.\n"
        f"Sorular yarışmacılara özel mesaj olarak gönderilecek.\n"
        f"Her soru için 30 saniye süre vardır.\n\n"
        f"Her raunt sonrası sonuçlar burada paylaşılacaktır.",
        parse_mode="Markdown"
    )
    
    # İlk raundu başlat
    threading.Thread(target=start_round, args=(chat_id,)).start()

@bot.message_handler(commands=['iptal'])
def cancel_game_command(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "Bu komut sadece gruplarda kullanılabilir.")
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Aktif oyun var mı kontrol et
    if chat_id not in active_games:
        bot.reply_to(message, "Bu grupta aktif bir yarışma bulunmuyor.")
        return
    
    game = active_games[chat_id]
    
    # Yarışmayı sadece oluşturan admin veya grup yöneticisi iptal edebilir
    if user_id != game["admin_id"] and not is_admin(chat_id, user_id):
        bot.reply_to(message, "Yarışmayı sadece oluşturan yönetici veya grup yöneticileri iptal edebilir.")
        return
    
    # Oyunu iptal et
    end_game(chat_id, "cancelled")
    
    bot.reply_to(message, "Yarışma iptal edildi.")

@bot.message_handler(commands=['durum'])
def game_status_command(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "Bu komut sadece gruplarda kullanılabilir.")
        return
    
    chat_id = message.chat.id
    
    # Aktif oyun var mı kontrol et
    if chat_id not in active_games:
        bot.reply_to(message, "Bu grupta aktif bir yarışma bulunmuyor.")
        return
    
    game = active_games[chat_id]
    
    # Oyun durumunu hazırla
    if game["status"] == "waiting":
        status_msg = (
            f"🎮 *Yarışma Durumu*\n\n"
            f"Durum: Katılım açık\n"
            f"Toplam Raunt: {game['total_rounds']}\n"
            f"Katılımcılar: {len(game['participants'])}\n\n"
            f"Yarışma sahibi: {bot.get_chat_member(chat_id, game['admin_id']).user.first_name}"
        )
    elif game["status"] == "active":
        active_players = len(game["participants"]) - len(game["eliminated"])
        
        status_msg = (
            f"🎮 *Yarışma Durumu*\n\n"
            f"Durum: Aktif\n"
            f"Mevcut Raunt: {game['current_round']}/{game['total_rounds']}\n"
            f"Kalan Yarışmacılar: {active_players}\n"
            f"Elenenler: {len(game['eliminated'])}\n\n"
        )
        
        # Aktif oyuncuları listele
        if active_players > 0:
            status_msg += "*Kalan Yarışmacılar:*\n"
            count = 1
            for player_id, player in game["participants"].items():
                if player_id not in game["eliminated"]:
                    name = player["name"]
                    correct = player["correct_answers"]
                    status_msg += f"{count}. {name} - {correct} doğru\n"
                    count += 1
    else:
        status_msg = (
            f"🎮 *Yarışma Durumu*\n\n"
            f"Durum: Tamamlandı\n"
            f"Toplam Raunt: {game['current_round']}\n"
        )
        
        # Kazanan bilgisini ekle
        if "winner_id" in game and game["winner_id"]:
            winner = bot.get_chat_member(chat_id, game["winner_id"]).user
            status_msg += f"Kazanan: {winner.first_name}\n"
    
    bot.reply_to(message, status_msg, parse_mode="Markdown")

@bot.message_handler(commands=['istatistik'])
def stats_command(message):
    user_id = message.from_user.id
    
    conn = get_db()
    c = conn.cursor()
    
    # Kullanıcı istatistikleri
    c.execute('''
    SELECT games_played, total_rounds_passed, total_correct_answers, total_wins
    FROM users
    WHERE user_id = ?
    ''', (user_id,))
    
    user_stats = c.fetchone()
    
    if not user_stats:
        bot.reply_to(message, "Henüz hiç oyun oynamamışsınız.")
        conn.close()
        return
    
    stats_msg = (
        f"📊 *Oyun İstatistikleriniz*\n\n"
        f"Katıldığınız Oyunlar: {user_stats['games_played']}\n"
        f"Geçtiğiniz Rauntlar: {user_stats['total_rounds_passed']}\n"
        f"Doğru Cevaplar: {user_stats['total_correct_answers']}\n"
        f"Kazandığınız Oyunlar: {user_stats['total_wins']}\n\n"
    )
    
    # Son 5 oyun
    c.execute('''
    SELECT gs.start_time, gs.total_rounds, gp.eliminated_round
    FROM game_participants gp
    JOIN game_sessions gs ON gp.game_id = gs.id
    WHERE gp.user_id = ?
    ORDER BY gs.start_time DESC
    LIMIT 5
    ''', (user_id,))
    
    recent_games = c.fetchall()
    
    if recent_games:
        stats_msg += "*Son Oyunlarınız:*\n"
        for i, game in enumerate(recent_games):
            if game['eliminated_round']:
                result = f"{game['eliminated_round']}. rauntta elendiniz"
            else:
                result = "Tamamladınız"
            
            stats_msg += f"{i+1}. {game['start_time']} - {game['total_rounds']} raunt - {result}\n"
    
    conn.close()
    bot.send_message(message.chat.id, stats_msg, parse_mode="Markdown")

# Katılım butonu için callback
@bot.callback_query_handler(func=lambda call: call.data.startswith('join_game:'))
def join_game_callback(call):
    game_id = int(call.data.split(':')[1])
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # Aktif oyun var mı kontrol et
    if chat_id not in active_games or active_games[chat_id]["id"] != game_id:
        bot.answer_callback_query(call.id, "Bu yarışma artık aktif değil.")
        return
    
    game = active_games[chat_id]
    
    # Oyun durumu kontrol et
    if game["status"] != "waiting":
        bot.answer_callback_query(call.id, "Yarışma kayıtları kapanmış veya yarışma zaten başlamış.")
        return
    
    # Kullanıcı zaten katılmış mı kontrol et
    if user_id in game["participants"]:
        bot.answer_callback_query(call.id, "Zaten bu yarışmaya katıldınız.")
        return
    
    register_user(call.from_user)
    
    # Kullanıcıyı oyuna ekle
    game["participants"][user_id] = {
        "name": call.from_user.first_name,
        "username": call.from_user.username,
        "wrong_answers": 0,
        "correct_answers": 0,
        "current_question": None,
        "answered": False
    }
    
    # Veritabanına ekle
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''
    INSERT INTO game_participants (game_id, user_id, join_time)
    VALUES (?, ?, ?)
    ''', (game["id"], user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    conn.commit()
    conn.close()
    
    # Duyuru mesajını güncelle
    try:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Yarışmaya Katıl", callback_data=f"join_game:{game['id']}"))
        
        game_message = (
            f"🎮 *Yeni Yarışma Başlatıldı!*\n\n"
            f"Toplam Raunt: {game['total_rounds']}\n"
            f"Yarışmacılar: {len(game['participants'])}\n\n"
            f"Katılmak için aşağıdaki butona tıklayın veya /katil komutunu kullanın.\n"
            f"Yarışma sahibi: {bot.get_chat_member(chat_id, game['admin_id']).user.first_name}\n\n"
            f"Yeterince katılımcı olduğunda, yarışma sahibi /baslat komutu ile yarışmayı başlatabilir."
        )
        
        bot.edit_message_text(
            game_message,
            chat_id,
            game["announcement_message_id"],
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Mesaj güncelleme hatası: {e}")
    
    # Kullanıcıya katılım bilgisi
    try:
        bot.send_message(
            user_id,
            f"*{call.message.chat.title}* grubundaki yarışmaya başarıyla katıldınız.\n\n"
            f"Yarışma başladığında, sorular size özel mesaj olarak gelecektir.\n"
            f"Her soru için 30 saniye süreniz olacaktır.\n"
            f"Lütfen bu sohbeti kapatmayın.",
            parse_mode="Markdown"
        )
        
        bot.answer_callback_query(call.id, "Yarışmaya başarıyla katıldınız!")
        
        # Gruba bildirim
        bot.send_message(
            chat_id,
            f"{call.from_user.first_name} yarışmaya katıldı! Toplam katılımcı: {len(game['participants'])}"
        )
    except Exception as e:
        bot.answer_callback_query(
            call.id,
            "Yarışmaya katıldınız, ancak özel mesaj gönderilemedi. Lütfen önce botla özel sohbet başlatın.",
            show_alert=True
        )

# Soru cevaplama için callback
@bot.callback_query_handler(func=lambda call: call.data.startswith('answer:'))
def answer_callback(call):
    parts = call.data.split(':')
    game_id = int(parts[1])
    question_id = int(parts[2])
    answer = parts[3]
    user_id = call.from_user.id
    
    # Bu soru için doğru oyun ve kullanıcı mı kontrol et
    game_found = False
    for chat_id, game in active_games.items():
        if game["id"] == game_id:
            game_found = True
            if user_id in game["participants"] and user_id not in game["eliminated"]:
                player = game["participants"][user_id]
                
                # Soru doğru mu ve henüz cevap verilmemiş mi kontrol et
                if player["current_question"] == question_id and not player["answered"]:
                    player["answered"] = True
                    
                    # Zamanlayıcıyı durdur
                    timer_key = f"{user_id}_{question_id}"
                    if timer_key in answer_timers and answer_timers[timer_key].is_alive():
                        answer_timers[timer_key].cancel()
                        del answer_timers[timer_key]  # Zamanlayıcıyı sözlükten tamamen kaldır
                    
                    # Cevabı kontrol et
                    question = None
                    for q in questions_db[min(game["current_round"], 10)]:
                        if q.get("id") == question_id:
                            question = q
                            break
                    
                    if question and answer == question["correct"]:
                        player["correct_answers"] += 1
                        result_text = "✅ Doğru cevap!"
                    else:
                        player["wrong_answers"] += 1
                        if question:
                            result_text = f"❌ Yanlış cevap! Doğru cevap: {question['correct']}"
                        else:
                            result_text = "❌ Yanlış cevap!"
                    
                    # Cevap sonucunu bildir
                    try:
                        bot.edit_message_reply_markup(
                            chat_id=call.message.chat.id,
                            message_id=call.message.message_id,
                            reply_markup=None
                        )
                        
                        bot.send_message(
                            user_id,
                            result_text
                        )
                    except Exception as e:
                        logger.error(f"Cevap bildirme hatası: {e}")
                    
                    # Tüm oyuncular cevap verdi mi kontrol et
                    all_answered = True
                    for p_id, p in game["participants"].items():
                        if p_id not in game["eliminated"] and not p["answered"]:
                            all_answered = False
                            break
                    
                    if all_answered:
                        # Tüm oyuncular cevap vermiş, raunt tamamlanıyor
                        check_round_completion(chat_id)
                else:
                    bot.answer_callback_query(call.id, "Bu soruyu zaten cevapladınız veya sorunuz değişti.")
            else:
                bot.answer_callback_query(call.id, "Bu oyuna katılmadınız veya elendiniz.")
            break
    
    if not game_found:
        bot.answer_callback_query(call.id, "Bu oyun artık aktif değil.")
    else:
        bot.answer_callback_query(call.id)

# Cevap süre sonu fonksiyonu
def time_out_answer(chat_id, user_id, question_id):
    if chat_id not in active_games:
        return
    
    game = active_games[chat_id]
    
    if user_id not in game["participants"] or user_id in game["eliminated"]:
        return
    
    player = game["participants"][user_id]
    
    # Hala aynı soruyu mu çözüyor kontrol et
    if player["current_question"] != question_id or player["answered"]:
        return
    
    # Süre doldu, yanlış cevap olarak işaretle
    player["wrong_answers"] += 1
    player["answered"] = True
    
    # Kullanıcıya bildir
    try:
        question = None
        for q in questions_db[min(game["current_round"], 10)]:
            if q.get("id") == question_id:
                question = q
                break
                
        timeout_message = (
            f"⏱️ *Süre Doldu!*\n\n"
            f"Soruyu zamanında cevaplayamadınız.\n"
        )
        
        if question:
            timeout_message += f"Doğru cevap: {question['correct']}"
            
            # Mesajın klavyesini kaldırmaya çalış
            try:
                # Son mesajları bul
                messages = bot.get_updates()
                for msg in messages:
                    if hasattr(msg, 'message') and msg.message and msg.message.chat.id == user_id:
                        if hasattr(msg.message, 'reply_markup') and msg.message.reply_markup:
                            try:
                                bot.edit_message_reply_markup(
                                    chat_id=user_id,
                                    message_id=msg.message.message_id,
                                    reply_markup=None
                                )
                            except Exception:
                                pass
            except Exception as e:
                logger.error(f"Klavye kaldırma hatası: {e}")
        
        bot.send_message(user_id, timeout_message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Süre doldu bildirimi hatası: {e}")
    
    # Tüm oyuncular cevap verdi mi kontrol et
    all_answered = True
    for p_id, p in game["participants"].items():
        if p_id not in game["eliminated"] and not p["answered"]:
            all_answered = False
            break
    
    if all_answered:
        # Tüm oyuncular cevap vermiş, raunt tamamlanıyor
        check_round_completion(chat_id)

# Raunt başlatma fonksiyonu
def start_round(chat_id):
    if chat_id not in active_games:
        return
    
    game = active_games[chat_id]
    
    # Oyun durumu kontrol et
    if game["status"] != "active":
        return
    
    current_round = game["current_round"]
    
    # Zamanlayıcıları temizle
    for timer_key in list(answer_timers.keys()):
        if answer_timers[timer_key].is_alive():
            answer_timers[timer_key].cancel()
        del answer_timers[timer_key]
    
    # Raunt başlangıç duyurusu
    bot.send_message(
        chat_id,
        f"🎮 *Raunt {current_round} Başlıyor!*\n\n"
        f"Zorluk seviyesi: {current_round}/10\n"
        f"Kalan yarışmacılar: {len(game['participants']) - len(game['eliminated'])}\n\n"
        f"Sorular yarışmacılara özel mesaj olarak gönderildi. Her soru için 30 saniye süre vardır!",
        parse_mode="Markdown"
    )
    
    # Bu raunt için soruları hazırla
    round_questions = questions_db[min(current_round, 10)].copy()  # En fazla zorluk 10
    random.shuffle(round_questions)
    
    # Her katılımcı için durumu sıfırla
    for player_id, player in game["participants"].items():
        if player_id not in game["eliminated"]:
            player["answered"] = False
            player["current_question"] = None
    
    # Her katılımcıya soru gönder
    for player_id, player in game["participants"].items():
        if player_id not in game["eliminated"]:
            # Oyuncuya özel soru
            question = round_questions[0]
            # Soruya unique ID ekle
            question_id = int(time.time() * 1000) + random.randint(1, 1000)
            question["id"] = question_id
            
            # Oyuncunun mevcut sorusunu kaydet
            player["current_question"] = question_id
            
            # Soruyu gönder
            options = question["options"].copy()
            correct = question["correct"]
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            random.shuffle(options)  # Şıkları karıştır
            
            for option in options:
                markup.add(types.InlineKeyboardButton(
                    option,
                    callback_data=f"answer:{game['id']}:{question_id}:{option}"
                ))
            
            try:
                bot.send_message(
                    player_id,
                    f"*Raunt {current_round}, Soru:*\n\n{question['question']}\n\n⏱️ *Süre: 30 saniye*",
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
                # 30 saniyelik zamanlayıcı başlat
                timer = threading.Timer(30, time_out_answer, args=(chat_id, player_id, question_id))
                timer.daemon = True
                timer.start()
                
                # Zamanlayıcıyı kaydet
                timer_key = f"{player_id}_{question_id}"
                answer_timers[timer_key] = timer
                
            except Exception as e:
                logger.error(f"Soru gönderme hatası: {e}")
                # Oyuncuya mesaj gönderilemiyor, otomatik eleme?
                player["wrong_answers"] += 1
                player["answered"] = True
            
            # Sonraki oyuncu için farklı bir soru seç
            round_questions = round_questions[1:] + [round_questions[0]]
    
    # Soruları listeye ekle
    game["questions_asked"].extend(round_questions[:len(game["participants"]) - len(game["eliminated"])])
    
    # Her raunt için 90 saniyelik maksimum süre sınırı (tüm oyuncular cevap vermese bile)
    global overall_round_timer
    overall_round_timer = threading.Timer(90, force_round_completion, args=(chat_id,))
    overall_round_timer.daemon = True
    overall_round_timer.start()

# Raunt zorla tamamlama (maksimum süre dolduğunda)
def force_round_completion(chat_id):
    if chat_id not in active_games:
        return
    
    logger.info(f"Raunt için maksimum süre doldu: {chat_id}")
    
    # Cevap vermemiş oyuncuları kontrol et
    game = active_games[chat_id]
    
    for player_id, player in game["participants"].items():
        if player_id not in game["eliminated"] and not player["answered"]:
            # Süre doldu, yanlış sayılır
            player["wrong_answers"] += 1
            player["answered"] = True
            
            # Kullanıcıya bildir
            try:
                bot.send_message(
                    player_id,
                    "⏱️ *Raunt Süresi Doldu!*\n\nCevap vermediğiniz için bu soru yanlış sayıldı.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Raunt süresi doldu bildirimi hatası: {e}")
    
    # Raunt sonuçlarını hesapla
    check_round_completion(chat_id)

# Raunt tamamlanma kontrolü
def check_round_completion(chat_id):
    if chat_id not in active_games:
        return
    
    game = active_games[chat_id]
    
    # Genel raunt zamanlayıcısını iptal et
    if 'overall_round_timer' in globals() and globals()['overall_round_timer'].is_alive():
        globals()['overall_round_timer'].cancel()
    
    # Tüm oyuncular cevap verdi mi kontrol et - raunt tamamlanması için tüm oyuncuların cevap vermiş olması şart
    all_answered = True
    for player_id, player in game["participants"].items():
        if player_id not in game["eliminated"] and not player["answered"]:
            all_answered = False
            break
    
    if not all_answered:
        # Hala cevap verilmemiş, bekle
        return
    
    # Raunt sonuçlarını hesapla
    round_results = {
        "correct": 0,
        "wrong": 0,
        "eliminated": []
    }
    
    # Raunt sonuçlarını güncelle ve elenen oyuncuları belirle
    for player_id, player in game["participants"].items():
        if player_id not in game["eliminated"]:
            if player["current_question"] is not None:
                # Doğru cevap sayısı
                if player["correct_answers"] >= game["current_round"]:
                    round_results["correct"] += 1
                else:
                    round_results["wrong"] += 1
            
            # 2 yanlış cevap eleme kuralı
            if player["wrong_answers"] >= 2:
                round_results["eliminated"].append(player_id)
                game["eliminated"][player_id] = {
                    "round": game["current_round"],
                    "reason": "2 yanlış cevap"
                }
                
                # Veritabanını güncelle
                conn = get_db()
                c = conn.cursor()
                
                c.execute('''
                UPDATE game_participants
                SET eliminated_round = ?, eliminated_reason = ?
                WHERE game_id = ? AND user_id = ?
                ''', (game["current_round"], "2 yanlış cevap", game["id"], player_id))
                
                conn.commit()
                conn.close()
                
                # Oyuncuya bildir
                try:
                    bot.send_message(
                        player_id,
                        f"❌ *Elendiniz!*\n\n"
                        f"2 yanlış cevap verdiğiniz için {game['current_round']}. rauntta elendiniz.\n"
                        f"Toplam doğru cevap: {player['correct_answers']}\n\n"
                        f"Bir sonraki yarışmada daha iyi şanslar dileriz!",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Eleme bildirimi hatası: {e}")
    
    # Raunt sonuçlarını kaydet
    game["round_results"][game["current_round"]] = round_results
    
    # Raunt sonuçlarını gruba bildir
    result_msg = (
        f"🎮 *Raunt {game['current_round']} Sonuçları*\n\n"
        f"✅ Doğru cevap verenler: {round_results['correct']}\n"
        f"❌ Yanlış cevap verenler: {round_results['wrong']}\n"
        f"⛔ Elenenler: {len(round_results['eliminated'])}\n\n"
    )
    
    # Elenen oyuncuları listele
    if round_results["eliminated"]:
        result_msg += "*Elenen Yarışmacılar:*\n"
        for player_id in round_results["eliminated"]:
            player = game["participants"][player_id]
            result_msg += f"- {player['name']} ({player['correct_answers']} doğru cevap)\n"
    
    # Kalan oyuncuları listele
    active_players = []
    for player_id, player in game["participants"].items():
        if player_id not in game["eliminated"]:
            active_players.append((player_id, player))
    
    if active_players:
        result_msg += "\n*Kalan Yarışmacılar:*\n"
        for player_id, player in active_players:
            result_msg += f"- {player['name']} ({player['correct_answers']} doğru cevap)\n"
    
    bot.send_message(chat_id, result_msg, parse_mode="Markdown")
    
    # Oyun durumunu kontrol et
    active_player_count = len(game["participants"]) - len(game["eliminated"])
    
    if active_player_count == 0:
        # Kimse kalmadı, oyun bitti
        end_game(chat_id, "no_players")
    elif active_player_count == 1:
        # Sadece bir kişi kaldı, kazanan!
        winner_id = active_players[0][0]
        end_game(chat_id, "winner", winner_id)
    elif game["current_round"] >= game["total_rounds"]:
        # Maksimum raunt tamamlandı
        if active_player_count > 1:
            # En çok doğru cevabı olan kazanır
            best_player = max(active_players, key=lambda p: p[1]["correct_answers"])
            end_game(chat_id, "max_rounds", best_player[0])
        else:
            # Son kalan kişi kazanır
            end_game(chat_id, "max_rounds", active_players[0][0])
    else:
        # Bir sonraki raunda geç
        game["current_round"] += 1
        
        # Veritabanını güncelle
        conn = get_db()
        c = conn.cursor()
        
        c.execute('''
        UPDATE game_sessions SET current_round = ?
        WHERE id = ?
        ''', (game["current_round"], game["id"]))
        
        conn.commit()
        conn.close()
        
        # Biraz bekle ve sonraki raundu başlat
        time.sleep(5)
        threading.Thread(target=start_round, args=(chat_id,)).start()

# Oyun bitirme fonksiyonu
def end_game(chat_id, reason, winner_id=None):
    if chat_id not in active_games:
        return
    
    game = active_games[chat_id]
    
    # Tüm zamanlayıcıları iptal et
    for timer_key in list(answer_timers.keys()):
        if answer_timers[timer_key].is_alive():
            answer_timers[timer_key].cancel()
            del answer_timers[timer_key]
    
    # Oyun durumunu güncelle
    if reason == "winner":
        status = "completed"
        winner_message = f"🏆 *Tebrikler!* {bot.get_chat_member(chat_id, winner_id).user.first_name} yarışmayı kazandı!"
    elif reason == "max_rounds":
        status = "completed"
        if winner_id:
            winner_message = f"🏆 *Tebrikler!* {bot.get_chat_member(chat_id, winner_id).user.first_name} en yüksek puanla yarışmayı kazandı!"
        else:
            winner_message = "Yarışma sona erdi, ancak kazanan belirlenemedi."
    elif reason == "no_players":
        status = "completed"
        winner_message = "Tüm yarışmacılar elendi. Kazanan yok!"
    elif reason == "cancelled":
        status = "cancelled"
        winner_message = "Yarışma iptal edildi."
    else:
        status = "cancelled"
        winner_message = "Yarışma sona erdi."
    
    # Veritabanını güncelle
    conn = get_db()
    c = conn.cursor()
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute('''
    UPDATE game_sessions 
    SET status = ?, end_time = ?, winner_id = ?
    WHERE id = ?
    ''', (status, now, winner_id, game["id"]))
    
    # Kazanan istatistiklerini güncelle
    if winner_id and status == "completed":
        c.execute('''
        UPDATE users
        SET total_wins = total_wins + 1
        WHERE user_id = ?
        ''', (winner_id,))
    
    # Tüm katılımcıların istatistiklerini güncelle
    for player_id, player in game["participants"].items():
        # Oyun sayısını artır
        c.execute('''
        UPDATE users
        SET games_played = games_played + 1,
            total_rounds_passed = total_rounds_passed + ?,
            total_correct_answers = total_correct_answers + ?
        WHERE user_id = ?
        ''', (
            game["current_round"] if player_id not in game["eliminated"] else 
            game["eliminated"][player_id]["round"] - 1 if player_id in game["eliminated"] else 0,
            player["correct_answers"],
            player_id
        ))
    
    conn.commit()
    conn.close()
    
    # Oyun sonucunu gruba bildir
    final_msg = (
        f"🎮 *Yarışma Sona Erdi!*\n\n"
        f"{winner_message}\n\n"
        f"Toplam Raunt: {game['current_round']}/{game['total_rounds']}\n"
        f"Toplam Katılımcı: {len(game['participants'])}\n"
        f"Elenenler: {len(game['eliminated'])}\n\n"
    )
    
    # Son durum
    final_standings = []
    
    # Kazanan
    if winner_id and status == "completed":
        winner = game["participants"][winner_id]
        final_standings.append((winner_id, winner, "Kazanan"))
    
    # Diğer oyuncular (elenenler)
    for player_id, player in game["participants"].items():
        if player_id != winner_id:
            if player_id in game["eliminated"]:
                status_text = f"{game['eliminated'][player_id]['round']}. rauntta elendi"
            else:
                status_text = "Tamamladı"
            
            final_standings.append((player_id, player, status_text))
    
    # Puana göre sırala
    final_standings.sort(key=lambda p: p[1]["correct_answers"], reverse=True)
    
    # Sıralamayı ekle
    final_msg += "*Son Sıralama:*\n"
    for i, (player_id, player, status_text) in enumerate(final_standings):
        final_msg += f"{i+1}. {player['name']} - {player['correct_answers']} doğru - {status_text}\n"
    
    bot.send_message(chat_id, final_msg, parse_mode="Markdown")
    
    # Kazanana özel mesaj
    if winner_id and status == "completed":
        try:
            bot.send_message(
                winner_id,
                f"🏆 *Tebrikler! Yarışmayı Kazandınız!*\n\n"
                f"Toplam doğru cevap: {game['participants'][winner_id]['correct_answers']}\n"
                f"Tamamlanan raunt: {game['current_round']}\n\n"
                f"Gruba dön ve zaferinle övün!",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Kazanan bildirimi hatası: {e}")
    
    # Oyunu kaldır
    del active_games[chat_id]

# Ana fonksiyon
def main():
    try:
        # Soruları kontrol et
        for level in range(1, 11):
            file_path = os.path.join(QUESTIONS_DIR, f"level_{level}.json")
            if not os.path.exists(file_path):
                logger.error(f"{file_path} dosyası bulunamadı! Lütfen soru dosyalarını oluşturun.")
                print(f"{file_path} dosyası bulunamadı! Lütfen soru dosyalarını oluşturun.")
                return
        
        # Veritabanını başlat
        init_db()
        
        logger.info("Kim Milyoner Olmak İster Bot başlatılıyor...")
        print("Bot başlatıldı! Ctrl+C ile durdurun.")
        
        # Botu başlat
        bot.polling(none_stop=True, interval=0)
    
    except KeyboardInterrupt:
        print("Bot durduruldu!")
    
    except Exception as e:
        logger.error(f"Bot çalıştırma hatası: {e}")
        print(f"Hata: {e}")

if __name__ == "__main__":
    main()
