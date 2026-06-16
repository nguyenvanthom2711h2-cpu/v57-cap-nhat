import streamlit as st
import pandas as pd
import telebot
from datetime import datetime, timedelta
import time
import warnings
import os, sys, contextlib

# Import vnstock
try:
    from vnstock.api.quote import Quote
except ImportError:
    from vnstock import Quote

warnings.filterwarnings("ignore")

# ==========================================
# CẤU HÌNH GIAO DIỆN WEB
# ==========================================
st.set_page_config(page_title="Stock Screener Multi-TF", layout="wide")
st.title("🚀 Bộ Lọc Cổ Phiếu Đồng Thuận Multi-TF")

# Sidebar cấu hình
st.sidebar.header("Cấu hình hệ thống")
# Để trống Token nếu không muốn dùng Telegram
TOKEN = st.sidebar.text_input("Telegram Token", value="8958414448:AAETDsuT0ut2gznqgvSzJbT62pgNKnlBxLE", type="password")
CHAT_ID = st.sidebar.text_input("Telegram Chat ID", value="6095817110")

SYMBOLS_TO_SCAN = [
    'ACB','BCM','BID','BVH','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','PLX','POW','SAB',
    'SHB','SSB','SSI','STB','TCB','TPB','VCB','VHM','VIB','VIC','VJC','VNM','VPB','VRE','LPB','DGC',
    'DPM','DCM','VGC','PVD','PVS','NLG','KDH','KBC','IDC','SZC','GMD','HAH','OIL','FRT','PNJ','TLG',
    'BSI','HSG','NKG','DIG','DXG','PDR','NVL','VIX','VCK','TCX','DGW','VND','HCM','VCI','EIB','MSB',
    'OCB','REE','CTR','VGI','VTP'
]

SCAN_PAIRS = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]

@contextlib.contextmanager
def mute_stdout():
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try: yield
        finally: sys.stdout = old_stdout

# ==========================================
# 2. HÀM TÍNH TOÁN (Giữ nguyên bản gốc của bạn)
# ==========================================
def calculate_indicators(df):
    if df is None or len(df) < 50: return 0, 0
    try:
        df = df.copy()
        delta = df['c'].diff()
        gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        df['rsi'] = 100 - (100 / (1 + avg_gain / avg_loss))
        df['rsi9'] = df['rsi'].rolling(9).mean()
        df['rsi45'] = df['rsi'].rolling(45).mean()
        
        last = df.iloc[-1]
        status = 0
        if last['rsi'] > last['rsi9'] and last['rsi'] > last['rsi45']: status = 1
        elif last['rsi'] < last['rsi9'] and last['rsi'] < last['rsi45']: status = -1
        return status, last['c']
    except: return 0, 0

def resample_stock_data(df, rule):
    if df is None or len(df) < 2: return None
    df['ts'] = pd.to_datetime(df['ts'])
    df.set_index('ts', inplace=True)
    logic = {'o':'first', 'h':'max', 'l':'min', 'c':'last', 'v':'sum'}
    return df.resample(rule).apply(logic).dropna().reset_index()

# ==========================================
# 3. QUY TRÌNH QUÉT
# ==========================================
def run_automated_screener():
    now_str = datetime.now().strftime('%H:%M:%S')
    summary_data = {}
    
    # Tạo khu vực hiển thị trạng thái
    status_area = st.empty()
    progress_bar = st.progress(0)
    
    # Tạo bot nếu có token
    bot = None
    if TOKEN and CHAT_ID:
        try: bot = telebot.TeleBot(TOKEN)
        except: pass

    total_steps = len(SCAN_PAIRS) * len(SYMBOLS_TO_SCAN)
    current_step = 0

    for tf1, tf2 in SCAN_PAIRS:
        tf_label = f"{tf1.upper()}-{tf2.upper()}"
        
        for symbol in SYMBOLS_TO_SCAN:
            current_step += 1
            progress_bar.progress(current_step / total_steps)
            status_area.write(f"🔍 Đang lọc {tf_label}: **{symbol}**...")
            
            try:
                with mute_stdout():
                    q = Quote(symbol=symbol, source='VCI')
                    
                    def get_tf_data(tf):
                        if 'h' in tf.lower():
                            df = q.history(start=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'), interval='1H')
                            df = df.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})
                            if tf.lower() == '1h': return df
                            return resample_stock_data(df, '4H')
                        else:
                            df = q.history(start='2022-01-01', interval='1D')
                            df = df.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})
                            if tf.lower() == '1d': return df
                            rule_map = {'3d':'3D','1w':'W-MON'}
                            return resample_stock_data(df, rule_map.get(tf.lower(), '1D'))

                    df1 = get_tf_data(tf1)
                    df2 = get_tf_data(tf2)

                    stat1, p1 = calculate_indicators(df1)
                    stat2, p2 = calculate_indicators(df2)

                    if stat1 == stat2 and stat1 != 0:
                        side = "BUY" if stat1 == 1 else "SELL"
                        display_price = p1 if p1 > 1000 else p1 * 1000
                        
                        if symbol not in summary_data:
                            summary_data[symbol] = {'price': display_price, 'buy': [], 'sell': []}
                        
                        if side == "BUY":
                            summary_data[symbol]['buy'].append(tf_label)
                        else:
                            summary_data[symbol]['sell'].append(tf_label)

                        # Gửi Telegram
                        if bot:
                            try:
                                msg = (f"{'🚀 MUA' if side=='BUY' else '🔻 BÁN'} ĐỒNG THUẬN\n"
                                       f"Mã: {symbol} | Khung: {tf_label} | Giá: {display_price:,.0f}")
                                bot.send_message(CHAT_ID, msg)
                            except: pass
            except: continue

    status_area.empty()
    return summary_data

# ==========================================
# NÚT BẤM VÀ HIỂN THỊ
# ==========================================
if st.button("🚀 BẮT ĐẦU QUÉT TOÀN BỘ MÃ"):
    with st.spinner("Đang tính toán RSI đồng thuận..."):
        results = run_automated_screener()
        
        if results:
            st.subheader(f"📊 BẢNG TỔNG HỢP [{datetime.now().strftime('%H:%M:%S')}]")
            
            final_rows = []
            for sym in sorted(results.keys()):
                data = results[sym]
                final_rows.append({
                    "MÃ": sym,
                    "GIÁ": f"{data['price']:,.0f}",
                    "ĐỒNG THUẬN MUA (🚀)": ", ".join(data['buy']) if data['buy'] else "-",
                    "ĐỒNG THUẬN BÁN (🔻)": ", ".join(data['sell']) if data['sell'] else "-"
                })
            
            st.dataframe(pd.DataFrame(final_rows), use_container_width=True)
        else:
            st.warning("Không tìm thấy mã đồng thuận nào.")

st.info("Hướng dẫn: Nhấn nút phía trên để bắt đầu chu kỳ quét. Code sẽ quét qua 4 cặp khung thời gian và gộp kết quả theo mã cổ phiếu.")
