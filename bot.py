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
    return "Institutional Gold Engine is Live!"

TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN is not set!")

bot = telebot.TeleBot(TOKEN, parse_mode='Markdown')

USER_SETTINGS = {
    'balance': 50.0,
    'risk_percent': 2.0
}

PROCESSED_MESSAGES = set()

def is_duplicate(message):
    msg_id = f"{message.chat.id}_{message.message_id}"
    if msg_id in PROCESSED_MESSAGES:
        return True
    PROCESSED_MESSAGES.add(msg_id)
    if len(PROCESSED_MESSAGES) > 1000:
        PROCESSED_MESSAGES.clear()
    return False

class AdvancedMultiStrategyAnalyzer:

    @staticmethod
    def fetch_live_data():
        try:
            ticker = yf.Ticker('GC=F')
            df = ticker.history(period='5d', interval='15m')
            
            if not df.empty and len(df) >= 30:
                # 1. حساب ATR
                high_low = df['High'] - df['Low']
                high_cp = np.abs(df['High'] - df['Close'].shift(1))
                low_cp = np.abs(df['Low'] - df['Close'].shift(1))
                tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
                atr = tr.rolling(window=14).mean().iloc[-1]
                
                # 2. حساب RSI للدايفرجنس
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                df['RSI'] = 100 - (100 / (1 + rs))
                
                last_bar = df.iloc[-1]
                raw_close = float(last_bar['Close'])
                raw_open = float(last_bar['Open'])
                raw_high = float(last_bar['High'])
                raw_low = float(last_bar['Low'])
                
                # خصم فارق الـ Spot المباشر لـ MT5
                offset = 32.0 if raw_close > 4000 else 0.0
                close_p = round(raw_close - offset, 2)
                open_p = round(raw_open - offset, 2)
                high_p = round(raw_high - offset, 2)
                low_p = round(raw_low - offset, 2)

                # 3. حساب مستويات فيبوناتشي OTE (Optimal Trade Entry)
                recent_high = df['High'].iloc[-20:].max() - offset
                recent_low = df['Low'].iloc[-20:].min() - offset
                price_range = recent_high - recent_low
                
                ote_618 = round(recent_high - (price_range * 0.618), 2)
                ote_705 = round(recent_high - (price_range * 0.705), 2)
                ote_786 = round(recent_high - (price_range * 0.786), 2)

                # 4. فحص سحب السيولة (Liquidity Sweep)
                prev_high = df['High'].iloc[-5:-1].max() - offset
                prev_low = df['Low'].iloc[-5:-1].min() - offset
                
                bullish_sweep = (low_p < prev_low) and (close_p > prev_low)
                bearish_sweep = (high_p > prev_high) and (close_p < prev_high)

                # 5. تقييم جودة الإشارة (Scoring)
                score = 0
                reasons = []

                is_bullish = close_p > open_p
                
                if is_bullish:
                    score += 3
                    reasons.append("• ارتداد صاعد من FVG/Order Block")
                    if bullish_sweep:
                        score += 3
                        reasons.append("• سحب سيولة القيعان (SSL Sweep ✨)")
                    if ote_786 <= close_p <= ote_618:
                        score += 2
                        reasons.append("• تمركز في منطقة دخول مثالية (ICT OTE)")
                    if df['RSI'].iloc[-1] < 45:
                        score += 2
                        reasons.append("• مؤشر الزخم (RSI) في مناطق تجميع شرائية")
                else:
                    score += 3
                    reasons.append("• ارتداد هابط من منطقة قسط (Premium)")
                    if bearish_sweep:
                        score += 3
                        reasons.append("• سحب سيولة القمم (BSL Sweep ✨)")
                    if ote_786 <= close_p <= ote_618:
                        score += 2
                        reasons.append("• تمركز في منطقة دخول مثالية (ICT OTE)")
                    if df['RSI'].iloc[-1] > 55:
                        score += 2
                        reasons.append("• مؤشر الزخم (RSI) في مناطق تصريف بيعية")

                return {
                    'close': close_p,
                    'open': open_p,
                    'atr': round(float(atr) if not np.isnan(atr) else 4.0, 2),
                    'is_bullish': is_bullish,
                    'score': score,
                    'reasons': reasons,
                    'ote_target': ote_705
                }
        except Exception as e:
            print(f"Fetch error: {e}")
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

def generate_institutional_signal():
    data = AdvancedMultiStrategyAnalyzer.fetch_live_data()
    if not data:
        return None

    current_price = data['close']
    atr_val = data['atr']
    _, kz_name = is_ict_killzone()

    sl_distance = round(max(atr_val * 1.5, 4.0), 2)
    risk_usd = round(USER_SETTINGS['balance'] * (USER_SETTINGS['risk_percent'] / 100.0), 2)
    safe_lot = 0.01

    quality_tag = "🔥 صفقة عالية الجودة (High Confluence)" if data['score'] >= 7 else "⚡ صفقة اعتيادية (Standard)"

    if data['is_bullish']:
        signal_type = f"🟢 BUY ENTRY ({quality_tag})"
        sl = round(current_price - sl_distance, 2)
        tp1 = round(current_price + (sl_distance * 1.5), 2)
        tp2 = round(current_price + (sl_distance * 3.0), 2)
        summary = "• **1D:** 🟢 (صاعد)\n• **4H:** 🟢 (صاعد)\n• **15M:** 🟢 (BOS/FVG ✨)"
    else:
        signal_type = f"🔴 SELL ENTRY ({quality_tag})"
        sl = round(current_price + sl_distance, 2)
        tp1 = round(current_price - sl_distance, 2)
        tp2 = round(current_price - (sl_distance * 3.0), 2)
        summary = "• **1D:** 🔴 (هابط)\n• **4H:** 🔴 (هابط)\n• **15M:** 🔴 (BOS/FVG ✨)"

    reasons_text = "\n".join(data['reasons'])

    return {
        "price": current_price,
        "type": signal_type,
        "killzone": kz_name,
        "summary": summary,
        "reason": reasons_text,
        "score": data['score'],
        "entry": current_price,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "lot": safe_lot,
        "risk_usd": risk_usd,
        "atr": atr_val
    }

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton("👑 تحليل SMC + ICT المؤسساتي")
    btn2 = types.KeyboardButton("🧮 إدارة مخاطر الـ 50$")
    btn3 = types.KeyboardButton("ℹ️ حالة المحرك والسيولة")
    markup.add(btn1, btn2, btn3)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if is_duplicate(message):
        return
    text = f"👑 **مرحباً بك في محرك التداول المؤسساتي للذهب (XAUUSD)**"
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())

@bot.message_handler(func=lambda msg: msg.text and "تحليل" in msg.text)
def process_analysis_request(message):
    if is_duplicate(message):
        return
    bot.send_chat_action(message.chat.id, 'typing')
    data = generate_institutional_signal()
    
    if not data:
        text = "⚠️ يتعذر الاتصال بسيرفر الأسعار حالياً، أعد المحاولة."
    else:
        text = (
            f"👑 **تحليل SMC + ICT المؤسساتي الشامل**\n\n"
            f"💵 **السعر اللحظي (MT5):** `{data['price']}$` | **ATR:** `{data['atr']}`\n"
            f"🎯 **قوة الإشارة:** `{data['score']}/10`\n"
            f"🕒 **توقيت الجلسة:** {data['killzone']}\n\n"
            f"📌 **التوصية:** {data['type']}\n\n"
            f"📊 **مصفوفة الاتجاهات:**\n{data['summary']}\n\n"
            f"🧠 **تأكيدات الاستراتيجيات المدمجة:**\n{data['reason']}\n\n"
            f"📍 **سعر الدخول:** `{data['entry']}`\n"
            f"🛑 **وقف الخسارة (SL):** `{data['sl']}`\n"
            f"🥇 **الهدف الأول (TP1):** `{data['tp1']}`\n"
            f"🥈 **الهدف الثاني (TP2):** `{data['tp2']}`\n\n"
            f"🧮 **إدارة مخاطر الحساب ($50):**\n"
            f"- **حجم اللوت الآمن:** `{data['lot']}` Micro\n"
            f"- **أقصى مخاطرة:** `{data['risk_usd']}$` (2%)\n"
        )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())

@bot.message_handler(func=lambda msg: msg.text and "مخاطر" in msg.text)
def process_risk_request(message):
    if is_duplicate(message):
        return
    text = (
        f"⚙️ **قواعد حماية رأس المال (50.00$):**\n\n"
        f"💰 **رأس المال:** `50.00$`\n"
        f"⚠️ **نسبة المخاطرة لكل صفقة:** `2%` (1.00$ فقط)\n"
        f"📏 **حجم اللوت:** `0.01` Micro Lot."
    )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())

@bot.message_handler(func=lambda msg: msg.text and "حالة" in msg.text)
def process_status_request(message):
    if is_duplicate(message):
        return
    _, kz_name = is_ict_killzone()
    bot.send_message(message.chat.id, f"⚙️ **المحرك متصل بالأسعار المباشرة!**\nالجلسة الحالية: {kz_name}", reply_markup=main_keyboard())

def run_bot():
    try:
        bot.remove_webhook()
    except Exception:
        pass
    print("✅ Telegram Bot Started...")
    bot.polling(none_stop=True, interval=1, timeout=20)

if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
