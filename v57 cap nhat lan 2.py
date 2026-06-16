import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import warnings

# Tắt các cảnh báo không cần thiết
warnings.filterwarnings("ignore")

# Thử import thư viện vnstock
try:
    from vnstock import stock_historical_data
except ImportError:
    st.error("❌ Chưa cài đặt vnstock. Hãy kiểm tra lại file requirements.txt")
    st.stop()

# --- CẤU HÌNH ---
st.set_page_config(page_title="VnStock Screener", layout="wide")
st.title("🚀 Bộ Lọc Chứng Khoán Multi-TF")
st.caption("Phiên bản tự động sửa lỗi kết nối - Tương thích Streamlit Cloud")

# Danh sách mã (Rút gọn để quét nhanh, bạn có thể thêm lại sau)
SYMBOLS = [
    'ACB','BID','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','PLX','POW','SAB',
    'SHB','SSB','SSI','STB','TCB','TPB','VCB','VHM','VIB','VIC','VJC','VNM','VPB','VRE','LPB','DGC',
    'DPM','DCM','VGC','PVD','PVS','NLG','KDH','KBC','IDC','SZC','GMD','HAH','OIL','FRT','PNJ'
]

# --- HÀM TÍNH TOÁN RSI ---
def calculate_signals(df):
    if df is None or len(df) < 50: return 0, 0
    try:
        # Ép tên cột về chữ thường để tránh lỗi Vnstock lúc hoa lúc thường
        df.columns = [c.lower() for c in df.columns]
        close = df['close']
        
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        
        rsi = 100 - (100 / (1 + avg_gain / avg_loss))
        ma9 = rsi.rolling(9).mean()
        ma45 = rsi.rolling(45).mean()
        
        last_rsi, last_ma9, last_ma45 = rsi.iloc[-1], ma9.iloc[-1], ma45.iloc[-1]
        
        if last_rsi > last_ma9 and last_rsi > last_ma45: return 1, close.iloc[-1]
        if last_rsi < last_ma9 and last_rsi < last_ma45: return -1, close.iloc[-1]
    except: pass
    return 0, 0

def resample_data(df, rule):
    if df is None or len(df) < 2: return None
    try:
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        # Gộp nến
        res = df.resample(rule).agg({'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'})
        return res.dropna().reset_index()
    except: return None

# --- HÀM LẤY DỮ LIỆU ---
def get_data(symbol, res, days):
    # Thử nguồn TCBS trước (ổn nhất trên Cloud)
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    try:
        df = stock_historical_data(symbol=symbol, start_date=start_date, end_date=end_date, 
                                 resolution=res, type='stock', source='tcbs')
        if df is not None and not df.empty: return df
    except: pass
    return None

# --- GIAO DIỆN QUÉT ---
if st.button("🔍 BẮT ĐẦU QUÉT DỮ LIỆU"):
    results = {}
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, sym in enumerate(SYMBOLS):
        status_text.write(f"🔄 Đang quét: **{sym}** ({i+1}/{len(SYMBOLS)})")
        progress_bar.progress((i + 1) / len(SYMBOLS))
        
        # Lấy data
        df_h = get_data(sym, '1H', 60)
        df_d = get_data(sym, '1D', 600) # Lấy xa để đủ nến cho khung Tuần
        
        if df_h is not None and df_d is not None:
            tfs = {
                '1h': df_h,
                '4h': resample_data(df_h, '4H'),
                '1d': df_d,
                '3d': resample_data(df_d, '3D'),
                '1w': resample_data(df_d, 'W-MON')
            }
            
            sigs = {name: calculate_signals(tf_df)[0] for name, tf_df in tfs.items()}
            price = df_d['close'].iloc[-1] if 'close' in df_d.columns else df_d['Close'].iloc[-1]
            
            pairs = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]
            for tf1, tf2 in pairs:
                if sigs[tf1] == sigs[tf2] and sigs[tf1] != 0:
                    if sym not in results:
                        p_show = price if price > 1000 else price * 1000
                        results[sym] = {'p': p_show, 'buy': [], 'sell': []}
                    
                    lbl = f"{tf1.upper()}-{tf2.upper()}"
                    if sigs[tf1] =
