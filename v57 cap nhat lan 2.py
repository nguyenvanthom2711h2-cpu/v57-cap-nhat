import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import warnings

# Tắt cảnh báo
warnings.filterwarnings("ignore")

# Thử import thư viện vnstock theo cách mới nhất
try:
    from vnstock import stock_historical_data
except ImportError:
    st.error("❌ Không tìm thấy thư viện vnstock. Hãy kiểm tra file requirements.txt")
    st.stop()

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="VnStock Screener Pro", layout="wide")
st.title("🚀 Bộ Lọc Chứng Khoán Multi-TF")
st.caption("Phiên bản tối ưu cho Streamlit Cloud - Chống chặn IP")

# DANH SÁCH MÃ (Bạn có thể thêm bớt tùy ý)
SYMBOLS = [
    'ACB','BID','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','PLX','POW','SAB',
    'SHB','SSB','SSI','STB','TCB','TPB','VCB','VHM','VIB','VIC','VJC','VNM','VPB','VRE','LPB','DGC',
    'DPM','DCM','VGC','PVD','PVS','NLG','KDH','KBC','IDC','SZC','GMD','HAH','OIL','FRT','PNJ','TLG',
    'BSI','HSG','NKG','DIG','DXG','PDR','NVL','VIX','VND','HCM','VCI','EIB','MSB',
    'OCB','REE','CTR','VGI','VTP'
]

# --- HÀM TÍNH TOÁN RSI ĐỒNG THUẬN ---
def calculate_rsi_logic(df):
    if df is None or len(df) < 50: return 0, 0
    try:
        # Chuẩn hóa tên cột về chữ thường
        df.columns = [c.lower() for c in df.columns]
        close = df['close']
        
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        
        rsi = 100 - (100 / (1 + avg_gain / avg_loss))
        rsi_ma9 = rsi.rolling(9).mean()
        rsi_ma45 = rsi.rolling(45).mean()
        
        last_rsi = rsi.iloc[-1]
        last_ma9 = rsi_ma9.iloc[-1]
        last_ma45 = rsi_ma45.iloc[-1]
        
        if last_rsi > last_ma9 and last_rsi > last_ma45: return 1, close.iloc[-1]
        if last_rsi < last_ma9 and last_rsi < last_ma45: return -1, close.iloc[-1]
    except Exception as e:
        pass
    return 0, 0

def resample_ohlc(df, rule):
    if df is None or len(df) < 2: return None
    try:
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        logic = {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}
        return df.resample(rule).apply(logic).dropna().reset_index()
    except: return None

# --- HÀM LẤY DỮ LIỆU AN TOÀN (CỐ GẮNG NÉ CHẶN IP) ---
def get_data_with_fallback(symbol, res, start_date):
    # Thử nguồn TCBS trước, nếu lỗi thử DNSE (VCI hiện bị chặn rất nặng trên Cloud)
    sources = ['tcbs', 'dnse']
    for src in sources:
        try:
            df = stock_historical_data(symbol=symbol, 
                                     start_date=start_date, 
                                     end_date=datetime.now().strftime('%Y-%m-%d'), 
                                     resolution=res, type='stock', source=src)
            if df is not None and not df.empty:
                return df
        except:
            continue
    return None

# --- GIAO DIỆN CHÍNH ---
if st.button("🔍 BẮT ĐẦU QUÉT TOÀN THỊ TRƯỜNG"):
    results = {}
    progress_bar = st.progress(0)
    status_msg = st.empty()
    
    start_time = time.time()
    
    # Để tránh bị khóa IP, chúng ta quét tuần tự nhưng tối ưu hóa dữ liệu
    for i, sym in enumerate(SYMBOLS):
        status_msg.info(f" đang xử lý: **{sym}** ({i+1}/{len(SYMBOLS)})")
        progress_bar.progress((i + 1) / len(SYMBOLS))
        
        # 1. Lấy dữ liệu 1H (Lấy 60 ngày là đủ gộp 4H)
        df_h = get_data_with_fallback(sym, '1H', (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d'))
        # 2. Lấy dữ liệu 1D (Lấy từ 2022 để đủ nến gộp Tuần)
        df_d = get_data_with_fallback(sym, '1D', '2022-01-01')
        
        if df_h is not None and df_d is not None:
            # Tạo các khung thời gian
            tfs = {
                '1h': df_h,
                '4h': resample_ohlc(df_h, '4H'),
                '1d': df_d,
                '3d': resample_ohlc(df_d, '3D'),
                '1w': resample_ohlc(df_d, 'W-MON')
            }
            
            # Tính tín hiệu từng khung
            sigs = {}
            for name, df_tf in tfs.items():
                res_sig, _ = calculate_rsi_logic(df_tf)
                sigs[name] = res_sig
            
            # Kiểm tra đồng thuận
            pairs = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]
            last_price = df_d['close'].iloc[-1] if 'close' in df_d.columns else df_d['Close'].iloc[-1]
            
            for tf1, tf2 in pairs:
                if sigs[tf1] == sigs[tf2] and sigs[tf1] != 0:
                    if sym not in results:
                        # Quy đổi
