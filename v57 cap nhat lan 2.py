import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import warnings
import time
from concurrent.futures import ThreadPoolExecutor

# Thử import thư viện vnstock
try:
    from vnstock import stock_historical_data
except ImportError:
    st.error("❌ Thiếu thư viện vnstock. Hãy kiểm tra file requirements.txt")
    st.stop()

warnings.filterwarnings("ignore")

# --- CẤU HÌNH ---
st.set_page_config(page_title="Stock Scanner Turbo", layout="wide")
st.title("🚀 Bộ Lọc Chứng Khoán Multi-TF (Bản Siêu Tốc)")

SYMBOLS = [
    'ACB','BCM','BID','BVH','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','PLX','POW','SAB',
    'SHB','SSB','SSI','STB','TCB','TPB','VCB','VHM','VIB','VIC','VJC','VNM','VPB','VRE','LPB','DGC',
    'DPM','DCM','VGC','PVD','PVS','NLG','KDH','KBC','IDC','SZC','GMD','HAH','OIL','FRT','PNJ','TLG',
    'BSI','HSG','NKG','DIG','DXG','PDR','NVL','VIX','VCK','TCX','DGW','VND','HCM','VCI','EIB','MSB',
    'OCB','REE','CTR','VGI','VTP'
]

SCAN_PAIRS = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]

# --- HÀM TÍNH TOÁN ---
def calculate_indicators(df):
    if df is None or len(df) < 50: return 0, 0
    try:
        # Vnstock trả về tên cột: time, open, high, low, close, volume
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

# --- HÀM QUÉT TỪNG MÃ (CHẠY ĐA LUỒNG) ---
def scan_single_symbol(sym):
    try:
        # Lấy dữ liệu 1H và 1D từ TCBS (Nhanh nhất)
        end_d = datetime.now().strftime('%Y-%m-%d')
        start_h = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
        start_d = '2022-01-01'
        
        df_h = stock_historical_data(symbol=sym, start_date=start_h, end_date=end_d, resolution='1H', type='stock', source='tcbs')
        df_d = stock_historical_data(symbol=sym, start_date=start_d, end_date=end_d, resolution='1D', type='stock', source='tcbs')

        if df_h is None or df_h.empty or df_d is None or df_d.empty:
            return None

        tfs = {
            '1h': df_h,
            '4h': resample_stock_data(df_h, '4h'),
            '1d': df_d,
            '3d': resample_stock_data(df_d, '3D'),
            '1w': resample_stock_data(df_d, 'W-MON')
        }
        
        signals = {}
        for name, df_tf in tfs.items():
            sig, _ = calculate_indicators(df_tf)
            signals[name] = sig
        
        last_p = df_h['close'].iloc[-1]
        price_vnd = last_p if last_p > 1000 else last_p * 1000
        
        res = {'sym': sym, 'p': price_vnd, 'buy': [], 'sell': []}
        found = False
        for tf1, tf2 in SCAN_PAIRS:
            if signals.get(tf1) == signals.get(tf2) and signals.get(tf1) != 0:
                label = f"{tf1.upper()}-{tf2.upper()}"
                if signals[tf1] == 1: res['buy'].append(label)
                else: res['sell'].append(label)
                found = True
        
        return res if found else None
    except:
        return None

# --- GIAO DIỆN CHÍNH ---
if st.button("🚀 BẮT ĐẦU QUÉT SIÊU TỐC"):
    st.info("Đang sử dụng xử lý đa luồng để tăng tốc quét...")
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    start_time = time.time()
    all_results = []
    
    # Sử dụng ThreadPoolExecutor để chạy song song 5 mã một lúc
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(scan_single_symbol, sym): sym for sym in SYMBOLS}
        
        for i, future in enumerate(futures):
            res = future.result()
            if res:
                all_results.append(res)
            
            # Cập nhật UI
            progress = (i + 1) / len(SYMBOLS)
            progress_bar.progress(progress)
            status_text.text(f"✅ Đã xử lý {i+1}/{len(SYMBOLS)} mã...")

    end_time = time.time()
    status_text.success(f"Hoàn tất quét trong {round(end_time - start_time, 1)} giây!")

    if all_results:
        st.subheader(f"📊 Kết Quả Tổng Hợp ({datetime.now().strftime('%H:%M:%S')})")
        final_list = []
        for d in all_results:
            final_list.append({
                "MÃ": d['sym'],
                "GIÁ": f"{d['p']:,.0f}",
                "MUA (🚀)": ", ".join(d['buy']) if d['buy'] else "-",
                "BÁN (🔻)": ", ".join(d['sell']) if d['sell'] else "-"
            })
        st.dataframe(pd.DataFrame(final_list), use_container_width=True, hide_index=True)
    else:
        st.warning("Không tìm thấy tín hiệu đồng thuận nào.")

st.divider()
st.caption("Lưu ý: Nếu bị đứng, hãy nhấn F5 để tải lại trang. Tốc độ phụ thuộc vào đường truyền tới server TCBS.")
