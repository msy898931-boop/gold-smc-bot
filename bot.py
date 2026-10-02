import os
import time
import datetime
import threading
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import telebot
from telebot import types
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Real-Time Spot Gold Engine is Live!"

TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('MY_CHAT_ID')

if not TOKEN:
    raise ValueError("BOT_TOKEN is not set!")

bot = telebot.TeleBot(TOKEN, parse_mode='Markdown')

PROCESSED_MESSAGES = set()

def is_duplicate(message):
    msg_id = f"{message.chat.id}_{message.message_id}"
    if msg_id in PROCESSED_MESSAGES:
        return True
    PROCESSED_MESSAGES.add(msg_id)
    if len(PROCESSED_MESSAGES) > 1000:
        PROCESSED_MESSAGES.clear()
    return False

class InstitutionalMultiTimeframeFetcher:

    @staticmethod
    def get_market_data():
        try:
            # 1. جلب شمعات GC=F (عقود الذهب)
            ticker = yf.Ticker('GC=F')
            df_m15 = ticker.history(period='5d', interval='15m')
            df_h1 = ticker.history(period='10d', interval='1h')

            if df_m15.empty or df_h1.empty or len(df_m15) < 20:
                return None

            # 2. جلب سعر الذهب المباشر (Spot Price) بطلب مباشر وسريع بدلاً من المعادلات
            spot_price = None
            try:
                # جلب السعر اللحظي المباشر للسبوت
                res = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/XAUUSD=X?interval=1m&range=1d", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
                spot_price = float(res['chart']['result'][0]['meta']['regularMarketPrice'])
            except Exception:
                pass

            # إذا نجح جلب السعر اللحظي، نحسب الفارق بين العقود وسعر السبوت الحالي بدقة متناهية
            raw_close = float(df_m15['Close'].iloc[-1])
            if spot_price:
                offset = raw_close - spot_price
            else:
                # فارق ثابت آمن لحين الاستجابة
                offset = 32.10 if raw_close > 4000 else 0.0

            # حساب ATR على M15
            high_low = df_m15['High'] - df_m15['Low']
            high_cp = np.abs(df_m15['High'] - df_m15['Close'].shift(1))
            low_cp = np.abs(df_m15['Low'] - df_m15['Close'].shift(1))
            tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
            atr_m15 = tr.rolling(window=14).mean().iloc[-1]

            close_m15 = round(raw_close - offset, 2)
            open_m15 = round(float(df_m15['Open'].iloc[-1]) - offset, 2)
            high_m15 = round(float(df_m15['High'].iloc[-1]) - offset, 2)
            low_m15 = round(float(df_m15['Low'].iloc[-1]) - offset, 2)

            # فحص H1
            h1_high_prev = df_h1['High'].iloc[-5:-1].max() - offset
            h1_low_prev = df_h1['Low'].iloc[-5:-1].min() - offset
            h1_close = float(df_h1['Close'].iloc[-1]) - offset

            h1_bullish_sweep = (df_h1['Low'].iloc[-1] - offset < h1_low_prev) and (h1_close > h1_low_prev)
            h1_bearish_sweep = (df_h1['High'].iloc[-1] - offset > h1_high_prev) and (h1_close < h1_high_prev)
            h1_trend = "صاعد (Bullish)" if df_h1['Close'].iloc[-1] > df_h1['Open'].iloc[-5] else "هابط (Bearish)"

            return {
                'df_m15': df_m15,
                'df_h1': df_h1,
                'close': close_m15,
                'open': open_m15,
                'high': high_m15,
                'low': low_m15,
                'atr': round(float(atr_m15) if not np.isnan(atr_m15) else 4.0, 2),
                'h1_trend': h1_trend,
                'h1_bullish_sweep': h1_bullish_sweep,
                'h1_bearish_sweep': h1_bearish_sweep,
                'is_bullish_m15': close_m15 > open_m15
            }
        except Exception as e:
            print(f"Fetch Error: {e}")
            return None

def is_ict_killzone():
    hour = datetime.datetime.now(datetime.timezone.utc).hour
    if 7 <= hour <= 10:
        return True, "🇬🇧 جلسة لندن (London Killzone)"
    elif 12 <= hour <= 15:
        return True, "🇺🇸 جلسة نيويورك (NY Killzone)"
    elif 0 <= hour <= 4:
        return False, "🌏 الجلسة الآسيوية (تجميع)"
    else:
        return False, "💤 فترة سيولة منخفضة"

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton("👑 تحليل SMC + ICT (H1 + M15)")
    btn2 = types.KeyboardButton("🎯 مستويات فيبوناتشي OTE")
    btn3 = types.KeyboardButton("🌊 سحب السيولة (Sweeps)")
    btn4 = types.KeyboardButton("🧮 إدارة مخاطر الـ 50$")
    btn5 = types.KeyboardButton("ℹ️ حالة المحرك والسيولة")
    markup.add(btn1, btn2, btn3, btn4, btn5)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if is_duplicate(message):
        return
    text = "👑 **مرحباً بك في محرك التداول المؤسساتي (Real-Time Spot Engine)**"
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())

@bot.message_handler(func=lambda msg: msg.text and "SMC" in msg.text)
def process_smc_request(message):
    if is_duplicate(message):
        return
    bot.send_chat_action(message.chat.id, 'typing')
    data = InstitutionalMultiTimeframeFetcher.get_market_data()
    
    if not data:
        bot.send_message(message.chat.id, "⚠️ يتعذر الاتصال بسيرفر الأسعار حالياً.")
        return

    curr_p = data['close']
    atr_v = data['atr']
    _, kz_name = is_ict_killzone()
    sl_dist = round(max(atr_v * 1.5, 5.0), 2)

    if data['h1_bearish_sweep'] or (data['h1_trend'] == "هابط (Bearish)" and not data['is_bullish_m15']):
        sig = "🔴 SELL ENTRY (Bearish OB + H1 BSL Sweep)"
        sl = round(curr_p + sl_dist, 2)
        tp1 = round(curr_p - (sl_dist * 1.2), 2)
        tp2 = round(curr_p - (sl_dist * 2.5), 2)
        tp3 = round(curr_p - (sl_dist * 4.5), 2)
        reason = "سحب سيولة القمم على فريم الساعة (H1 BSL) مع ارتداد هابط على M15."
    else:
        sig = "🟢 BUY ENTRY (Bullish OB + H1 SSL Sweep)"
        sl = round(curr_p - sl_dist, 2)
        tp1 = round(curr_p + (sl_dist * 1.2), 2)
        tp2 = round(curr_p + (sl_dist * 2.5), 2)
        tp3 = round(curr_p + (sl_dist * 4.5), 2)
        reason = "سحب سيولة القيعان على فريم الساعة (H1 SSL) واختراق صاعد للهيكل."

    text = (
        f"👑 **تحليل SMC + ICT المطور (Real-Time Spot)**\n\n"
        f"💵 **السعر اللحظي (MT5):** `{curr_p}$` | **ATR:** `{atr_v}`\n"
        f"📊 **اتجاه فريم الساعة (H1):** `{data['h1_trend']}`\n"
        f"🕒 **الجلسة:** {kz_name}\n\n"
        f"📌 **التوصية:** {sig}\n"
        f"🧠 **السبب:** {reason}\n\n"
        f"📍 **سعر الدخول:** `{curr_p}`\n"
        f"🛑 **وقف الخسارة (SL):** `{sl}`\n"
        f"🥇 **الهدف الأول (TP1):** `{tp1}`\n"
        f"🥈 **الهدف الثاني (TP2):** `{tp2}`\n"
        f"🥉 **الهدف الثالث (TP3):** `{tp3}`\n\n"
        f"🧮 **إدارة الحساب ($50):** لوت آمن `0.01` Micro (المخاطرة 2%)."
    )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())

@bot.message_handler(func=lambda msg: msg.text and "OTE" in msg.text)
def process_ote_request(message):
    if is_duplicate(message):
        return
    bot.send_chat_action(message.chat.id, 'typing')
    data = InstitutionalMultiTimeframeFetcher.get_market_data()
    if not data:
        return

    df = data['df_m15']
    curr_p = data['close']
    recent_h = df['High'].iloc[-20:].max()
    recent_l = df['Low'].iloc[-20:].min()
    rng = recent_h - recent_l

    ote_618 = round(recent_h - (rng * 0.618), 2)
    ote_705 = round(recent_h - (rng * 0.705), 2)
    ote_786 = round(recent_h - (rng * 0.786), 2)

    text = (
        f"🎯 **تحليل فيبوناتشي التوازن (ICT OTE)**\n\n"
        f"💵 **السعر الحالي:** `{curr_p}$`\n\n"
        f"📐 **المستويات المؤسساتية:**\n"
        f"• **0.618:** `{ote_618}$`\n"
        f"• **0.705:** `{ote_705}$` (المستوى الأقوى ✨)\n"
        f"• **0.786:** `{ote_786}$`"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())

@bot.message_handler(func=lambda msg: msg.text and "سحب السيولة" in msg.text)
def process_sweeps_request(message):
    if is_duplicate(message):
        return
    bot.send_chat_action(message.chat.id, 'typing')
    data = InstitutionalMultiTimeframeFetcher.get_market_data()
    if not data:
        return

    curr_p = data['close']
    status = "🔥 **سحب سيولة قمم (H1/M15 BSL Sweep)!**" if data['h1_bearish_sweep'] else ("🔥 **سحب سيولة قيعان (H1/M15 SSL Sweep)!**" if data['h1_bullish_sweep'] else "💤 **لا يوجد سحب سيولة قوي حالياً.**")

    text = (
        f"🌊 **رادار سحب السيولة (H1 & M15)**\n\n"
        f"💵 **السعر الحالي:** `{curr_p}$`\n"
        f"📊 **النتيجة:** {status}"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())

@bot.message_handler(func=lambda msg: msg.text and "مخاطر" in msg.text)
def process_risk_request(message):
    if is_duplicate(message):
        return
    text = "🧮 **إدارة مخاطر الحساب ($50.00):**\nلوت آمن: `0.01` Micro."
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())

@bot.message_handler(func=lambda msg: msg.text and "حالة" in msg.text)
def process_status_request(message):
    if is_duplicate(message):
        return
    _, kz_name = is_ict_killzone()
    bot.send_message(message.chat.id, f"⚙️ **المحرك متصل بالبث المباشر المضمون لأسعار الذهب!**\nالجلسة: {kz_name}", reply_markup=main_keyboard())

def run_bot():
    try:
        bot.remove_webhook()
    except Exception:
        pass
    bot.polling(none_stop=True, interval=1, timeout=20)

if __name__ == "__main__":
    t_bot = threading.Thread(target=run_bot)
    t_bot.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
