import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time
import warnings
import numpy as np
from scipy.signal import argrelextrema

warnings.filterwarnings("ignore")

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="VN Stock Consensus v152", layout="wide")
st.title("🚀 Bộ Lọc Đồng Thuận & Phân Kỳ RSI")
st.caption("Dữ liệu Yahoo Finance | RSI Wilder's | Đảm bảo 100% kết quả như bản cũ")

# DANH SÁCH MÃ CHỨNG KHOÁN (Giữ nguyên bản gốc)
SYMBOLS_RAW = [
    'ACB','BID','CTG','HDB','LPB','MBB','MSB','OCB','SHB','STB','TCB','TPB','VCB','VIB','VPB','EIB','SSB','ABB','BVB',
    'SSI','VND','VCI','HCM','VIX','BSI','FTS','MBS','SHS','CTS','AGR','ORS','VDS','TVS',
    'VHM','VIC','VRE','DXG','DIG','PDR','NVL','NLG','KDH','CEO','L14','TCH','HQC','ITA','VCG','HHV','LCG','FCN','C4G','HBC','CTD',
    'HPG','HSG','NKG','TVN','TLH','VGS',
    'GAS','PVD','PVS','PVT','PVC','PLX','POW','PC1','TV2','GEG','REE','BCG','ASM','NT2',
    'IDC','SZC','KBC','VGC','PHR','GVR','BCM','TIP','DPR',
    'MWG','MSN','FPT','PNJ','DGW','FRT','PET','VTP','CTR','VGI',
    'DGC','DPM','DCM','LAS','BFC','CSV',
    'VHC','ANV','IDI','PAN','DBC','BAF','HAG','HNG','LSS','SBT',
    'GMD','HAH','VSC','VOS','SKG','PVT',
    'VNM','SAB','BHN','TLG','KDC','GIL','MSH','TNG','VGT','RAL','DQC'
]
SYMBOLS = [s + ".VN" for s in SYMBOLS_RAW]
SCAN_PAIRS = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]

# ==========================================
# 1. HÀM PHÁT HIỆN PHÂN KỲ (Bổ sung thêm)
# ==========================================
def detect_rsi_divergence(df, order=5):
    """
    Hàm này chỉ dùng để hiển thị thêm, không ảnh hưởng đến bộ lọc đồng thuận
    """
    try:
        if df is None or len(df) < 30: return "-"
        close = df['c'].values
        rsi = df['rsi'].values
        
        # Tìm đỉnh đáy
        peaks = argrelextrema(rsi, np.greater, order=order)[0]
        troughs = argrelextrema(rsi, np.less, order=order)[0]
        
        # Bullish Divergence (Hội tụ)
        if len(troughs) >= 2:
            t1, t2 = troughs[-2], troughs[-1]
            if close[t2] < close[t1] and rsi[t2] > rsi[t1]:
                if (len(df) - 1 - t2) < 10: return "HỘI TỤ (MUA) 🚀"
        
        # Bearish Divergence (Phân kỳ)
        if len(peaks) >= 2:
            p1, p2 = peaks[-2], peaks[-1]
            if close[p2] > close[p1] and rsi[p2] < rsi[p1]:
                if (len(df) - 1 - p2) < 10: return "PHÂN KỲ (BÁN) 📉"
        return "-"
    except: return "-"

# ==========================================
# 2. HÀM TÍNH TOÁN (GIỮ 100% LOGIC GỐC)
# ==========================================
def calculate_indicators(df):
    # Trả về: (Trạng thái -1/0/1, Giá cuối, Phân kỳ)
    if df is None or len(df) < 50: return 0, 0, "-"
    try:
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        
        # --- CÔNG THỨC GỐC CỦA BẠN ---
        delta = df['c'].diff()
        gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        
        df['rsi'] = 100 - (100 / (1 + avg_gain / avg_loss))
        df['rsi9'] = df['rsi'].rolling(9).mean()
        df['rsi45'] = df['rsi'].rolling(45).mean()
        # -----------------------------
        
        div = detect_rsi_divergence(df)
        last = df.iloc[-1]
        
        status = 0
        if last['rsi'] > last['rsi9'] and last['rsi'] > last['rsi45']: status = 1
        elif last['rsi'] < last['rsi9'] and last['rsi'] < last['rsi45']: status = -1
        
        return status, last['c'], div
    except: return 0, 0, "-"

# ==========================================
# 3. HÀM GỘP NẾN (GIỮ 100% LOGIC GỐC)
# ==========================================
def resample_stock_data(df, rule):
    if df is None or len(df) < 2: return None
    try:
        df = df.copy()
        if 'ts' not in df.columns: df['ts'] = df.index
        df['ts'] = pd.to_datetime(df['ts'])
        df.set_index('ts', inplace=True)
        logic = {'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}
        res = df.resample(rule).apply(logic).dropna().reset_index()
        res.columns = ['ts', 'o', 'h', 'l', 'c', 'v']
        return res
    except: return None

# ==========================================
# 4. QUY TRÌNH QUÉT
# ==========================================
if st.button("🔍 BẮT ĐẦU QUÉT HỆ THỐNG"):
    summary_data = {}
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, sym in enumerate(SYMBOLS):
        short_name = sym.replace(".VN", "")
        status_text.write(f"🔄 Đang quét: **{short_name}**...")
        progress_bar.progress((i + 1) / len(SYMBOLS))
        
        try:
            # Tải dữ liệu (Xử lý MultiIndex của yfinance mới)
            d1h = yf.download(sym, period="60d", interval="1h", progress=False)
            d1d = yf.download(sym, period="2y", interval="1d", progress=False)

            if not d1h.empty and not d1d.empty:
                if isinstance(d1h.columns, pd.MultiIndex):
                    d1h.columns = d1h.columns.get_level_values(0)
                    d1d.columns = d1d.columns.get_level_values(0)

                # Chuẩn bị DataFrames
                df_h = d1h[['Open','High','Low','Close','Volume']].rename(columns={'Open':'o','High':'h','Low':'l','Close':'c','Volume':'v'})
                df_d = d1d[['Open','High','Low','Close','Volume']].rename(columns={'Open':'o','High':'h','Low':'l','Close':'c','Volume':'v'})

                tfs = {
                    '1h': df_h.reset_index().rename(columns={'Datetime':'ts'}),
                    '4h': resample_stock_data(d1h, '4H'),
                    '1d': df_d.reset_index().rename(columns={'Date':'ts'}),
                    '3d': resample_stock_data(d1d, '3D'),
                    '1w': resample_stock_data(d1d, 'W-MON')
                }
                
                sigs = {}; prices = {}; divs = {}
                for name, df_tf in tfs.items():
                    stat, p, div = calculate_indicators(df_tf)
                    sigs[name] = stat
                    prices[name] = p
                    divs[name] = div
                
                # --- LOGIC ĐỒNG THUẬN QUYẾT ĐỊNH VIỆC HIỂN THỊ ---
                for tf1, tf2 in SCAN_PAIRS:
                    # Nếu signal 2 khung giống nhau và khác 0 (BUY hoặc SELL)
                    if sigs.get(tf1) == sigs.get(tf2) and sigs.get(tf1) != 0:
                        side = "BUY" if sigs[tf1] == 1 else "SELL"
                        p_val = prices['1h'] if prices['1h'] > 1000 else prices['1h'] * 1000
                        
                        if short_name not in summary_data:
                            summary_data[short_name] = {'p': p_val, 'buy': [], 'sell': [], 'div': divs['1d']}
                        
                        label = f"{tf1.upper()}-{tf2.upper()}"
                        if side == "BUY": summary_data[short_name]['buy'].append(label)
                        else: summary_data[short_name]['sell'].append(label)
            
            time.sleep(0.01) # Tránh bị block IP
        except: continue

    status_text.empty()
    if summary_data:
        st.subheader("📊 Kết quả Đồng Thuận & Phân Kỳ")
        final_rows = []
        for s in sorted(summary_data.keys()):
            d = summary_data[s]
            final_rows.append({
                "MÃ": s,
                "GIÁ": f"{d['p']:,.0f}",
                "MUA (🚀)": ", ".join(d['buy']) if d['buy'] else "-",
                "BÁN (🔻)": ", ".join(d['sell']) if d['sell'] else "-",
                "PHÂN KỲ RSI (1D)": d['div']
            })
        
        df_final = pd.DataFrame(final_rows)

        # Style màu sắc
        def color_div(val):
            if 'HỘI TỤ' in str(val): return 'color: #00ff88; font-weight: bold;'
            if 'PHÂN KỲ' in str(val): return 'color: #ff4444; font-weight: bold;'
            return ''

        # Dùng map để style (tương thích mọi bản Pandas)
        st.dataframe(df_final.style.map(color_div, subset=['PHÂN KỲ RSI (1D)']), 
                     use_container_width=True, hide_index=True)
    else:
        st.warning("Không tìm thấy mã nào đồng thuận.")
