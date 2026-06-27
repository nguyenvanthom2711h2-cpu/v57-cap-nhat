import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time
import warnings

warnings.filterwarnings("ignore")

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="VN Stock Consensus Clone", layout="wide")
st.title("🚀 Bộ Lọc Đồng Thuận (Clone chính xác bản Python)")
st.caption("Dữ liệu Yahoo Finance | Công thức chuẩn RSI Wilder's (alpha=1/14)")

# DANH SÁCH MÃ CHỨNG KHOÁN
SYMBOLS_RAW = [
    # NGÂN HÀNG
    'ACB','BID','CTG','HDB','LPB','MBB','MSB','OCB','SHB','STB','TCB','TPB','VCB','VIB','VPB','EIB','SSB','ABB','BVB',
    # CHỨNG KHOÁN
    'SSI','VND','VCI','HCM','VIX','BSI','FTS','MBS','SHS','CTS','AGR','ORS','VDS','TVS',
    # BẤT ĐỘNG SẢN & ĐẦU TƯ CÔNG
    'VHM','VIC','VRE','DXG','DIG','PDR','NVL','NLG','KDH','CEO','L14','TCH','HQC','ITA','VCG','HHV','LCG','FCN','C4G','HBC','CTD',
    # THÉP
    'HPG','HSG','NKG','TVN','TLH','VGS',
    # DẦU KHÍ & NĂNG LƯỢNG
    'GAS','PVD','PVS','PVT','PVC','PLX','POW','PC1','TV2','GEG','REE','BCG','ASM','NT2',
    # KHU CÔNG NGHIỆP & CAO SU
    'IDC','SZC','KBC','VGC','PHR','GVR','BCM','TIP','DPR',
    # BÁN LẺ & CÔNG NGHỆ
    'MWG','MSN','FPT','PNJ','DGW','FRT','PET','VTP','CTR','VGI',
    # HÓA CHẤT - PHÂN BÓN
    'DGC','DPM','DCM','LAS','BFC','CSV',
    # THỦY SẢN - NÔNG NGHIỆP
    'VHC','ANV','IDI','PAN','DBC','BAF','HAG','HNG','LSS','SBT',
    # CẢNG BIỂN - LOGISTICS
    'GMD','HAH','VSC','VOS','SKG','PVT',
    # SẢN XUẤT - TIÊU DÙNG
    'VNM','SAB','BHN','TLG','KDC','GIL','MSH','TNG','VGT','RAL','DQC'
]
SYMBOLS = [s + ".VN" for s in SYMBOLS_RAW]

SCAN_PAIRS = [('1h', '4h'), ('4h', '1d'), ('1d', '3d'), ('3d', '1w')]

# ==========================================
# 1. HÀM TÍNH TOÁN (Giữ nguyên 100% bản gốc)
# ==========================================
def calculate_indicators(df):
    if df is None or len(df) < 50: return 0, 0
    try:
        df = df.copy()
        # Chuyển tên cột sang chữ thường để khớp logic cũ
        df.columns = [c.lower() for c in df.columns]
        
        delta = df['c'].diff()
        gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
        
        # Công thức alpha=1/14 chuẩn Wilder's trong bản gốc của bạn
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        
        df['rsi'] = 100 - (100 / (1 + avg_gain / avg_loss))
        df['rsi9'] = df['rsi'].rolling(9).mean()
        df['rsi45'] = df['rsi'].rolling(45).mean()
        
        last = df.iloc[-1]
        status = 0
        if last['rsi'] > last['rsi9'] and last['rsi'] > last['rsi45']: status = 1
        elif last['rsi'] < last['rsi9'] and last['rsi'] < last['rsi45']: status = -1
        return status, last['c']
    except: return 0, 0

# ==========================================
# 2. HÀM GỘP NẾN (Giữ nguyên 100% bản gốc)
# ==========================================
def resample_stock_data(df, rule):
    if df is None or len(df) < 2: return None
    try:
        df = df.copy()
        # Yahoo trả về index là Datetime, ta cần đưa về cột 'ts' để khớp logic cũ
        df['ts'] = df.index
        df['ts'] = pd.to_datetime(df['ts'])
        df.set_index('ts', inplace=True)
        
        # Mapping cột Yahoo sang tên viết tắt o, h, l, c, v
        logic = {'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}
        res = df.resample(rule).apply(logic).dropna().reset_index()
        # Đổi lại tên để hàm calculate_indicators đọc được
        res.columns = ['ts', 'o', 'h', 'l', 'c', 'v']
        return res
    except: return None

# ==========================================
# 3. QUY TRÌNH QUÉT
# ==========================================
if st.button("🔍 BẮT ĐẦU QUÉT THEO LOGIC GỐC"):
    summary_data = {}
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, sym in enumerate(SYMBOLS):
        short_name = sym.replace(".VN", "")
        status_text.write(f"🔄 Đang quét: **{short_name}**...")
        progress_bar.progress((i + 1) / len(SYMBOLS))
        
        try:
            # Tải dữ liệu
            d1h = yf.download(sym, period="60d", interval="1h", progress=False)
            d1d = yf.download(sym, period="2y", interval="1d", progress=False)

            if not d1h.empty and not d1d.empty:
                # Xử lý làm phẳng MultiIndex của yfinance (nếu có)
                if isinstance(d1h.columns, pd.MultiIndex):
                    d1h.columns = d1h.columns.get_level_values(0)
                    d1d.columns = d1d.columns.get_level_values(0)

                # Chuẩn bị DataFrames cho các khung
                # Đổi tên cột Yahoo sang o,h,l,c,v để đồng bộ
                df_h = d1h[['Open','High','Low','Close','Volume']].rename(columns={'Open':'o','High':'h','Low':'l','Close':'c','Volume':'v'})
                df_d = d1d[['Open','High','Low','Close','Volume']].rename(columns={'Open':'o','High':'h','Low':'l','Close':'c','Volume':'v'})

                tfs = {
                    '1h': df_h.reset_index().rename(columns={'Datetime':'ts','index':'ts'}),
                    '4h': resample_stock_data(d1h, '4H'),
                    '1d': df_d.reset_index().rename(columns={'Date':'ts','index':'ts'}),
                    '3d': resample_stock_data(d1d, '3D'),
                    '1w': resample_stock_data(d1d, 'W-MON')
                }
                
                # Tính tín hiệu
                sigs = {}
                prices = {}
                for name, df_tf in tfs.items():
                    stat, p = calculate_indicators(df_tf)
                    sigs[name] = stat
                    prices[name] = p
                
                # Kiểm tra đồng thuận
                for tf1, tf2 in SCAN_PAIRS:
                    if sigs.get(tf1) == sigs.get(tf2) and sigs.get(tf1) != 0:
                        side = "BUY" if sigs[tf1] == 1 else "SELL"
                        # Quy đổi giá sang VNĐ
                        p_val = prices['1h'] if prices['1h'] > 1000 else prices['1h'] * 1000
                        
                        if short_name not in summary_data:
                            summary_data[short_name] = {'p': p_val, 'buy': [], 'sell': []}
                        
                        label = f"{tf1.upper()}-{tf2.upper()}"
                        if side == "BUY": summary_data[short_name]['buy'].append(label)
                        else: summary_data[short_name]['sell'].append(label)
            
            time.sleep(0.02)
        except: continue

    status_text.empty()
    if summary_data:
        st.subheader("📊 Bảng Tổng Hợp Kết Quả")
        final_rows = []
        for s in sorted(summary_data.keys()):
            d = summary_data[s]
            final_rows.append({
                "MÃ": s,
                "GIÁ": f"{d['p']:,.0f}",
                "MUA (🚀)": ", ".join(d['buy']) if d['buy'] else "-",
                "BÁN (🔻)": ", ".join(d['sell']) if d['sell'] else "-"
            })
        st.dataframe(pd.DataFrame(final_rows), use_container_width=True, hide_index=True)
    else:
        st.warning("Không tìm thấy mã nào đồng thuận theo logic gốc.")
