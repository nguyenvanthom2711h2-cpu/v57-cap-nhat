import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import warnings

# Import vnstock
try:
    from vnstock.api.quote import Quote
except:
    from vnstock import Quote

warnings.filterwarnings("ignore")

# CẤU HÌNH GIAO DIỆN
st.set_page_config(page_title="Bộ Lọc Cổ Phiếu Đồng Thuận", layout="wide")
st.title("🚀 Bộ Lọc Cổ Phiếu Đồng Thuận Multi-TF")
st.write("Hệ thống tự động quét RSI đồng thuận trên nhiều khung thời gian.")

# DANH SÁCH MÃ
SYMBOLS = [
    'ACB','BCM','BID','BVH','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','PLX','POW','SAB',
    'SHB','SSB','SSI','STB','TCB','TPB','VCB','VHM','VIB','VIC','VJC','VNM','VPB','VRE','LPB','DGC',
    'DPM','DCM','VGC','PVD','PVS','NLG','KDH','KBC','IDC','SZC','GMD','HAH','OIL','FRT','PNJ','TLG',
    'BSI','HSG','NKG','DIG','DXG','PDR','NVL','VIX','VCK','TCX','DGW','VND','HCM','VCI','EIB','MSB',
    'OCB','REE','CTR','VGI','VTP'
]

PAIRS = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]

# HÀM TÍNH TOÁN
def calculate_indicators(df):
    if df is None or len(df) < 50: return 0, 0
    df = df.copy()
    delta = df['c'].diff()
    gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + avg_gain / avg_loss))
    df['rsi9'] = df['rsi'].rolling(9).mean()
    df['rsi45'] = df['rsi'].rolling(45).mean()
    last = df.iloc[-1]
    if last['rsi'] > last['rsi9'] and last['rsi'] > last['rsi45']: return 1, last['c']
    if last['rsi'] < last['rsi9'] and last['rsi'] < last['rsi45']: return -1, last['c']
    return 0, last['c']

def resample_data(df, rule):
    df['ts'] = pd.to_datetime(df['ts'])
    df.set_index('ts', inplace=True)
    logic = {'o':'first', 'h':'max', 'l':'min', 'c':'last', 'v':'sum'}
    return df.resample(rule).apply(logic).dropna().reset_index()

# NÚT BẤM CHẠY
if st.button('🚀 BẮT ĐẦU QUÉT DỮ LIỆU'):
    summary = {}
    progress_text = st.empty()
    bar = st.progress(0)
    
    total = len(PAIRS) * len(SYMBOLS)
    count = 0

    for tf1, tf2 in PAIRS:
        label = f"{tf1.upper()}-{tf2.upper()}"
        for sym in SYMBOLS:
            count += 1
            bar.progress(count / total)
            progress_text.text(f"🔍 Đang quét {label}: {sym}...")
            
            try:
                q = Quote(symbol=sym, source='VCI')
                # Lấy data khung nhỏ
                if 'h' in tf1:
                    df_raw = q.history(start=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'), interval='1H')
                    df_raw = df_raw.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})
                    df1 = df_raw if tf1 == '1h' else resample_data(df_raw, '4H')
                else:
                    df_raw = q.history(start='2022-01-01', interval='1D')
                    df_raw = df_raw.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})
                    df1 = df_raw if tf1 == '1d' else resample_data(df_raw, '3D' if tf1=='3d' else 'W-MON')
                
                # Lấy data khung lớn
                if 'h' in tf2:
                    df2 = resample_data(df_raw, '4H')
                else:
                    if 'h' in tf1: # Nếu cặp 4h-1d
                        df_d = q.history(start='2022-01-01', interval='1D')
                        df_d = df_d.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})
                        df2 = df_d
                    else:
                        df2 = resample_data(df_raw, '3D' if tf2=='3d' else 'W-MON')

                s1, p1 = calculate_indicators(df1)
                s2, p2 = calculate_indicators(df2)

                if s1 == s2 and s1 != 0:
                    price = p1 if p1 > 1000 else p1 * 1000
                    if sym not in summary: summary[sym] = {'Giá': price, 'MUA': [], 'BÁN': []}
                    if s1 == 1: summary[sym]['MUA'].append(label)
                    else: summary[sym]['BÁN'].append(label)
            except:
                continue
    
    progress_text.success("✅ Đã quét xong!")
    
    # HIỂN THỊ KẾT QUẢ
    if summary:
        st.subheader(f"📊 Bảng Tổng Hợp Tín Hiệu ({datetime.now().strftime('%H:%M:%S')})")
        data_rows = []
        for s, d in summary.items():
            data_rows.append({
                "MÃ": s,
                "GIÁ": f"{d['Giá']:,.0f}",
                "ĐỒNG THUẬN MUA (🚀)": ", ".join(d['MUA']),
                "ĐỒNG THUẬN BÁN (🔻)": ", ".join(d['BÁN'])
            })
        st.table(pd.DataFrame(data_rows))
    else:
        st.warning("Không tìm thấy tín hiệu đồng thuận nào.")
