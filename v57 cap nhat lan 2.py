import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="VN Stock Yahoo Finance", layout="wide")
st.title("🚀 Bộ Lọc Chứng Khoán Việt Nam (Nguồn Yahoo Finance)")
st.caption("Giải pháp chạy ổn định 100% trên Web Streamlit Cloud")

# DANH SÁCH MÃ (Tự động thêm đuôi .VN)
SYMBOLS_RAW = [
    'ACB','BID','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','SSI','STB','TCB','VCB','VHM','VIC','VNM','VPB','VRE',
    'DGC','DPM','DCM','VGC','PVD','PVS','NLG','KDH','KBC','IDC','SZC','GMD','HAH','OIL','FRT','PNJ'
]
SYMBOLS = [s + ".VN" for s in SYMBOLS_RAW]

# --- HÀM TÍNH TOÁN RSI ---
def calculate_rsi_logic(df):
    if df is None or len(df) < 50: return 0, 0
    try:
        close = df['Close']
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        ma9 = rsi.rolling(9).mean()
        ma45 = rsi.rolling(45).mean()
        
        last_rsi, last_ma9, last_ma45 = rsi.iloc[-1], ma9.iloc[-1], ma45.iloc[-1]
        
        if last_rsi > last_ma9 and last_rsi > last_ma45: return 1, close.iloc[-1]
        if last_rsi < last_ma9 and last_rsi < last_ma45: return -1, close.iloc[-1]
    except: pass
    return 0, 0

# --- HÀM GỘP NẾN ---
def resample_data(df, rule):
    try:
        res = df.resample(rule).agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'})
        return res.dropna()
    except: return None

# --- GIAO DIỆN QUÉT ---
if st.button("🔍 BẮT ĐẦU QUÉT"):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, sym in enumerate(SYMBOLS):
        short_name = sym.replace(".VN", "")
        status_text.info(f"🔄 Đang tải dữ liệu: **{short_name}**")
        progress_bar.progress((i + 1) / len(SYMBOLS))
        
        try:
            # Lấy dữ liệu từ Yahoo Finance (Khung 1 giờ và 1 ngày)
            # Khung 1h của Yahoo chỉ cho phép lấy tối đa 730 ngày
            data_1h = yf.download(sym, period="60d", interval="1h", progress=False)
            data_1d = yf.download(sym, period="2y", interval="1d", progress=False)

            if not data_1h.empty and not data_1d.empty:
                # Chuẩn bị các khung thời gian
                tfs = {
                    '1h': data_1h,
                    '4h': resample_data(data_1h, '4h'),
                    '1d': data_1d,
                    '3d': resample_data(data_1d, '3D'),
                    '1w': resample_data(data_1d, 'W-MON')
                }
                
                sigs = {name: calculate_rsi_logic(tf_df)[0] for name, tf_df in tfs.items()}
                price = data_1d['Close'].iloc[-1]
                
                buy, sell = [], []
                pairs = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]
                for tf1, tf2 in pairs:
                    if sigs[tf1] == sigs[tf2] and sigs[tf1] != 0:
                        lbl = f"{tf1.upper()}-{tf2.upper()}"
                        if sigs[tf1] == 1: buy.append(lbl)
                        else: sell.append(lbl)
                
                if buy or sell:
                    # Yahoo Finance trả về giá chuẩn (ví dụ 35000), không cần nhân 1000
                    results.append({
                        "MÃ": short_name,
                        "GIÁ": f"{price:,.0f}",
                        "MUA (🚀)": ", ".join(buy) if buy else "-",
                        "BÁN (🔻)": ", ".join(sell) if sell else "-"
                    })
        except:
            continue

    status_text.empty()
    if results:
        st.subheader(f"📊 Kết Quả Đồng Thuận ({datetime.now().strftime('%H:%M:%S')})")
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
    else:
        st.warning("Không tìm thấy mã nào đạt điều kiện hoặc Yahoo Finance đang bảo trì.")

st.divider()
st.info("💡 Tại sao dùng Yahoo Finance? Vì Yahoo là máy chủ quốc tế, họ không chặn địa chỉ IP của Streamlit Cloud như các công ty chứng khoán VN.")
