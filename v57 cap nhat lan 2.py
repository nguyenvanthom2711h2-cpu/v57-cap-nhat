import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time
import warnings

warnings.filterwarnings("ignore")

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="VN Stock Consensus v2", layout="wide")
st.title("🚀 Bộ Lọc Đồng Thuận Multi-TF (Bản sửa lỗi Yahoo)")
st.caption("Dữ liệu Yahoo Finance | Hỗ trợ khung 1H-4H-1D-3D-1W")

# DANH SÁCH MÃ CHỨNG KHOÁN (Rút gọn các mã thanh khoản cao để quét nhanh và chính xác hơn)
SYMBOLS_RAW = [
    'ACB','BID','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','SSI','STB','TCB','VCB','VHM','VIC','VNM','VPB','VRE',
    'LPB','DGC','DPM','DCM','VGC','PVD','PVS','NLG','KDH','KBC','IDC','SZC','GMD','HAH','OIL','FRT','PNJ','HSG','NKG','DIG','DXG','VND','VCI'
]
SYMBOLS = [s + ".VN" for s in SYMBOLS_RAW]

SCAN_PAIRS = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]

# ==========================================
# 1. HÀM TÍNH TOÁN RSI CHUẨN
# ==========================================
def calculate_indicators(df):
    if df is None or len(df) < 50: return 0, 0, 0
    try:
        # Lấy giá đóng cửa cuối cùng
        close = df['close']
        delta = close.diff()
        
        # RSI Wilder's (chuẩn TradingView/Vnstock)
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
        
        status = 0
        if last_rsi > last_ma9 and last_rsi > last_ma45: status = 1
        elif last_rsi < last_ma9 and last_rsi < last_ma45: status = -1
        
        return status, last_rsi, close.iloc[-1]
    except:
        return 0, 0, 0

# ==========================================
# 2. HÀM LẤY VÀ XỬ LÝ DỮ LIỆU YAHOO
# ==========================================
def get_clean_data(sym, period, interval):
    try:
        df = yf.download(sym, period=period, interval=interval, progress=False)
        if df.empty: return None
        
        # Xử lý lỗi MultiIndex của Yahoo Finance mới
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        df.columns = ['open', 'high', 'low', 'close', 'volume']
        return df
    except:
        return None

def resample_data(df, rule):
    if df is None: return None
    try:
        res = df.resample(rule).agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
        }).dropna()
        return res
    except:
        return None

# ==========================================
# 3. QUY TRÌNH QUÉT
# ==========================================
if st.button("🔍 BẤT ĐẦU QUÉT"):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(SYMBOLS)
    
    for i, sym in enumerate(SYMBOLS):
        name = sym.replace(".VN", "")
        status_text.write(f"🔄 Đang quét mã: **{name}**...")
        progress_bar.progress((i + 1) / total)
        
        # Tải dữ liệu 1H và 1D
        df_1h = get_clean_data(sym, "60d", "1h")
        df_1d = get_clean_data(sym, "2y", "1d")
        
        if df_1h is not None and df_1d is not None:
            # Tạo các khung thời gian
            tfs = {
                '1h': df_1h,
                '4h': resample_data(df_h, '4H') if (df_h := df_1h) is not None else None,
                '1d': df_1d,
                '3d': resample_data(df_1d, '3D'),
                '1w': resample_data(df_1d, 'W-MON')
            }
            
            # Tính tín hiệu
            sigs = {}
            for tf_name, df_tf in tfs.items():
                status, _, _ = calculate_indicators(df_tf)
                sigs[tf_name] = status
            
            # Kiểm tra đồng thuận
            buy_pairs = []
            sell_pairs = []
            for tf1, tf2 in SCAN_PAIRS:
                if sigs.get(tf1) == sigs.get(tf2) and sigs.get(tf1) != 0:
                    pair_label = f"{tf1.upper()}-{tf2.upper()}"
                    if sigs[tf1] == 1: buy_pairs.append(pair_label)
                    else: sell_pairs.append(pair_label)
            
            if buy_pairs or sell_pairs:
                last_p = df_1d['close'].iloc[-1]
                # Chuẩn hóa giá: Yahoo trả về đúng giá (VD: 35500), nếu thấp quá (<1000) thì nhân 1000
                price_show = last_p if last_p > 1000 else last_p * 1000
                
                results.append({
                    "MÃ": name,
                    "GIÁ": f"{price_show:,.0f}",
                    "ĐỒNG THUẬN MUA (🚀)": ", ".join(buy_pairs) if buy_pairs else "-",
                    "ĐỒNG THUẬN BÁN (🔻)": ", ".join(sell_pairs) if sell_pairs else "-"
                })
        
        time.sleep(0.05) # Né chặn request

    status_text.empty()
    
    if results:
        st.subheader(f"📊 Bảng Tổng Hợp Kết Quả ({datetime.now().strftime('%H:%M:%S')})")
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Hiện tại không có mã nào đạt điều kiện đồng thuận. Hãy thử lại vào lúc thị trường biến động mạnh hơn.")

st.divider()
st.info("💡 Mẹo: Nếu bạn không thấy kết quả, hãy kiểm tra xem danh sách mã trên Yahoo Finance có thay đổi không. Các mã FPT.VN, SSI.VN hiện tại vẫn lấy dữ liệu rất tốt.")
