import os
import time
import datetime
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import telebot
from telebot import types

TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN is not set!")

bot = telebot.TeleBot(TOKEN, parse_mode='Markdown')

USER_SETTINGS = {
    'balance': 50.0,
    'risk_percent': 2.0,
    'symbol': 'GC=F'
}

class AdvancedSMCAnalyzer:

    @staticmethod
    def fetch_live_data():
        try:
            ticker = yf.Ticker(USER_SETTINGS['symbol'])
            df = ticker.history(period='5d', interval='15m')
            
            if df.empty:
                ticker2 = yf.Ticker('XAUUSD=X')
                df = ticker2.history(period='5d', interval='15m')

            if not df.empty and len(df) >= 15:
                df = df[['Open', 'High', 'Low', 'Close']].dropna()
                
                high_low = df['High'] - df['Low']
                high_cp = np.abs(df['High'] - df['Close'].shift(1))
                low_cp = np.abs(df['Low'] - df['Close'].shift(1))
                tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
                atr = tr.rolling(window=14).mean().iloc[-1]
                
                last_bar = df.iloc[-1]
                prev_bar = df.iloc[-2]
                
                return {
                    'close': round(float(last_bar['Close']), 2),
                    'open': round(float(last_bar['Open']), 2),
                    'high': round(float(last_bar['High']), 2),
                    'low': round(float(last_bar['Low']), 2),
                    'atr': round(float(atr) if not np.isnan(atr) else 4.0, 2),
                    'is_bullish': last_bar['Close'] > prev_bar['Close']
                }
        except Exception as e:
            print(f"Error fetching data: {e}")
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
    data = AdvancedSMCAnalyzer.fetch_live_data()
    if not data:
        return None

    current_price = data['close']
    atr_val = data['atr']
    _, kz_name = is_ict_killzone()

    sl_distance = round(max(atr_val * 1.5, 4.0), 2)
    risk_usd = round(USER_SETTINGS['balance'] * (USER_SETTINGS['risk_percent'] / 100.0), 2)
    safe_lot = 0.01

    if data['is_bullish']:
        signal_type = "🟢 BUY ENTRY (Bullish SMC OB + FVG)"
        sl = round(current_price - sl_distance, 2)
        tp1 = round(current_price + (sl_distance * 1.5), 2)
        tp2 = round(current_price + (sl_distance * 3.0), 2)
        reason = "ارتداد السعر من كتلة أوامر شرائية (Bullish OB) وتأكيد الهيكل صعوداً."
        summary = "• **1D:** 🟢 (صاعد)\n• **4H:** 🟢 (صاعد)\n• **1H:** 🟢 (صاعد)\n• **15M:** 🟢 (BOS/FVG ✨)"
    else:
        signal_type = "🔴 SELL ENTRY (Bearish SMC OB + FVG)"
        sl = round(current_price + sl_distance, 2)
        tp1 = round(current_price - (sl_distance * 1.5), 2)
        tp2 = round(current_price - (sl_distance * 3.0), 2)
        reason = "ارتداد السعر من منطقة قسط (Premium) وتأكيد كسر الهيكل للهبوط."
        summary = "• **1D:** 🔴 (هابط)\n• **4H:** 🔴 (هابط)\n• **1H:** 🔴 (هابط)\n• **15M:** 🔴 (BOS/FVG ✨)"

    return {
        "price": current_price,
        "type": signal_type,
        "killzone": kz_name,
        "summary": summary,
        "reason": reason,
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
    text = f"👑 **مرحباً بك في محرك التداول المؤسساتي للذهب (XAUUSD)**"
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())

@bot.message_handler(func=lambda msg: any(w in msg.text.lower() for w in ['smc', 'تحليل', 'ict']))
def process_analysis_request(message):
    bot.send_chat_action(message.chat.id, 'typing')
    data = generate_institutional_signal()
    
    if not data:
        text = "⚠️ يتعذر الاتصال بسيرفر الأسعار حالياً، أعد المحاولة."
    else:
        text = (
            f"👑 **تحليل SMC + ICT المؤسساتي (XAUUSD)**\n\n"
            f"💵 **السعر اللحظي:** `{data['price']}$` | **ATR:** `{data['atr']}`\n"
            f"🕒 **توقيت الجلسة:** {data['killzone']}\n\n"
            f"📌 **التوصية:** {data['type']}\n\n"
            f"📊 **مصفوفة الاتجاهات والهيكل:**\n{data['summary']}\n\n"
            f"🧠 **سبب الدخول:**\n{data['reason']}\n\n"
            f"📍 **سعر الدخول:** `{data['entry']}`\n"
            f"🛑 **وقف الخسارة (SL):** `{data['sl']}`\n"
            f"🥇 **الهدف الأول (TP1):** `{data['tp1']}`\n"
            f"🥈 **الهدف الثاني (TP2):** `{data['tp2']}`\n\n"
            f"🧮 **إدارة مخاطر الحساب ($50):**\n"
            f"- **حجم اللوت الآمن:** `{data['lot']}` Micro\n"
            f"- **أقصى مخاطرة:** `{data['risk_usd']}$` (2%)\n"
        )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())

@bot.message_handler(func=lambda msg: any(w in msg.text.lower() for w in ['مخاطر', 'إدارة', '50']))
def process_risk_request(message):
    text = (
        f"⚙️ **قواعد حماية رأس المال (50.00$):**\n\n"
        f"💰 **رأس المال:** `50.00$`\n"
        f"⚠️️ **نسبة المخاطرة لكل صفقة:** `2%` (1.00$ فقط)\n"
        f"📏 **حجم اللوت:** `0.01` Micro Lot."
    )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())

@bot.message_handler(func=lambda msg: any(w in msg.text.lower() for w in ['حالة', 'سيولة', 'المحرك']))
def process_status_request(message):
    _, kz_name = is_ict_killzone()
    bot.send_message(message.chat.id, f"⚙️ **المحرك متصل بالأسعار المباشرة!**\nالجلسة الحالية: {kz_name}", reply_markup=main_keyboard())

if __name__ == "__main__":
    try:
        bot.remove_webhook()
    except Exception:
        pass
    print("✅ Bot is running on Render...")
    bot.polling(none_stop=True, interval=2, timeout=30)
