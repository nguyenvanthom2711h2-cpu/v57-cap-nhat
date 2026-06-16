import streamlit as st
import pandas as pd
import telebot
from datetime import datetime, timedelta
import time
import warnings
import os

# Import vnstock
try:
    from vnstock.api.quote import Quote
except ImportError:
    from vnstock import Quote

warnings.filterwarnings("ignore")

# ==========================================
# CẤU HÌNH STREAMLIT UI
# ==========================================
st.set_page_config(page_title="Stock Screener Dashboard", layout="wide")
st.title("🚀 Hệ thống Lọc Cổ phiếu Đồng thuận Multi-TF")

# Sử dụng Sidebar để cấu hình (hoặc dùng st.secrets khi đẩy lên web)
TOKEN = st.sidebar.text_input("Telegram Token", value="8958414448:AAETDsuT0ut2gznqgvSzJbT62pgNKnlBxLE", type="password")
CHAT_ID = st.sidebar.text_input("Telegram Chat ID", value="6095817110")
bot = telebot.TeleBot(TOKEN)

WAIT_TIME = st.sidebar.slider("Thời gian nghỉ giữa các chu kỳ (giây)", 300, 3600, 900)

SYMBOLS_TO_SCAN = [
    'ACB','BCM','BID','BVH','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','PLX','POW','SAB',
    'SHB','SSB','SSI','STB','TCB','TPB','VCB','VHM','VIB','VIC','VJC','VNM','VPB','VRE','LPB','DGC',
    'DPM','DCM','VGC','PVD','PVS','NLG','KDH','KBC','IDC','SZC','GMD','HAH','OIL','FRT','PNJ','TLG',
    'BSI','HSG','NKG','DIG','DXG','PDR','NVL','VIX','VCK','TCX','DGW','VND','HCM','VCI','EIB','MSB',
    'OCB','REE','CTR','VGI','VTP'
]

SCAN_PAIRS = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]

# ==========================================
# HÀM LOGIC (Giữ nguyên từ bản cũ)
# ==========================================
def calculate_indicators(df):
    if df is None or len(df) < 50: return 0, 0
    df = df.copy()
    delta = df['c'].diff()
    gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + avg_gain / avg_loss))
    df['rsi9'] = df['rsi'].rolling(9).mean()
    df['rsi45'] = df['rsi'].rolling(45).mean()
    last = df.iloc[-1]
    status = 1 if (last['rsi'] > last['rsi9'] and last['rsi'] > last['rsi45']) else (-1 if (last['rsi'] < last['rsi9'] and last['rsi'] < last['rsi45']) else 0)
    return status, last['c']

def resample_stock_data(df, rule):
    df['ts'] = pd.to_datetime(df['ts'])
    df.set_index('ts', inplace=True)
    logic = {'o':'first', 'h':'max', 'l':'min', 'c':'last', 'v':'sum'}
    return df.resample(rule).apply(logic).dropna().reset_index()

# ==========================================
# QUY TRÌNH QUÉT
# ==========================================
def run_screener():
    summary_data = {}
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    total_steps = len(SCAN_PAIRS) * len(SYMBOLS_TO_SCAN)
    current_step = 0

    for tf1, tf2 in SCAN_PAIRS:
        tf_label = f"{tf1.upper()}-{tf2.upper()}"
        for symbol in SYMBOLS_TO_SCAN:
            current_step += 1
            progress_bar.progress(current_step / total_steps)
            status_text.text(f"🔍 Đang quét {tf_label}: {symbol}...")
            
            try:
                q = Quote(symbol=symbol, source='VCI')
                def get_data(tf):
                    if 'h' in tf.lower():
                        df = q.history(start=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'), interval='1H')
                        df = df.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})
                        return df if tf.lower() == '1h' else resample_stock_data(df, '4H')
                    else:
                        df = q.history(start='2022-01-01', interval='1D')
                        df = df.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})
                        if tf.lower() == '1d': return df
                        return resample_stock_data(df, '3D' if tf.lower()=='3d' else 'W-MON')
                
                df1, df2 = get_data(tf1), get_data(tf2)
                s1, p1 = calculate_indicators(df1)
                s2, p2 = calculate_indicators(df2)

                if s1 == s2 and s1 != 0:
                    side = "BUY" if s1 == 1 else "SELL"
                    price = p1 if p1 > 1000 else p1 * 1000
                    if symbol not in summary_data:
                        summary_data[symbol] = {'Giá': price, 'MUA (🚀)': [], 'BÁN (🔻)': []}
                    
                    if side == "BUY": summary_data[symbol]['MUA (🚀)'].append(tf_label)
                    else: summary_data[symbol]['BÁN (🔻)'].append(tf_label)
            except: continue

    return summary_data

# ==========================================
# GIAO DIỆN CHÍNH
# ==========================================
if st.sidebar.button("Bắt đầu Quét thủ công"):
    results = run_screener()
    if results:
        df_display = []
        for s, d in results.items():
            df_display.append([s, f"{d['Giá']:,.0f}", ", ".join(d['MUA (🚀)']), ", ".join(d['BÁN (🔻)'])])
        
        st.success(f"Cập nhật lúc: {datetime.now().strftime('%H:%M:%S')}")
        st.table(pd.DataFrame(df_display, columns=["MÃ", "GIÁ", "ĐỒNG THUẬN MUA", "ĐỒNG THUẬN BÁN"]))
    else:
        st.warning("Không có tín hiệu nào.")

st.info("Lưu ý: Để chạy tự động 24/7 và gửi Telegram, Streamlit Cloud không phải là nơi lý tưởng nhất (nó sẽ ngủ nếu không có người xem). Bạn nên dùng Render, Railway hoặc VPS.")
