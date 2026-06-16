import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="VN Stock Yahoo Finance", layout="wide")
st.title("🚀 Bộ Lọc Chứng Khoán Việt Nam (Nguồn Yahoo Finance)")
st.caption("Dữ liệu lấy từ Yahoo Finance - Tối ưu hiển thị kết quả")

# DANH SÁCH MÃ CHỨNG KHOÁN VN
SYMBOLS_RAW = [
    'ACB','BID','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','SSI','STB','TCB','VCB','VHM','VIC','VNM','VPB','VRE',
    'DGC','DPM','DCM','VGC','PVD','PVS','NLG','KDH','KBC','IDC','SZC','GMD','HAH','OIL','FRT','PNJ','HSG','NKG','DIG','DXG'
]
SYMBOLS = [s + ".VN" for s in SYMBOLS_RAW]

# --- HÀM TÍNH TOÁN RSI (SỬ DỤNG EMA ĐỂ NHẠY HƠN) ---
def calculate_rsi_logic(df):
    if df is None or len(df) < 50: return 0, 0
    try:
        # Xử lý lấy cột Close bất kể định dạng Yahoo
        if isinstance(df.columns, pd.MultiIndex):
            close = df.xs('Close', axis=1, level=0).iloc[:, 0]
        else:
            close = df['Close']
            
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        
        # Dùng EWM (Exponential) để giống RSI chuẩn của TradingView hơn
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        ma9 = rsi.rolling(9).mean()
        ma45 = rsi.rolling(45).mean()
        
        last_rsi = rsi.iloc[-1]
        last_ma9 = ma9.iloc[-1]
        last_ma45 = ma45.iloc[-1]
        
        if last_rsi > last_ma9 and last_rsi > last_ma45: return 1, close.iloc[-1]
        if last_rsi < last_ma9 and last_rsi < last_ma45: return -1, close.iloc[-1]
    except: pass
    return 0, 0

# --- HÀM GỘP NẾN ---
def resample_data(df, rule):
    try:
        # Xử lý nến cho Yahoo Multi-index
        if isinstance(df.columns, pd.MultiIndex):
            df_flat = df.copy()
            df_flat.columns = df_flat.columns.get_level_values(0)
        else:
            df_flat = df
            
        res = df_flat.resample(rule).agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'})
        return res.dropna()
    except: return None

# --- GIAO DIỆN QUÉT ---
if st.button("🔍 BẮT ĐẦU QUÉT"):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    found_count = 0
    
    for i, sym in enumerate(SYMBOLS):
        short_name = sym.replace(".VN", "")
        status_text.info(f"🔄 Đang quét: **{short_name}** (Tìm thấy: {found_count})")
        progress_bar.progress((i + 1) / len(SYMBOLS))
        
        try:
            # Tải dữ liệu (Lấy thêm dữ liệu để tính toán RSI 45 chính xác hơn)
            data_1h = yf.download(sym, period="60d", interval="1h", progress=False)
            data_1d = yf.download(sym, period="2y", interval="1d", progress=False)

            if not data_1h.empty and not data_1d.empty:
                tfs = {
                    '1h': data_1h,
                    '4h': resample_data(data_1h, '4H'),
                    '1d': data_1d,
                    '3d': resample_data(data_1d, '3D'),
                    '1w': resample_data(data_1d, 'W-MON')
                }
                
                sigs = {name: calculate_rsi_logic(tf_df)[0] for name, tf_df in tfs.items()}
                
                # Lấy giá hiện tại
                if isinstance(data_1d.columns, pd.MultiIndex):
                    price = data_1d.xs('Close', axis=1, level=0).iloc[-1, 0]
                else:
                    price = data_1d['Close'].iloc[-1]
                
                buy, sell = [], []
                pairs = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]
                for tf1, tf2 in pairs:
                    if sigs.get(tf1) == sigs.get(tf2) and sigs.get(tf1) != 0:
                        lbl = f"{tf1.upper()}-{tf2.upper()}"
                        if sigs[tf1] == 1: buy.append(lbl)
                        else: sell.append(lbl)
                
                if buy or sell:
                    found_count += 1
                    results.append({
                        "MÃ": short_name,
                        "GIÁ": f"{price:,.0f}",
                        "MUA (🚀)": ", ".join(buy) if buy else "-",
                        "BÁN (🔻)": ", ".join(sell) if sell else "-"
                    })
        except:
            continue
        # Nghỉ cực ngắn để ổn định
        time.sleep(0.05)

    status_text.empty()
    if results:
        st.success(f"✅ Đã tìm thấy {len(results)} mã đạt điều kiện!")
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Hiện tại không có mã nào có sự đồng thuận RSI trên các khung giờ đã chọn.")

st.divider()
st.info("💡 Mẹo: Nếu không thấy mã nào, có thể thị trường đang đi ngang. Bạn có thể quay lại kiểm tra vào phiên chiều hoặc ngày mai.")
