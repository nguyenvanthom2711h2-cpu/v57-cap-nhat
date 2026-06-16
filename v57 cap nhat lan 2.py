import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time

# Thử import vnstock3
try:
    from vnstock3 import Vnstock
except ImportError:
    st.error("❌ Thiếu thư viện vnstock3. Hãy kiểm tra file requirements.txt")
    st.stop()

st.set_page_config(page_title="VnStock Consesus", layout="wide")
st.title("🚀 Bộ Lọc Chứng Khoán Multi-TF (Bản Vnstock3)")

# --- CẤU HÌNH DANH SÁCH MÃ ---
SYMBOLS = ['ACB','BID','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','SSI','STB','TCB','VCB','VHM','VIC','VNM','VPB','VRE']

# --- HÀM TÍNH RSI ---
def calculate_rsi_consensus(df):
    if df is None or len(df) < 50: return 0, 0
    try:
        df.columns = [c.lower() for c in df.columns]
        close = df['close']
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        rsi_ma9 = rsi.rolling(9).mean()
        rsi_ma45 = rsi.rolling(45).mean()
        
        curr_rsi = rsi.iloc[-1]
        if curr_rsi > rsi_ma9.iloc[-1] and curr_rsi > rsi_ma45.iloc[-1]: return 1, close.iloc[-1]
        if curr_rsi < rsi_ma9.iloc[-1] and curr_rsi < rsi_ma45.iloc[-1]: return -1, close.iloc[-1]
    except: pass
    return 0, 0

# --- HÀM GỘP NẾN ---
def resample_ohlc(df, rule):
    try:
        df.columns = [c.lower() for c in df.columns]
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        res = df.resample(rule).agg({'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'})
        return res.dropna().reset_index()
    except: return None

# --- GIAO DIỆN CHÍNH ---
if st.button("🔍 BẮT ĐẦU QUÉT"):
    results = []
    progress_bar = st.progress(0)
    log_area = st.empty()
    
    # Khởi tạo Vnstock
    stock = Vnstock().stock(source='TCBS')

    for i, sym in enumerate(SYMBOLS):
        log_area.info(f"正在 quét mã: **{sym}**...")
        progress_bar.progress((i + 1) / len(SYMBOLS))
        
        try:
            # Lấy dữ liệu 1H và 1D
            df_h = stock.quote.history(symbol=sym, interval='1H', count=500)
            df_d = stock.quote.history(symbol=sym, interval='1D', count=500)

            if df_h is not None and not df_h.empty and df_d is not None:
                # Tạo các khung thời gian
                tfs = {
                    '1h': df_h,
                    '4h': resample_ohlc(df_h, '4H'),
                    '1d': df_d,
                    '3d': resample_ohlc(df_d, '3D'),
                    '1w': resample_ohlc(df_d, 'W-MON')
                }
                
                sigs = {name: calculate_rsi_consensus(tf_df)[0] for name, tf_df in tfs.items()}
                price = df_d['close'].iloc[-1] if 'close' in df_d.columns else df_d['Close'].iloc[-1]
                
                buy_found = []
                sell_found = []
                
                pairs = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]
                for tf1, tf2 in pairs:
                    if sigs[tf1] == sigs[tf2] and sigs[tf1] != 0:
                        lbl = f"{tf1.upper()}-{tf2.upper()}"
                        if sigs[tf1] == 1: buy_found.append(lbl)
                        else: sell_found.append(lbl)
                
                if buy_found or sell_found:
                    p_final = price if price > 1000 else price * 1000
                    results.append({
                        "MÃ": sym,
                        "GIÁ": f"{p_final:,.0f}",
                        "MUA (🚀)": ", ".join(buy_found),
                        "BÁN (🔻)": ", ".join(sell_found)
                    })
            
            # Nghỉ ngắn để né chặn IP
            time.sleep(0.5)
            
        except Exception as e:
            st.error(f"⚠️ Lỗi tại mã {sym}: {str(e)}")
            if "403" in str(e) or "Forbidden" in str(e):
                st.warning("👉 IP của Streamlit Cloud đã bị TCBS chặn. Hãy thử lại sau hoặc liên hệ Admin.")
                break

    log_area.empty()
    if results:
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
    else:
        st.warning("Không tìm thấy tín hiệu hoặc lỗi dữ liệu.")
