import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import warnings

# Import vnstock
try:
    from vnstock import Quote
except:
    st.error("Thiếu thư viện vnstock. Hãy thêm 'vnstock' vào file requirements.txt")

warnings.filterwarnings("ignore")

# CẤU HÌNH GIAO DIỆN
st.set_page_config(page_title="Screener Pro", layout="wide")
st.title("🚀 Bộ Lọc Cổ Phiếu Đồng Thuận Multi-TF")

# DANH SÁCH MÃ (Rút gọn một chút để quét nhanh hơn hoặc giữ nguyên tùy bạn)
SYMBOLS = [
    'ACB','BCM','BID','BVH','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','PLX','POW','SAB',
    'SHB','SSB','SSI','STB','TCB','TPB','VCB','VHM','VIB','VIC','VJC','VNM','VPB','VRE','LPB','DGC',
    'DPM','DCM','VGC','PVD','PVS','NLG','KDH','KBC','IDC','SZC','GMD','HAH','OIL','FRT','PNJ','TLG',
    'BSI','HSG','NKG','DIG','DXG','PDR','NVL','VIX','VCK','TCX','DGW','VND','HCM','VCI','EIB','MSB',
    'OCB','REE','CTR','VGI','VTP'
]

PAIRS = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]

def calculate_rsi_signal(df):
    """Tính RSI và trả về 1 (MUA), -1 (BÁN), 0 (KO)"""
    if df is None or len(df) < 50: 
        return 0, 0
    try:
        df = df.copy()
        delta = df['c'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        df['rsi'] = 100 - (100 / (1 + avg_gain / avg_loss))
        df['rsi9'] = df['rsi'].rolling(9).mean()
        df['rsi45'] = df['rsi'].rolling(45).mean()
        
        last = df.iloc[-1]
        if last['rsi'] > last['rsi9'] and last['rsi'] > last['rsi45']: return 1, last['c']
        if last['rsi'] < last['rsi9'] and last['rsi'] < last['rsi45']: return -1, last['c']
    except:
        pass
    return 0, 0

def resample_data(df, rule):
    try:
        df['ts'] = pd.to_datetime(df['ts'])
        df.set_index('ts', inplace=True)
        logic = {'o':'first', 'h':'max', 'l':'min', 'c':'last', 'v':'sum'}
        res = df.resample(rule).apply(logic).dropna().reset_index()
        return res
    except:
        return None

# GIAO DIỆN NÚT BẤM
if st.button('🚀 BẮT ĐẦU QUÉT DỮ LIỆU'):
    summary = {}
    log_area = st.empty()
    progress_bar = st.progress(0)
    
    total_steps = len(SYMBOLS)
    count = 0

    for sym in SYMBOLS:
        count += 1
        progress_bar.progress(count / total_steps)
        log_area.code(f"🔄 Đang xử lý: {sym}...")
        
        try:
            # 1. Lấy dữ liệu 1H (90 ngày)
            q_h = Quote(symbol=sym, source='DNSE') # Đổi sang DNSE cho ổn định
            df_h_raw = q_h.history(start=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'), interval='1H')
            df_h_raw = df_h_raw.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})
            
            # 2. Lấy dữ liệu 1D (Từ 2021 để đủ nến cho khung tuần)
            df_d_raw = q_h.history(start='2021-01-01', interval='1D')
            df_d_raw = df_d_raw.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})

            # Chuẩn bị các khung thời gian
            tfs = {
                '1H': df_h_raw,
                '4H': resample_data(df_h_raw, '4H'),
                '1D': df_d_raw,
                '3D': resample_data(df_d_raw, '3D'),
                '1W': resample_data(df_d_raw, 'W-MON')
            }

            # Tính tín hiệu cho từng khung
            signals = {}
            prices = {}
            for name, df in tfs.items():
                sig, price = calculate_rsi_signal(df)
                signals[name] = sig
                prices[name] = price

            # Kiểm tra các cặp đồng thuận
            for tf1, tf2 in PAIRS:
                s1, s2 = signals.get(tf1.upper(), 0), signals.get(tf2.upper(), 0)
                if s1 == s2 and s1 != 0:
                    pair_label = f"{tf1.upper()}-{tf2.upper()}"
                    p = prices.get(tf1.upper(), 0)
                    price_val = p if p > 1000 else p * 1000
                    
                    if sym not in summary:
                        summary[sym] = {'Giá': price_val, 'MUA': [], 'BÁN': []}
                    
                    if s1 == 1:
                        summary[sym]['MUA'].append(pair_label)
                    else:
                        summary[sym]['BÁN'].append(pair_label)
        except Exception as e:
            continue

    log_area.empty()
    
    if summary:
        st.success(f"✅ Tìm thấy {len(summary)} mã có tín hiệu đồng thuận!")
        data_rows = []
        for s, d in summary.items():
            data_rows.append({
                "MÃ": s,
                "GIÁ": f"{d['Giá']:,.0f}",
                "ĐỒNG THUẬN MUA (🚀)": ", ".join(d['MUA']) if d['MUA'] else "-",
                "ĐỒNG THUẬN BÁN (🔻)": ", ".join(d['BÁN']) if d['BÁN'] else "-"
            })
        st.dataframe(pd.DataFrame(data_rows), use_container_width=True)
    else:
        st.warning("⚠️ Không tìm thấy tín hiệu đồng thuận nào. Có thể thị trường đang đi ngang hoặc lỗi kết nối dữ liệu.")
