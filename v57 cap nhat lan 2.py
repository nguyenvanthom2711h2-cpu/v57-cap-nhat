import pandas as pd
from tabulate import tabulate
from datetime import datetime, timedelta
import time
import warnings
import os, sys, contextlib

# Import vnstock
try:
    from vnstock.api.quote import Quote
except ImportError:
    try:
        from vnstock import Quote
    except ImportError:
        print("❌ Lỗi: Không tìm thấy vnstock. Hãy chạy: pip install vnstock -U")
        sys.exit()

warnings.filterwarnings("ignore")

# ==========================================
# 1. CẤU HÌNH
# ==========================================
WAIT_TIME = 900  # Nghỉ 15 phút giữa các lần quét
SYMBOLS_TO_SCAN = [
    'ACB','BCM','BID','BVH','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','PLX','POW','SAB',
    'SHB','SSB','SSI','STB','TCB','TPB','VCB','VHM','VIB','VIC','VJC','VNM','VPB','VRE','LPB','DGC',
    'DPM','DCM','VGC','PVD','PVS','NLG','KDH','KBC','IDC','SZC','GMD','HAH','OIL','FRT','PNJ','TLG',
    'BSI','HSG','NKG','DIG','DXG','PDR','NVL','VIX','VCK','TCX','DGW','VND','HCM','VCI','EIB','MSB',
    'OCB','REE','CTR','VGI','VTP'
]

SCAN_PAIRS = [
    ('1h', '4h'),
    ('4h', '1d'),
    ('1d', '3d'),
    ('3d', '1w')
]

@contextlib.contextmanager
def mute_stdout():
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try: yield
        finally: sys.stdout = old_stdout

# ==========================================
# 2. HÀM TÍNH TOÁN (Giữ nguyên bản gốc)
# ==========================================
def calculate_indicators(df):
    if df is None or len(df) < 50: return 0, 0
    try:
        df = df.copy()
        delta = df['c'].diff()
        gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
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

def resample_stock_data(df, rule):
    if df is None or len(df) < 2: return None
    df['ts'] = pd.to_datetime(df['ts'])
    df.set_index('ts', inplace=True)
    logic = {'o':'first', 'h':'max', 'l':'min', 'c':'last', 'v':'sum'}
    return df.resample(rule).apply(logic).dropna().reset_index()

# ==========================================
# 3. QUY TRÌNH QUÉT & TỔNG HỢP
# ==========================================
def run_automated_screener():
    now_str = datetime.now().strftime('%H:%M:%S')
    print(f"\n{'='*75}")
    print(f"🚀 CHU KỲ QUÉT MỚI [{now_str}]")
    print(f"{'='*75}")

    # Khởi tạo từ điển để gộp các khung thời gian theo mã
    summary_data = {}

    for tf1, tf2 in SCAN_PAIRS:
        tf_label = f"{tf1.upper()}-{tf2.upper()}"
        print(f"🔍 Đang lọc đồng thuận: {tf_label}...")
        total = len(SYMBOLS_TO_SCAN)

        for idx, symbol in enumerate(SYMBOLS_TO_SCAN):
            print(f" [{idx+1}/{total}] Đang quét: {symbol}...", end="\r")
            try:
                with mute_stdout():
                    q = Quote(symbol=symbol, source='VCI')
                    
                    def get_tf_data(tf):
                        if 'h' in tf.lower():
                            df = q.history(start=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'), interval='1H')
                            df = df.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})
                            if tf.lower() == '1h': return df
                            return resample_stock_data(df, '4H')
                        else:
                            df = q.history(start='2022-01-01', interval='1D')
                            df = df.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})
                            if tf.lower() == '1d': return df
                            rule_map = {'3d':'3D','1w':'W-MON'}
                            return resample_stock_data(df, rule_map.get(tf.lower(), '1D'))

                    df1 = get_tf_data(tf1)
                    df2 = get_tf_data(tf2)

                    stat1, p1 = calculate_indicators(df1)
                    stat2, p2 = calculate_indicators(df2)

                    if stat1 == stat2 and stat1 != 0:
                        side = "BUY" if stat1 == 1 else "SELL"
                        display_price = p1 if p1 > 1000 else p1 * 1000
                        
                        # Gộp dữ liệu vào summary_data
                        if symbol not in summary_data:
                            summary_data[symbol] = {'price': display_price, 'buy': [], 'sell': []}
                        
                        if side == "BUY":
                            summary_data[symbol]['buy'].append(tf_label)
                        else:
                            summary_data[symbol]['sell'].append(tf_label)
                time.sleep(0.01)
            except: continue
        print(f" ✅ Hoàn thành quét {tf_label}                  ")

    # ==========================================
    # 4. HIỂN THỊ BẢNG TỔNG HỢP CUỐI CÙNG
    # ==========================================
    if summary_data:
        print(f"\n📊 BẢNG TỔNG HỢP TÍN HIỆU ĐỒNG THUẬN [{now_str}]")
        final_rows = []
        for sym in sorted(summary_data.keys()):
            data = summary_data[sym]
            buy_tfs = ", ".join(data['buy']) if data['buy'] else "-"
            sell_tfs = ", ".join(data['sell']) if data['sell'] else "-"
            final_rows.append([sym, f"{data['price']:,.0f}", buy_tfs, sell_tfs])
        
        print(tabulate(final_rows, 
                       headers=["MÃ", "GIÁ", "ĐỒNG THUẬN MUA (🚀)", "ĐỒNG THUẬN BÁN (🔻)"], 
                       tablefmt='grid'))
    else:
        print("\n❌ Không tìm thấy tín hiệu đồng thuận nào trong chu kỳ này.")

# ==========================================
# 5. VÒNG LẶP CHÍNH
# ==========================================
if __name__ == "__main__":
    print("================================================================")
    print("    BỘ LỌC CỔ PHIẾU MULTI-TF - CHẾ ĐỘ HIỂN THỊ TỔNG HỢP")
    print("================================================================")

    while True:
        try:
            run_automated_screener()
        except Exception as e:
            print(f"Lỗi hệ thống: {e}")
        
        print(f"\n💤 Đang nghỉ {WAIT_TIME/60} phút cho đến lần quét kế tiếp...")
        time.sleep(WAIT_TIME)
