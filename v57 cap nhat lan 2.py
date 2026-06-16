import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import warnings

# Thử import thư viện vnstock
try:
    from vnstock import Quote
except ImportError:
    st.error("❌ Lỗi: Chưa cài đặt thư viện 'vnstock'. Hãy tạo file 'requirements.txt' trên GitHub và thêm dòng 'vnstock' vào đó.")
    st.stop()

warnings.filterwarnings("ignore")

# --- CẤU HÌNH ---
st.set_page_config(page_title="Stock Scanner Web", layout="wide")
st.title("🚀 Bộ Lọc Chứng Khoán Multi-TF (Bản Web)")

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

# --- THỰC THI ---
if st.button("🚀 BẮT ĐẦU QUÉT"):
    summary_data = {}
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(SYMBOLS)
    
    for idx, sym in enumerate(SYMBOLS):
        progress_bar.progress((idx + 1) / total)
        status_text.code(f"🔄 Đang quét mã: {sym} ({idx+1}/{total})")
        
        try:
            # Lấy dữ liệu nguồn (Mặc định dùng VCI)
            q = Quote(symbol=sym, source='vci')
            
            # Lấy dữ liệu 1H và 1D
            df_h_raw = q.history(start=(datetime.now() - timedelta(days=70)).strftime('%Y-%m-%d'), interval='1H')
            df_d_raw = q.history(start='2022-01-01', interval='1D')

            if df_h_raw is not None and not df_h_raw.empty and df_d_raw is not None and not df_d_raw.empty:
                # Chuẩn hóa cột
                df_h = df_h_raw.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})
                df_d = df_d_raw.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})

                tfs = {
                    '1h': df_h,
                    '4h': resample_stock_data(df_h, '4H'),
                    '1d': df_d,
                    '3d': resample_stock_data(df_d, '3D'),
                    '1w': resample_stock_data(df_d, 'W-MON')
                }
                
                signals = {}
                for name, df_tf in tfs.items():
                    sig, _ = calculate_indicators(df_tf)
                    signals[name] = sig
                
                last_p = df_h['c'].iloc[-1]
                
                for tf1, tf2 in SCAN_PAIRS:
                    if signals.get(tf1) == signals.get(tf2) and signals.get(tf1) != 0:
                        if sym not in summary_data:
                            # Quy đổi giá sang VNĐ (ví dụ 35.5 -> 35,500)
                            price_vnd = last_p if last_p > 1000 else last_p * 1000
                            summary_data[sym] = {'p': price_vnd, 'buy': [], 'sell': []}
                        
                        label = f"{tf1.upper()}-{tf2.upper()}"
                        if signals[tf1] == 1: summary_data[sym]['buy'].append(label)
                        else: summary_data[sym]['sell'].append(label)
            
            # Nghỉ 0.2 giây để tránh bị server dữ liệu chặn
            time.sleep(0.2)

        except Exception as e:
            continue

    status_text.empty()
    
    if summary_data:
        st.subheader(f"📊 Kết Quả Tổng Hợp ({datetime.now().strftime('%H:%M:%S')})")
        final_list = []
        for s, d in summary_data.items():
            final_list.append({
                "MÃ": s,
                "GIÁ": f"{d['p']:,.0f}",
                "MUA (🚀)": ", ".join(d['buy']) if d['buy'] else "-",
                "BÁN (🔻)": ", ".join(d['sell']) if d['sell'] else "-"
            })
        st.dataframe(pd.DataFrame(final_list), use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Không tìm thấy tín hiệu hoặc server dữ liệu đang bận. Hãy thử lại sau ít phút.")
