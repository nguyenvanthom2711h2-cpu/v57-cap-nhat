import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import warnings
import time
import random

# Import vnstock
try:
    from vnstock import stock_historical_data
except ImportError:
    st.error("Thiếu thư viện vnstock trong requirements.txt")

warnings.filterwarnings("ignore")

# ==========================================
# CẤU HÌNH GIAO DIỆN
# ==========================================
st.set_page_config(page_title="Stock Web Screener", layout="wide")
st.title("🚀 Bộ Lọc Chứng Khoán Multi-TF (Bản Web)")

# Danh sách mã rút gọn các mã lỗi hoặc dùng toàn bộ
SYMBOLS = [
    'ACB','BCM','BID','BVH','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','PLX','POW','SAB',
    'SHB','SSB','SSI','STB','TCB','TPB','VCB','VHM','VIB','VIC','VJC','VNM','VPB','VRE','LPB','DGC',
    'DPM','DCM','VGC','PVD','PVS','NLG','KDH','KBC','IDC','SZC','GMD','HAH','OIL','FRT','PNJ','TLG',
    'BSI','HSG','NKG','DIG','DXG','PDR','NVL','VIX','VCK','TCX','DGW','VND','HCM','VCI','EIB','MSB',
    'OCB','REE','CTR','VGI','VTP'
]

SCAN_PAIRS = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]

# ==========================================
# HÀM TÍNH TOÁN (Tối ưu cho Web)
# ==========================================
def calculate_indicators(df):
    if df is None or len(df) < 50: return 0, 0
    try:
        df = df.copy()
        delta = df['close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        df['rsi'] = 100 - (100 / (1 + avg_gain / avg_loss))
        df['rsi9'] = df['rsi'].rolling(9).mean()
        df['rsi45'] = df['rsi'].rolling(45).mean()
        
        last = df.iloc[-1]
        if last['rsi'] > last['rsi9'] and last['rsi'] > last['rsi45']: return 1, last['close']
        if last['rsi'] < last['rsi9'] and last['rsi'] < last['rsi45']: return -1, last['close']
    except: pass
    return 0, 0

def resample_stock_data(df, rule):
    if df is None or len(df) < 2: return None
    try:
        df = df.copy()
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        logic = {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}
        return df.resample(rule).apply(logic).dropna().reset_index()
    except: return None

# ==========================================
# CƠ CHẾ LẤY DỮ LIỆU "SỐNG SÓT" TRÊN WEB
# ==========================================
def get_data_safe(symbol, resolution, days_back):
    """Thử lấy dữ liệu nhiều lần nếu gặp lỗi kết nối"""
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    for _ in range(3): # Thử lại tối đa 3 lần
        try:
            df = stock_historical_data(symbol=symbol, 
                                       start_date=start_date, 
                                       end_date=end_date, 
                                       resolution=resolution, 
                                       source='tcbs') # Dùng TCBS ổn định nhất cho Web
            if df is not None and not df.empty:
                return df
        except:
            time.sleep(random.uniform(1, 2)) # Nghỉ ngẫu nhiên để né bot detection
    return None

# ==========================================
# THỰC THI
# ==========================================
if st.button("🚀 BẮT ĐẦU QUÉT"):
    summary_data = {}
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(SYMBOLS)
    
    for idx, sym in enumerate(SYMBOLS):
        progress_bar.progress((idx + 1) / total)
        status_text.code(f"正在扫描 (Đang quét): {sym}...")
        
        # Lấy dữ liệu
        df_h = get_data_safe(sym, '1H', 60)
        df_d = get_data_safe(sym, '1D', 500)
        
        if df_h is not None and df_d is not None:
            tfs = {
                '1h': df_h,
                '4h': resample_stock_data(df_h, '4H'),
                '1d': df_d,
                '3d': resample_stock_data(df_d, '3D'),
                '1w': resample_stock_data(df_d, 'W-MON')
            }
            
            signals = {}
            for name, df_tf in tfs.items():
                sig, _ = calculate_indicators(df_tf)
                signals[name] = sig
            
            last_p = df_h['close'].iloc[-1]
            
            for tf1, tf2 in SCAN_PAIRS:
                if signals.get(tf1) == signals.get(tf2) and signals.get(tf1) != 0:
                    if sym not in summary_data:
                        summary_data[sym] = {'p': last_p, 'buy': [], 'sell': []}
                    
                    label = f"{tf1.upper()}-{tf2.upper()}"
                    if signals[tf1] == 1: summary_data[sym]['buy'].append(label)
                    else: summary_data[sym]['sell'].append(label)
        
        # Quan trọng: Nghỉ để không bị khóa IP
        time.sleep(0.3)

    status_text.empty()
    
    if summary_data:
        st.subheader("📊 Kết Quả Đồng Thuận")
        final_df = []
        for s, d in summary_data.items():
            final_df.append({
                "MÃ": s,
                "GIÁ": f"{d['p'] if d['p'] > 1000 else d['p']*1000:,.0f}",
                "MUA (🚀)": ", ".join(d['buy']) if d['buy'] else "-",
                "BÁN (🔻)": ", ".join(d['sell']) if d['sell'] else "-"
            })
        st.dataframe(pd.DataFrame(final_df), use_container_width=True, hide_index=True)
    else:
        st.warning("Không tìm thấy tín hiệu hoặc lỗi kết nối IP. Hãy thử lại.")
