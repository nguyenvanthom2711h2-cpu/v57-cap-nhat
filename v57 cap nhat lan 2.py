import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time
import warnings
import numpy as np
from scipy.signal import argrelextrema

warnings.filterwarnings("ignore")

# --- CẤU HÌNH GIAO DIỆN CSS ---
st.set_page_config(page_title="VN Stock Consensus v159", layout="wide")
st.markdown("""
    <style>
    .main-table { width: 100%; border-collapse: collapse; color: white; background-color: #161a25; }
    .main-table th { background-color: #1f2635; color: #9eb1d1; padding: 12px; text-align: left; border-bottom: 2px solid #2d3748; }
    .main-table td { padding: 10px; border-bottom: 1px solid #2d3748; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-size: 13px; }
    .up-color { color: #00ff88 !important; font-weight: bold; }
    .down-color { color: #ff4444 !important; font-weight: bold; }
    .vni-row { background-color: #1e293b; border-left: 5px solid #00ffcc; }
    </style>
""", unsafe_allow_html=True)

st.title("🚀 Master Stock Scanner v159")
st.caption("Dữ liệu Yahoo Finance | Đồng bộ màu sắc Chữ & Mũi tên | VN-INDEX cố định")

# DANH SÁCH MÃ CHỨNG KHOÁN (Giữ nguyên gốc)
SYMBOLS_RAW = [
    '^VNINDEX',
    'ACB','BID','CTG','HDB','LPB','MBB','MSB','OCB','SHB','STB','TCB','TPB','VCB','VIB','VPB','EIB','SSB','ABB','BVB',
    'SSI','VND','VCI','HCM','VIX','BSI','FTS','MBS','SHS','CTS','AGR','ORS','VDS','TVS','VCK','TCX',
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
# 1. HÀM PHÁT HIỆN PHÂN KỲ (Đồng bộ màu)
# ==========================================
def detect_div_html(df, tf_name, order=5):
    try:
        if df is None or len(df) < 35: return None
        close = df['c'].values
        rsi = df['rsi'].values
        peaks = argrelextrema(rsi, np.greater, order=order)[0]
        troughs = argrelextrema(rsi, np.less, order=order)[0]
        if len(troughs) >= 2:
            t1, t2 = troughs[-2], troughs[-1]
            if close[t2] < close[t1] and rsi[t2] > rsi[t1]:
                if (len(df) - 1 - t2) < 8: 
                    return f"<span class='up-color'>{tf_name}:HỘI TỤ 🚀</span>"
        if len(peaks) >= 2:
            p1, p2 = peaks[-2], peaks[-1]
            if close[p2] > close[p1] and rsi[p2] < rsi[p1]:
                if (len(df) - 1 - p2) < 8: 
                    return f"<span class='down-color'>{tf_name}:PHÂN KỲ 📉</span>"
        return None
    except: return None

# ==========================================
# 2. HÀM TÍNH TOÁN (Đồng bộ màu Chữ & Mũi tên)
# ==========================================
def calculate_indicators(df, tf_name):
    if df is None or len(df) < 50: return 0, 0, None, "", ""
    try:
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        delta = df['c'].diff(); gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        df['rsi'] = 100 - (100 / (1 + avg_gain / avg_loss))
        df['rsi9'] = df['rsi'].rolling(9).mean()
        df['rsi45'] = df['rsi'].rolling(45).mean()
        df['ma10'] = df['c'].rolling(10).mean()
        df['ma20'] = df['c'].rolling(20).mean()
        df['ma50'] = df['c'].rolling(50).mean()
        
        last = df.iloc[-1]
        t_upper = tf_name.upper()
        
        # Bọc cả Tên khung và Mũi tên vào trong class màu
        if last['c'] > last['ma50']:
            m50_label = f"<span class='up-color'>{t_upper}↑</span>"
        else:
            m50_label = f"<span class='down-color'>{t_upper}↓</span>"
            
        if last['ma10'] > last['ma20']:
            m1020_label = f"<span class='up-color'>{t_upper}↑</span>"
        else:
            m1020_label = f"<span class='down-color'>{t_upper}↓</span>"
        
        div_msg = detect_div_html(df, t_upper)
        status_rsi = 0
        if last['rsi'] > last['rsi9'] and last['rsi'] > last['rsi45']: status_rsi = 1
        elif last['rsi'] < last['rsi9'] and last['rsi'] < last['rsi45']: status_rsi = -1
        
        return status_rsi, last['c'], div_msg, m50_label, m1020_label
    except: return 0, 0, None, "", ""

# ==========================================
# 3. HÀM GỘP NẾN (GIỮ NGUYÊN)
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
        short_name = sym.replace(".VN", "").replace("^", "")
        status_text.write(f"🔄 Đang quét: **{short_name}**...")
        progress_bar.progress((i + 1) / len(SYMBOLS))
        
        try:
            d1h = yf.download(sym, period="60d", interval="1h", progress=False)
            d1d = yf.download(sym, period="2y", interval="1d", progress=False)

            if not d1d.empty:
                if isinstance(d1h.columns, pd.MultiIndex): d1h.columns = d1h.columns.get_level_values(0)
                if isinstance(d1d.columns, pd.MultiIndex): d1d.columns = d1d.columns.get_level_values(0)

                df_d = d1d[['Open','High','Low','Close','Volume']].rename(columns={'Open':'o','High':'h','Low':'l','Close':'c','Volume':'v'})
                tfs_data = {'1d': df_d.reset_index().rename(columns={'Date':'ts'}), 
                            '3d': resample_stock_data(d1d, '3D'), 
                            '1w': resample_stock_data(d1d, 'W-MON')}
                if not d1h.empty:
                    df_h = d1h[['Open','High','Low','Close','Volume']].rename(columns={'Open':'o','High':'h','Low':'l','Close':'c','Volume':'v'})
                    df_h_reset = df_h.reset_index()
                    tfs_data['1h'] = df_h_reset.rename(columns={df_h_reset.columns[0]:'ts'})
                    tfs_data['4h'] = resample_stock_data(d1h, '4H')

                sigs = {}; prices = {}; div_list = []; ma50_list = []; ma1020_list = []
                for name, df_tf in tfs_data.items():
                    stat, p, div_m, m50, m1020 = calculate_indicators(df_tf, name)
                    sigs[name] = stat
                    prices[name] = p
                    if div_m: div_list.append(div_m)
                    ma50_list.append(m50)
                    ma1020_list.append(m1020)
                
                p_current = prices.get('1h', prices.get('1d', 0))
                p_display = p_current if (sym.startswith('^') or p_current > 1000) else p_current * 1000

                c_buy = []; c_sell = []
                for tf1, tf2 in SCAN_PAIRS:
                    if sigs.get(tf1) is not None and sigs.get(tf1) == sigs.get(tf2) and sigs.get(tf1) != 0:
                        lbl = f"{tf1.upper()}-{tf2.upper()}"
                        if sigs[tf1] == 1: c_buy.append(f"<span class='up-color'>{lbl}</span>")
                        else: c_sell.append(f"<span class='down-color'>{lbl}</span>")

                if sym == "^VNINDEX" or c_buy or c_sell:
                    summary_data[short_name] = {
                        'p': p_display, 'buy': c_buy, 'sell': c_sell,
                        'divs': div_list, 'ma50': ma50_list, 'ma1020': ma1020_list,
                        'is_vni': (sym == "^VNINDEX")
                    }
            time.sleep(0.01)
        except: continue

    status_text.empty()
    if summary_data:
        # XÂY DỰNG BẢNG HTML
        html_table = "<table class='main-table'><thead><tr>"
        columns = ["MÃ", "GIÁ", "MUA (🚀)", "BÁN (🔻)", "PHÂN KỲ ĐA KHUNG", "GIÁ / MA50", "MA 10 / 20"]
        for col in columns: html_table += f"<th>{col}</th>"
        html_table += "</tr></thead><tbody>"

        sorted_keys = sorted([k for k in summary_data.keys() if k != "VNINDEX"])
        order = (["VNINDEX"] if "VNINDEX" in summary_data else []) + sorted_keys

        for s in order:
            d = summary_data[s]
            row_style = "class='vni-row'" if d['is_vni'] else ""
            name_label = f"⭐ <b>{s}</b>" if d['is_vni'] else s
            price_label = f"{d['p']:,.2f}" if d['is_vni'] else f"{d['p']:,.0f}"
            
            html_table += f"<tr {row_style}>"
            html_table += f"<td>{name_label}</td>"
            html_table += f"<td>{price_label}</td>"
            html_table += f"<td>{' | '.join(d['buy']) if d['buy'] else '-'}</td>"
            html_table += f"<td>{' | '.join(d['sell']) if d['sell'] else '-'}</td>"
            html_table += f"<td>{' | '.join(d['divs']) if d['divs'] else '-'}</td>"
            html_table += f"<td>{' | '.join(d['ma50'])}</td>"
            html_table += f"<td>{' | '.join(d['ma1020'])}</td>"
            html_table += "</tr>"

        html_table += "</tbody></table>"
        st.write(html_table, unsafe_allow_html=True)
    else:
        st.warning("Không tìm thấy mã nào thỏa mãn điều kiện lọc.")
