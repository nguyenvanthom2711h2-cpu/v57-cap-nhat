import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import warnings
import time

# Import vnstock - Sử dụng hàm historical data trực tiếp
try:
    from vnstock import stock_historical_data
except ImportError:
    st.error("Lỗi: Không tìm thấy thư viện vnstock. Vui lòng kiểm tra requirements.txt")

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
# HÀM TÍNH TOÁN
# ==========================================
def calculate_indicators(df):
    if df is None or len(df) < 50: return 0, 0
    try:
        df = df.copy()
        # Đảm bảo tên cột chuẩn cho tính toán
        delta = df['close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        df['rsi'] = 100 - (100 / (1 + avg_gain / avg_loss))
        df['rsi9'] = df['rsi'].rolling(9).mean()
        df['rsi45'] = df['rsi'].rolling(45).mean()
        
        last = df.iloc[-1]
        if last['rsi'] > last['rsi9'] and last['rsi'] > last['rsi45']: return 1, last['close']
        if last['rsi'] < last['rsi9'] and last['rsi'] < last['rsi45']: return -1, last['close']
    except: pass
    return 0, 0

def resample_stock_data(df, rule):
    if df is None or len(df) < 2: return None
    try:
        df = df.copy()
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        logic = {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}
        return df.resample(rule).apply(logic).dropna().reset_index()
    except: return None

# ==========================================
# THỰC THI QUÉT
# ==========================================
if st.button("🚀 BẮT ĐẦU QUÉT TOÀN BỘ MÃ"):
    summary_data = {}
    log_area = st.empty()
    progress_bar = st.progress(0)
    
    total_symbols = len(SYMBOLS)
    
    # Sử dụng nguồn 'kbs' thay vì 'vci' để tránh Connection Error
    SOURCE = 'kbs'

    for idx, symbol in enumerate(SYMBOLS):
        progress_bar.progress((idx + 1) / total_symbols)
        log_area.code(f"🔄 Đang xử lý mã: {symbol} ({idx+1}/{total_symbols})")

        try:
            # Lấy dữ liệu 1H (Intraday)
            # Lưu ý: Một số nguồn có thể dùng tham số resolution khác nhau, ở đây ta dùng '1H'
            df_h = stock_historical_data(symbol=symbol, 
                                       start_date=(datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d'), 
                                       end_date=datetime.now().strftime('%Y-%m-%d'), 
                                       resolution='1H', type='stock', source=SOURCE)
            
            # Lấy dữ liệu 1D
            df_d = stock_historical_data(symbol=symbol, 
                                       start_date='2022-01-01', 
                                       end_date=datetime.now().strftime('%Y-%m-%d'), 
                                       resolution='1D', type='stock', source=SOURCE)

            if df_h is None or df_h.empty or df_d is None or df_d.empty:
                continue

            # Tạo danh sách các khung thời gian
            tfs = {
                '1h': df_h,
                '4h': resample_stock_data(df_h, '4h'),
                '1d': df_d,
                '3d': resample_stock_data(df_d, '3D'),
                '1w': resample_stock_data(df_d, 'W-MON')
            }

            # Tính tín hiệu
            signals = {}
            current_price = df_h['close'].iloc[-1]
            for tf_name, df_tf in tfs.items():
                sig, _ = calculate_indicators(df_tf)
                signals[tf_name] = sig

            # Kiểm tra đồng thuận
            for tf1, tf2 in SCAN_PAIRS:
                s1, s2 = signals.get(tf1, 0), signals.get(tf2, 0)
                if s1 == s2 and s1 != 0:
                    label = f"{tf1.upper()}-{tf2.upper()}"
                    price_val = current_price if current_price > 1000 else current_price * 1000
                    
                    if symbol not in summary_data:
                        summary_data[symbol] = {'price': price_val, 'buy': [], 'sell': []}
                    
                    if s1 == 1: summary_data[symbol]['buy'].append(label)
                    else: summary_data[symbol]['sell'].append(label)
            
            # Nghỉ 0.5 giây giữa mỗi mã để tránh bị Connection Error
            time.sleep(0.5)

        except Exception as e:
            # Nếu lỗi kết nối, nghỉ lâu hơn một chút
            if "Connection" in str(e) or "Retry" in str(e):
                log_area.warning(f"⚠️ {symbol} bị nghẽn mạng, đang thử chờ nghỉ...")
                time.sleep(2)
            continue

    log_area.empty()
    
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
        st.warning("⚠️ Không tìm thấy mã nào đạt điều kiện hoặc dữ liệu tạm thời bị gián đoạn. Hãy thử lại sau ít phút.")
