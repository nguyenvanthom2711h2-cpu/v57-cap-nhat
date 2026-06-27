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
st.set_page_config(page_title="VN Stock Consensus v155", layout="wide")
st.title("🚀 Bộ Lọc Đồng Thuận & Đa Khung Phân Kỳ (Cố định VN-INDEX)")
st.caption("Dữ liệu Yahoo Finance | RSI Wilder's | VN-INDEX luôn hiển thị")

# DANH SÁCH MÃ CHỨNG KHOÁN
SYMBOLS_RAW = [
    '^VNINDEX', # Luôn ưu tiên quét mã này
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

SYMBOLS = [s if s.startswith('^') else s + ".VN" for s in SYMBOLS_RAW]
SCAN_PAIRS = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]

# ==========================================
# 1. HÀM PHÁT HIỆN PHÂN KỲ (GIỮ NGUYÊN)
# ==========================================
def detect_div_text(df, tf_name, order=5):
    try:
        if df is None or len(df) < 35: return None
        close = df['c'].values
        rsi = df['rsi'].values
        peaks = argrelextrema(rsi, np.greater, order=order)[0]
        troughs = argrelextrema(rsi, np.less, order=order)[0]
        if len(troughs) >= 2:
            t1, t2 = troughs[-2], troughs[-1]
            if close[t2] < close[t1] and rsi[t2] > rsi[t1]:
                if (len(df) - 1 - t2) < 8: return f"{tf_name}:HỘI TỤ 🚀"
        if len(peaks) >= 2:
            p1, p2 = peaks[-2], peaks[-1]
            if close[p2] > close[p1] and rsi[p2] < rsi[p1]:
                if (len(df) - 1 - p2) < 8: return f"{tf_name}:PHÂN KỲ 📉"
        return None
    except: return None

# ==========================================
# 2. HÀM TÍNH TOÁN (GIỮ 100% LOGIC GỐC)
# ==========================================
def calculate_indicators(df, tf_name):
    if df is None or len(df) < 50: return 0, 0, None
    try:
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        delta = df['c'].diff()
        gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        df['rsi'] = 100 - (100 / (1 + avg_gain / avg_loss))
        df['rsi9'] = df['rsi'].rolling(9).mean()
        df['rsi45'] = df['rsi'].rolling(45).mean()
        div_msg = detect_div_text(df, tf_name.upper())
        last = df.iloc[-1]
        status = 0
        if last['rsi'] > last['rsi9'] and last['rsi'] > last['rsi45']: status = 1
        elif last['rsi'] < last['rsi9'] and last['rsi'] < last['rsi45']: status = -1
        return status, last['c'], div_msg
    except: return 0, 0, None

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
if st.button("🔍 BẮT ĐẦU QUÉT"):
    summary_data = {}
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, sym in enumerate(SYMBOLS):
        short_name = sym.replace(".VN", "").replace("^", "")
        status_text.write(f"🔄 Đang quét: **{short_name}**...")
        progress_bar.progress((i + 1) / len(SYMBOLS))
        
        try:
            d1h = yf.download(sym, period="60d", interval="1h", progress=False)
            d1d = yf.download(sym, period="2y", interval="1d", progress=False)

            if not d1h.empty and not d1d.empty:
                if isinstance(d1h.columns, pd.MultiIndex): d1h.columns = d1h.columns.get_level_values(0)
                if isinstance(d1d.columns, pd.MultiIndex): d1d.columns = d1d.columns.get_level_values(0)

                df_h = d1h[['Open','High','Low','Close','Volume']].rename(columns={'Open':'o','High':'h','Low':'l','Close':'c','Volume':'v'})
                df_d = d1d[['Open','High','Low','Close','Volume']].rename(columns={'Open':'o','High':'h','Low':'l','Close':'c','Volume':'v'})

                tfs_data = {
                    '1h': df_h.reset_index().rename(columns={'Datetime':'ts', 'Date':'ts'}),
                    '4h': resample_stock_data(d1h, '4H'),
                    '1d': df_d.reset_index().rename(columns={'Date':'ts'}),
                    '3d': resample_stock_data(d1d, '3D'),
                    '1w': resample_stock_data(d1d, 'W-MON')
                }
                
                sigs = {}; prices = {}; div_list = []
                for name, df_tf in tfs_data.items():
                    stat, p, div_msg = calculate_indicators(df_tf, name)
                    sigs[name] = stat
                    prices[name] = p
                    if div_msg: div_list.append(div_msg)
                
                # Xác định giá hiển thị
                p_raw = prices['1h']
                if sym == "^VNINDEX": p_display = p_raw
                else: p_display = p_raw if p_raw > 1000 else p_raw * 1000

                # KIỂM TRA ĐỒNG THUẬN
                consensus_buy = []
                consensus_sell = []
                for tf1, tf2 in SCAN_PAIRS:
                    if sigs.get(tf1) == sigs.get(tf2) and sigs.get(tf1) != 0:
                        label = f"{tf1.upper()}-{tf2.upper()}"
                        if sigs[tf1] == 1: consensus_buy.append(label)
                        else: consensus_sell.append(label)

                # LOGIC HIỂN THỊ:
                # 1. Nếu là VNINDEX -> Luôn thêm vào summary_data
                # 2. Nếu là mã khác -> Chỉ thêm nếu có đồng thuận (consensus_buy hoặc consensus_sell không rỗng)
                if sym == "^VNINDEX" or consensus_buy or consensus_sell:
                    summary_data[short_name] = {
                        'p': p_display,
                        'buy': consensus_buy,
                        'sell': consensus_sell,
                        'divs': div_list,
                        'is_vni': (sym == "^VNINDEX")
                    }
            
            time.sleep(0.01)
        except: continue

    status_text.empty()
    if summary_data:
        st.subheader("📊 Bảng Tổng Hợp Kết Quả")
        final_rows = []
        
        # Sắp xếp: VNINDEX lên đầu, các mã khác theo Alpha
        sorted_keys = sorted([k for k in summary_data.keys() if k != "VNINDEX"])
        display_order = (["VNINDEX"] if "VNINDEX" in summary_data else []) + sorted_keys

        for s in display_order:
            d = summary_data[s]
            name_display = f"⭐ {s}" if d['is_vni'] else s
            final_rows.append({
                "MÃ": name_display,
                "GIÁ": f"{d['p']:,.2f}" if d['is_vni'] else f"{d['p']:,.0f}",
                "MUA (🚀)": ", ".join(d['buy']) if d['buy'] else "-",
                "BÁN (🔻)": ", ".join(d['sell']) if d['sell'] else "-",
                "TÍN HIỆU PHÂN KỲ": " | ".join(d['divs']) if d['divs'] else "-"
            })
        
        df_final = pd.DataFrame(final_rows)

        def color_multiple_div(val):
            style = ''
            if 'HỘI TỤ' in str(val): style += 'color: #00ff88; font-weight: bold;'
            if 'PHÂN KỲ' in str(val): style += 'color: #ff4444; font-weight: bold;'
            return style

        st.dataframe(df_final.style.map(color_multiple_div, subset=['TÍN HIỆU PHÂN KỲ']), 
                     use_container_width=True, hide_index=True)
    else:
        st.warning("Không lấy được dữ liệu.")
