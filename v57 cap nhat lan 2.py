import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import warnings

# --- KIỂM TRA THƯ VIỆN ---
try:
    from vnstock import Vnstock
except ImportError:
    st.error("❌ Lỗi: Máy chủ chưa cài đặt thư viện 'vnstock'.")
    st.info("👉 Cách sửa: Đảm bảo bạn có file 'requirements.txt' chứa chữ 'vnstock' trên GitHub và nhấn 'Reboot App' ở menu bên phải.")
    st.stop()

warnings.filterwarnings("ignore")

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="VnStock 4.0 Pro", layout="wide")
st.title("🚀 Bộ Lọc Chứng Khoán Multi-TF (Vnstock 4.0)")

# --- DANH SÁCH MÃ ---
SYMBOLS = ['ACB','BID','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','SSI','STB','TCB','VCB','VHM','VIC','VNM','VPB','VRE']

def calculate_rsi_consensus(df):
    if df is None or len(df) < 50: return 0, 0
    try:
        df.columns = [c.lower() for c in df.columns]
        close = df['close']
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = 100 - (100 / (1 + gain / loss))
        rsi_ma9 = rsi.rolling(9).mean()
        rsi_ma45 = rsi.rolling(45).mean()
        if rsi.iloc[-1] > rsi_ma9.iloc[-1] and rsi.iloc[-1] > rsi_ma45.iloc[-1]: return 1, close.iloc[-1]
        if rsi.iloc[-1] < rsi_ma9.iloc[-1] and rsi.iloc[-1] < rsi_ma45.iloc[-1]: return -1, close.iloc[-1]
    except: pass
    return 0, 0

def resample_ohlc(df, rule):
    try:
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        return df.resample(rule).agg({'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}).dropna().reset_index()
    except: return None

# --- GIAO DIỆN CHÍNH ---
if st.button("🔍 BẮT ĐẦU QUÉT"):
    results = []
    progress_bar = st.progress(0)
    log_area = st.empty()
    vnstock = Vnstock()

    for i, sym in enumerate(SYMBOLS):
        log_area.info(f"🔄 Đang quét: **{sym}**")
        progress_bar.progress((i + 1) / len(SYMBOLS))
        try:
            # Ưu tiên nguồn VCI hoặc TCBS
            s = vnstock.stock(symbol=sym, source='VCI')
            df_h = s.quote.history(interval='1H', count=500)
            df_d = s.quote.history(interval='1D', count=500)

            if df_h is not None and not df_h.empty:
                tfs = {
                    '1h': df_h,
                    '4h': resample_ohlc(df_h, '4H'),
                    '1d': df_d,
                    '3d': resample_ohlc(df_d, '3D'),
                    '1w': resample_ohlc(df_d, 'W-MON')
                }
                sigs = {name: calculate_rsi_consensus(tf_df)[0] for name, tf_df in tfs.items()}
                
                df_d.columns = [c.lower() for c in df_d.columns]
                price = df_d['close'].iloc[-1]
                
                buy, sell = [], []
                for tf1, tf2 in [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]:
                    if sigs[tf1] == sigs[tf2] and sigs[tf1] != 0:
                        lbl = f"{tf1.upper()}-{tf2.upper()}"
                        if sigs[tf1] == 1: buy.append(lbl)
                        else: sell.append(lbl)
                
                if buy or sell:
                    results.append({"MÃ": sym, "GIÁ": f"{price if price > 1000 else price*1000:,.0f}", 
                                    "MUA (🚀)": ", ".join(buy), "BÁN (🔻)": ", ".join(sell)})
            time.sleep(0.5)
        except: continue

    log_area.empty()
    if results:
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Không có mã đồng thuận hoặc bị lỗi kết nối.")
