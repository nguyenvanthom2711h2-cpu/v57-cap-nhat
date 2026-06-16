import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time
import warnings

warnings.filterwarnings("ignore")

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="VN Stock Consensus 1H-4H", layout="wide")
st.title("🚀 Bộ Lọc Đồng Thuận Multi-TF (Bản chuẩn 1H-4H)")
st.caption("Nguồn: Yahoo Finance | Logic: RSI Wilder's (alpha=1/14)")

# DANH SÁCH MÃ CHỨNG KHOÁN
SYMBOLS_RAW = [
    'ACB','BCM','BID','BVH','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','PLX','POW','SAB',
    'SHB','SSB','SSI','STB','TCB','TPB','VCB','VHM','VIB','VIC','VJC','VNM','VPB','VRE','LPB','DGC',
    'DPM','DCM','VGC','PVD','PVS','NLG','KDH','KBC','IDC','SZC','GMD','HAH','OIL','FRT','PNJ','TLG',
    'BSI','HSG','NKG','DIG','DXG','PDR','NVL','VIX','VND','HCM','VCI','EIB','MSB','OCB','REE','CTR','VGI','VTP'
]
SYMBOLS = [s + ".VN" for s in SYMBOLS_RAW]

# CÁC CẶP KHUNG GIỜ QUÉT
SCAN_PAIRS = [
    ('1h', '4h'), 
    ('4h', '1d'), 
    ('1d', '3d'), 
    ('3d', '1w')
]

# ==========================================
# 1. HÀM TÍNH TOÁN RSI (ALPHA=1/14 CHUẨN GỐC)
# ==========================================
def calculate_indicators(df):
    if df is None or len(df) < 50: return 0, 0
    try:
        df = df.copy()
        # Đảm bảo lấy đúng cột Close bất kể hoa thường
        df.columns = [c.lower() for c in df.columns]
        close = df['c'] if 'c' in df.columns else df['close']
        
        delta = close.diff()
        gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
        
        # alpha=1/14 là công thức RSI Wilder's chuẩn trong bản gốc của bạn
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        
        df['rsi'] = 100 - (100 / (1 + avg_gain / avg_loss))
        df['rsi9'] = df['rsi'].rolling(9).mean()
        df['rsi45'] = df['rsi'].rolling(45).mean()
        
        last = df.iloc[-1]
        status = 0
        if last['rsi'] > last['rsi9'] and last['rsi'] > last['rsi45']: status = 1
        elif last['rsi'] < last['rsi9'] and last['rsi'] < last['rsi45']: status = -1
        return status, last['rsi'], last.get('c', close.iloc[-1])
    except: return 0, 0, 0

# ==========================================
# 2. HÀM GỘP NẾN (XỬ LÝ RIÊNG CHO YAHOO)
# ==========================================
def resample_stock_data(df, rule):
    if df is None or len(df) < 2: return None
    try:
        df = df.copy()
        # Xử lý Multi-index của yfinance nếu có
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df.index = pd.to_datetime(df.index)
        logic = {'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}
        res = df.resample(rule).apply(logic).dropna().reset_index()
        # Chuyển về tên cột o, h, l, c, v để calculate_indicators đọc
        res.columns = ['ts', 'o', 'h', 'l', 'c', 'v']
        return res
    except: return None

# ==========================================
# 3. QUY TRÌNH QUÉT
# ==========================================
if st.button("🔍 BẮT ĐẦU QUÉT TOÀN BỘ CÁC KHUNG (BAO GỒM 1H-4H)"):
    summary_data = {}
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(SYMBOLS)
    
    for i, sym in enumerate(SYMBOLS):
        short_name = sym.replace(".VN", "")
        status_text.write(f"🔄 Đang quét: **{short_name}**...")
        progress_bar.progress((i + 1) / total)
        
        try:
            # Tải dữ liệu 1H (Yahoo cho phép tối đa 730 ngày, ta lấy 60 ngày là đủ)
            d1h = yf.download(sym, period="60d", interval="1h", progress=False)
            # Tải dữ liệu 1D (Lấy 2 năm)
            d1d = yf.download(sym, period="2y", interval="1d", progress=False)

            if not d1h.empty and not d1d.empty:
                # Chuẩn hóa nến 1H và 1D
                def clean_y_data(df):
                    temp = df.copy()
                    if isinstance(temp.columns, pd.MultiIndex):
                        temp.columns = temp.columns.get_level_values(0)
                    temp = temp[['Open','High','Low','Close','Volume']].rename(
                        columns={'Open':'o','High':'h','Low':'l','Close':'c','Volume':'v'}
                    )
                    return temp.reset_index().rename(columns={temp.index.name:'ts'})

                df_1h = clean_y_data(d1h)
                df_1d = clean_y_data(d1d)

                # Tạo từ điển các khung thời gian
                tfs = {
                    '1h': df_1h,
                    '4h': resample_stock_data(d1h, '4H'),
                    '1d': df_1d,
                    '3d': resample_stock_data(d1d, '3D'),
                    '1w': resample_stock_data(d1d, 'W-MON')
                }
                
                # Tính tín hiệu cho từng khung
                sigs = {}
                for name, df_tf in tfs.items():
                    stat, rsi_val, price_val = calculate_indicators(df_tf)
                    sigs[name] = stat

                # Kiểm tra các cặp đồng thuận (BAO GỒM 1H-4H)
                for tf1, tf2 in SCAN_PAIRS:
                    if sigs.get(tf1) == sigs.get(tf2) and sigs.get(tf1) != 0:
                        label = f"{tf1.upper()}-{tf2.upper()}"
                        
                        # Lấy giá đóng cửa khung 1h làm giá tham chiếu
                        raw_p = df_1h['c'].iloc[-1]
                        price_show = raw_p if raw_p > 1000 else raw_p * 1000
                        
                        if short_name not in summary_data:
                            summary_data[short_name] = {'p': price_show, 'buy': [], 'sell': []}
                        
                        if sigs[tf1] == 1:
                            summary_data[short_name]['buy'].append(label)
                        else:
                            summary_data[short_name]['sell'].append(label)
            
            time.sleep(0.01) # Tránh bị Yahoo rate limit
        except:
            continue

    status_text.empty()
    
    if summary_data:
        st.subheader(f"📊 BẢNG TỔNG HỢP KẾT QUẢ [{datetime.now().strftime('%H:%M:%S')}]")
        final_rows = []
        for s in sorted(summary_data.keys()):
            d = summary_data[s]
            final_rows.append({
                "MÃ": s,
                "GIÁ": f"{d['p']:,.0f}",
                "ĐỒNG THUẬN MUA (🚀)": ", ".join(d['buy']) if d['buy'] else "-",
                "ĐỒNG THUẬN BÁN (🔻)": ", ".join(d['sell']) if d['sell'] else "-"
            })
        
        st.dataframe(pd.DataFrame(final_rows), use_container_width=True, hide_index=True)
    else:
        st.warning("Không tìm thấy mã nào đồng thuận. Lưu ý: Yahoo Finance cập nhật chậm 15 phút so với thực tế.")
