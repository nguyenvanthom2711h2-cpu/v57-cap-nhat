import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import warnings

# Tắt cảnh báo
warnings.filterwarnings("ignore")

# Import vnstock bản mới nhất (4.0+)
try:
    from vnstock import Vnstock
except ImportError:
    st.error("❌ Không tìm thấy thư viện vnstock. Hãy kiểm tra file requirements.txt")
    st.stop()

st.set_page_config(page_title="VnStock Consensus 4.0", layout="wide")
st.title("🚀 Bộ Lọc Chứng Khoán Multi-TF (Vnstock 4.0)")

# --- DANH SÁCH MÃ ---
SYMBOLS = ['ACB','BID','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','SSI','STB','TCB','VCB','VHM','VIC','VNM','VPB','VRE']

# --- HÀM TÍNH RSI ---
def calculate_rsi_consensus(df):
    if df is None or len(df) < 50: return 0, 0
    try:
        # Vnstock 4.0 trả về tên cột có thể khác nhau tùy nguồn, ta ép về chữ thường
        df.columns = [c.lower() for c in df.columns]
        close = df['close']
        
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        rsi_ma9 = rsi.rolling(9).mean()
        rsi_ma45 = rsi.rolling(45).mean()
        
        curr_rsi = rsi.iloc[-1]
        if curr_rsi > rsi_ma9.iloc[-1] and curr_rsi > rsi_ma45.iloc[-1]: return 1, close.iloc[-1]
        if curr_rsi < rsi_ma9.iloc[-1] and curr_rsi < rsi_ma45.iloc[-1]: return -1, close.iloc[-1]
    except: pass
    return 0, 0

# --- HÀM GỘP NẾN ---
def resample_ohlc(df, rule):
    try:
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        res = df.resample(rule).agg({'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'})
        return res.dropna().reset_index()
    except: return None

# --- GIAO DIỆN CHÍNH ---
if st.button("🔍 BẮT ĐẦU QUÉT"):
    results = []
    progress_bar = st.progress(0)
    log_area = st.empty()
    
    # Khởi tạo Vnstock 4.0
    vnstock = Vnstock()

    for i, sym in enumerate(SYMBOLS):
        log_area.info(f"🔄 Đang quét mã: **{sym}**...")
        progress_bar.progress((i + 1) / len(SYMBOLS))
        
        try:
            # Khởi tạo đối tượng stock cho từng mã
            # Thử nguồn TCBS, nếu lỗi tự động bạn có thể đổi sang 'VCI' hoặc 'KBS'
            s = vnstock.stock(symbol=sym, source='TCBS')
            
            # Lấy dữ liệu (Bản 4.0 dùng count hoặc interval)
            df_h = s.quote.history(interval='1H', count=500)
            df_d = s.quote.history(interval='1D', count=500)

            if df_h is not None and not df_h.empty and df_d is not None and not df_d.empty:
                # Tạo các khung thời gian
                tfs = {
                    '1h': df_h,
                    '4h': resample_ohlc(df_h, '4H'),
                    '1d': df_d,
                    '3d': resample_ohlc(df_d, '3D'),
                    '1w': resample_ohlc(df_d, 'W-MON')
                }
                
                sigs = {name: calculate_rsi_consensus(tf_df)[0] for name, tf_df in tfs.items()}
                
                # Lấy giá đóng cửa cuối cùng
                df_d.columns = [c.lower() for c in df_d.columns]
                price = df_d['close'].iloc[-1]
                
                buy_found = []
                sell_found = []
                
                pairs = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]
                for tf1, tf2 in pairs:
                    if sigs[tf1] == sigs[tf2] and sigs[tf1] != 0:
                        lbl = f"{tf1.upper()}-{tf2.upper()}"
                        if sigs[tf1] == 1: buy_found.append(lbl)
                        else: sell_found.append(lbl)
                
                if buy_found or sell_found:
                    p_final = price if price > 1000 else price * 1000
                    results.append({
                        "MÃ": sym,
                        "GIÁ": f"{p_final:,.0f}",
                        "MUA (🚀)": ", ".join(buy_found) if buy_found else "-",
                        "BÁN (🔻)": ", ".join(sell_found) if sell_found else "-"
                    })
            
            # Nghỉ ngắn để né chặn IP (Quan trọng trên Streamlit Cloud)
            time.sleep(0.5)
            
        except Exception as e:
            # Nếu TCBS chặn, log sẽ hiện ở đây
            continue

    log_area.empty()
    if results:
        st.subheader(f"📊 Kết quả đồng thuận ({datetime.now().strftime('%H:%M:%S')})")
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Không tìm thấy tín hiệu hoặc bị server chặn IP. Hãy thử lại sau ít phút.")

st.divider()
st.caption("Lưu ý: Vnstock 4.0 yêu cầu kết nối ổn định. Nếu quét thất bại liên tục, có thể IP của Streamlit đã bị hạn chế.")
