import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import warnings
import time

# Import vnstock
try:
    from vnstock import Quote
except ImportError:
    st.error("Thiếu thư viện vnstock. Vui lòng kiểm tra lại file requirements.txt")

warnings.filterwarnings("ignore")

# ==========================================
# CẤU HÌNH GIAO DIỆN
# ==========================================
st.set_page_config(page_title="Stock Screener Pro", layout="wide")
st.title("🚀 Bộ Lọc Cổ Phiếu Đồng Thuận Multi-TF")

SYMBOLS = [
    'ACB','BCM','BID','BVH','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','PLX','POW','SAB',
    'SHB','SSB','SSI','STB','TCB','TPB','VCB','VHM','VIB','VIC','VJC','VNM','VPB','VRE','LPB','DGC',
    'DPM','DCM','VGC','PVD','PVS','NLG','KDH','KBC','IDC','SZC','GMD','HAH','OIL','FRT','PNJ','TLG',
    'BSI','HSG','NKG','DIG','DXG','PDR','NVL','VIX','VCK','TCX','DGW','VND','HCM','VCI','EIB','MSB',
    'OCB','REE','CTR','VGI','VTP'
]

SCAN_PAIRS = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]

# ==========================================
# HÀM XỬ LÝ DỮ LIỆU
# ==========================================
def calculate_indicators(df):
    if df is None or len(df) < 50: return 0, 0
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
    except: pass
    return 0, 0

def resample_stock_data(df, rule):
    if df is None or len(df) < 2: return None
    try:
        df = df.copy()
        df['ts'] = pd.to_datetime(df['ts'])
        df.set_index('ts', inplace=True)
        logic = {'o':'first', 'h':'max', 'l':'min', 'c':'last', 'v':'sum'}
        return df.resample(rule).apply(logic).dropna().reset_index()
    except: return None

# ==========================================
# THỰC THI QUÉT
# ==========================================
if st.button("🚀 BẮT ĐẦU QUÉT TOÀN BỘ MÃ"):
    summary_data = {}
    log_expander = st.expander("Nhật ký quét hệ thống", expanded=True)
    progress_bar = st.progress(0)
    
    total_symbols = len(SYMBOLS)
    
    # Sử dụng nguồn 'vci' hoặc 'kbs' thay vì 'DNSE'
    SOURCE = 'vci' 

    for idx, symbol in enumerate(SYMBOLS):
        progress_bar.progress((idx + 1) / total_symbols)
        with log_expander:
            st.write(f"🔄 Đang xử lý: **{symbol}**...")

        try:
            q = Quote(symbol=symbol, source=SOURCE)
            
            # Lấy dữ liệu 1H và 1D
            df_h_raw = q.history(start=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'), interval='1H')
            df_d_raw = q.history(start='2022-01-01', interval='1D')

            # Chuẩn hóa tên cột (Vnstock thường dùng: time, open, high, low, close, volume)
            def clean_df(df):
                if df is not None and not df.empty:
                    return df.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})
                return None

            df_h = clean_df(df_h_raw)
            df_d = clean_df(df_d_raw)

            if df_h is None and df_d is None:
                continue

            # Tạo danh sách các khung thời gian từ dữ liệu đã lấy
            tfs = {
                '1h': df_h,
                '4h': resample_stock_data(df_h, '4H'),
                '1d': df_d,
                '3d': resample_stock_data(df_d, '3D'),
                '1w': resample_stock_data(df_d, 'W-MON')
            }

            # Tính tín hiệu
            signals = {}
            current_price = 0
            for tf_name, df_tf in tfs.items():
                sig, p = calculate_indicators(df_tf)
                signals[tf_name] = sig
                if tf_name == '1h' and p > 0: current_price = p
                elif current_price == 0 and p > 0: current_price = p

            # Kiểm tra đồng thuận
            for tf1, tf2 in SCAN_PAIRS:
                s1, s2 = signals.get(tf1, 0), signals.get(tf2, 0)
                if s1 == s2 and s1 != 0:
                    label = f"{tf1.upper()}-{tf2.upper()}"
                    # Quy đổi giá nếu cần (ví dụ giá 35.5 -> 35,500)
                    price_display = current_price if current_price > 1000 else current_price * 1000
                    
                    if symbol not in summary_data:
                        summary_data[symbol] = {'price': price_display, 'buy': [], 'sell': []}
                    
                    if s1 == 1: summary_data[symbol]['buy'].append(label)
                    else: summary_data[symbol]['sell'].append(label)
            
            # Nghỉ rất ngắn để tránh bị server chặn IP
            time.sleep(0.1)

        except Exception as e:
            with log_expander:
                st.error(f"❌ {symbol}: {str(e)}")
            continue

    st.divider()
    if summary_data:
        st.subheader(f"📊 Bảng Kết Quả Tổng Hợp ({datetime.now().strftime('%H:%M:%S')})")
        rows = []
        for s in sorted(summary_data.keys()):
            d = summary_data[s]
            rows.append({
                "MÃ": s,
                "GIÁ": f"{d['price']:,.0f}",
                "ĐỒNG THUẬN MUA (🚀)": ", ".join(d['buy']) if d['buy'] else "-",
                "ĐỒNG THUẬN BÁN (🔻)": ", ".join(d['sell']) if d['sell'] else "-"
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Đã quét xong nhưng không có mã nào đạt điều kiện đồng thuận tại thời điểm này.")
