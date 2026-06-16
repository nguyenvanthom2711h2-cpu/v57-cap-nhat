import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import warnings
import time

# Import vnstock
try:
    from vnstock import Quote
except ImportError:
    st.error("Cần cài đặt vnstock. Vui lòng kiểm tra file requirements.txt")

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

# Các cặp khung giờ để kiểm tra đồng thuận
SCAN_PAIRS = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]

# ==========================================
# HÀM XỬ LÝ DỮ LIỆU
# ==========================================
def calculate_indicators(df):
    """Tính toán RSI đồng thuận: RSI > RSI_MA9 và RSI > RSI_MA45"""
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
    """Gộp nến sang khung thời gian lớn hơn"""
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
    
    # Khu vực log và tiến độ
    log_expander = st.expander("Xem nhật ký quét chi tiết", expanded=True)
    progress_bar = st.progress(0)
    
    total_symbols = len(SYMBOLS)
    
    for idx, symbol in enumerate(SYMBOLS):
        # Cập nhật tiến độ
        progress = (idx + 1) / total_symbols
        progress_bar.progress(progress)
        
        with log_expander:
            st.write(f"🔄 Đang xử lý: **{symbol}**...")

        try:
            # 1. Lấy dữ liệu nguồn (Dùng DNSE cho ổn định)
            q = Quote(symbol=symbol, source='DNSE')
            
            # Khung giờ: Lấy 90 ngày gần nhất
            df_h_raw = q.history(start=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'), interval='1H')
            df_h_raw = df_h_raw.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})
            
            # Khung ngày: Lấy từ 2022 để đủ nến gộp khung Tuần
            df_d_raw = q.history(start='2022-01-01', interval='1D')
            df_d_raw = df_d_raw.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})

            if df_h_raw.empty or df_d_raw.empty:
                continue

            # 2. Tạo các khung thời gian
            tfs = {
                '1h': df_h_raw,
                '4h': resample_stock_data(df_h_raw, '4H'),
                '1d': df_d_raw,
                '3d': resample_stock_data(df_d_raw, '3D'),
                '1w': resample_stock_data(df_d_raw, 'W-MON')
            }

            # 3. Tính tín hiệu cho từng khung
            signals = {}
            last_price = 0
            for tf_name, df_tf in tfs.items():
                sig, price = calculate_indicators(df_tf)
                signals[tf_name] = sig
                if tf_name == '1h': last_price = price

            # 4. So sánh các cặp đồng thuận
            for tf1, tf2 in SCAN_PAIRS:
                s1 = signals.get(tf1, 0)
                s2 = signals.get(tf2, 0)

                if s1 == s2 and s1 != 0:
                    pair_label = f"{tf1.upper()}-{tf2.upper()}"
                    display_p = last_price if last_price > 1000 else last_price * 1000
                    
                    if symbol not in summary_data:
                        summary_data[symbol] = {'price': display_p, 'buy': [], 'sell': []}
                    
                    if s1 == 1:
                        summary_data[symbol]['buy'].append(pair_label)
                    else:
                        summary_data[symbol]['sell'].append(pair_label)
            
            # Nghỉ ngắn để tránh bị API chặn
            time.sleep(0.1)
            
        except Exception as e:
            with log_expander:
                st.error(f"❌ Lỗi tại mã {symbol}: {e}")
            continue

    # ==========================================
    # HIỂN THỊ KẾT QUẢ
    # ==========================================
    st.divider()
    if summary_data:
        st.subheader(f"📊 BẢNG TỔNG HỢP TÍN HIỆU [{datetime.now().strftime('%H:%M:%S')}]")
        
        final_rows = []
        for sym in sorted(summary_data.keys()):
            data = summary_data[sym]
            final_rows.append({
                "MÃ": sym,
                "GIÁ HIỆN TẠI": f"{data['price']:,.0f}",
                "ĐỒNG THUẬN MUA (🚀)": ", ".join(data['buy']) if data['buy'] else "-",
                "ĐỒNG THUẬN BÁN (🔻)": ", ".join(data['sell']) if data['sell'] else "-"
            })
        
        st.dataframe(pd.DataFrame(final_rows), use_container_width=True, hide_index=True)
    else:
        st.error("⚠️ Không tìm thấy tín hiệu đồng thuận nào. Vui lòng thử lại sau ít phút hoặc kiểm tra kết nối internet.")
