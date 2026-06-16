import pandas as pd
import telebot
from tabulate import tabulate
from datetime import datetime, timedelta
import time
import warnings
import os, sys, contextlib

# Import vnstock
try:
    from vnstock.api.quote import Quote
    from vnstock.api.market import Listing
except ImportError:
    try:
        from vnstock import Quote, Listing
    except ImportError:
        print("❌ Lỗi: Không tìm thấy vnstock. Hãy chạy: pip install vnstock -U")
        sys.exit()

warnings.filterwarnings("ignore")

# ==========================================
# 1. CẤU HÌNH (Giữ nguyên bản gốc)
# ==========================================
TOKEN = '8958414448:AAETDsuT0ut2gznqgvSzJbT62pgNKnlBxLE'
CHAT_ID = '6095817110'
bot = telebot.TeleBot(TOKEN)

WAIT_TIME = 900 
MIN_VOLUME = 50000 
last_alerts = {}

SYMBOLS_TO_SCAN = [
    'ACB','BCM','BID','BVH','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','PLX','POW','SAB',
    'SHB','SSB','SSI','STB','TCB','TPB','VCB','VHM','VIB','VIC','VJC','VNM','VPB','VRE','LPB','DGC',
    'DPM','DCM','VGC','PVD','PVS','NLG','KDH','KBC','IDC','SZC','GMD','HAH','OIL','FRT','PNJ','TLG',
    'BSI','HSG','NKG','DIG','DXG','PDR','NVL','VIX','VCK','TCX','DGW','VND','HCM','VCI','EIB','MSB',
    'OCB','REE','CTR','VGI','VTP','VNM','KDH','NLG'
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
# 3. QUY TRÌNH QUÉT
# ==========================================
def run_automated_screener():
    now_str = datetime.now().strftime('%H:%M:%S')
    print(f"\n{'='*60}")
    print(f"🚀 CHU KỲ QUÉT TỰ ĐỘNG MỚI [{now_str}]")
    print(f"{'='*60}")

    # dictionary để lưu trữ tổng hợp: { 'SSI': {'price': 35000, 'buy': ['1H-4H', '4H-1D'], 'sell': []} }
    summary_data = {}

    for tf1, tf2 in SCAN_PAIRS:
        tf_label = f"{tf1.upper()}-{tf2.upper()}"
        print(f"\n🔍 Đang lọc đồng thuận: {tf_label}...")
        dashboard_rows = []
        total = len(SYMBOLS_TO_SCAN)

        for idx, symbol in enumerate(SYMBOLS_TO_SCAN):
            print(f" [{idx+1}/{total}] Quét: {symbol}...", end="\r")
            try:
                with mute_stdout():
                    q = Quote(symbol=symbol, source='VCI')
                    
                    def get_tf_data(tf):
                        if 'h' in tf.lower():
                            df = q.history(start=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'), interval='1H')
                            df = df.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})
                            if tf.lower() == '1h': return df
                            return resample_stock_data(df, '4H') if tf.lower() == '4h' else df
                        else:
                            df = q.history(start='2022-01-01', interval='1D')
                            df = df.rename(columns={'time':'ts','open':'o','high':'h','low':'l','close':'c','volume':'v'})
                            if tf.lower() == '1d': return df
                            rule_map = {'3d':'3D','1w':'W-MON','1m':'ME'}
                            return resample_stock_data(df, rule_map.get(tf.lower(), '1D'))

                    df1 = get_tf_data(tf1)
                    df2 = get_tf_data(tf2)

                    stat1, p1 = calculate_indicators(df1)
                    stat2, p2 = calculate_indicators(df2)

                    if stat1 == stat2 and stat1 != 0:
                        side = "BUY" if stat1 == 1 else "SELL"
                        label = "MUA 🚀" if side == "BUY" else "BÁN 🔻"
                        display_price = p1 if p1 > 1000 else p1 * 1000
                        dashboard_rows.append([symbol, f"{display_price:,.0f}", label])

                        # --- PHẦN MỚI: CẬP NHẬT DỮ LIỆU TỔNG HỢP ---
                        if symbol not in summary_data:
                            summary_data[symbol] = {'price': display_price, 'buy': [], 'sell': []}
                        
                        if side == "BUY":
                            summary_data[symbol]['buy'].append(tf_label)
                        else:
                            summary_data[symbol]['sell'].append(tf_label)
                        # ------------------------------------------

                        alert_key = f"{symbol}_{side}_{tf1}_{tf2}_{datetime.now().strftime('%H')}"
                        if alert_key not in last_alerts:
                            msg = (f"{'🚀 **MUA' if side=='BUY' else '🔻 **BÁN'} ĐỒNG THUẬN**\n\n"
                                   f"💎 Mã: **{symbol}**\n"
                                   f"⏱ Khung: `{tf_label}`\n"
                                   f"💵 Giá: `{display_price:,.0f}`")
                            bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
                            last_alerts[alert_key] = True
                time.sleep(0.01)
            except: continue

        if dashboard_rows:
            print(f"\n✅ Kết quả {tf_label}:")
            print(tabulate(dashboard_rows, headers=["MÃ", "GIÁ", "LỆNH"], tablefmt='grid'))
        else:
            print(f"\n❌ Không tìm thấy mã đồng thuận {tf_label}.")

    # ==========================================
    # 4. IN BẢNG TỔNG HỢP CUỐI CÙNG (PHẦN THÊM)
    # ==========================================
    if summary_data:
        print(f"\n{'='*60}")
        print(f"📊 BẢNG TỔNG HỢP TÍN HIỆU ĐỒNG THUẬN TOÀN BỘ CÁC KHUNG")
        print(f"{'='*60}")
        
        final_rows = []
        for sym in sorted(summary_data.keys()):
            data = summary_data[sym]
            # Gộp danh sách khung giờ thành chuỗi, nếu không có thì để "-"
            buy_tfs = ", ".join(data['buy']) if data['buy'] else "-"
            sell_tfs = ", ".join(data['sell']) if data['sell'] else "-"
            
            final_rows.append([sym, f"{data['price']:,.0f}", buy_tfs, sell_tfs])
        
        print(tabulate(final_rows, 
                       headers=["MÃ", "GIÁ", "ĐỒNG THUẬN MUA (🚀)", "ĐỒNG THUẬN BÁN (🔻)"], 
                       tablefmt='grid'))
        print(f"{'='*60}\n")

# ==========================================
# 5. VÒNG LẶP CHÍNH
# ==========================================
if __name__ == "__main__":
    print("==============================================")
    print("    BỘ LỌC TỰ ĐỘNG MULTI-TF (BẢN TỔNG HỢP)")
    print("    CHẾ ĐỘ: TỰ ĐỘNG QUÉT & GỘP KẾT QUẢ")
    print("==============================================")

    while True:
        try:
            run_automated_screener()
        except Exception as e:
            print(f"Lỗi hệ thống: {e}")
        
        print(f"\n💤 Đang nghỉ {WAIT_TIME/60} phút...")
        time.sleep(WAIT_TIME)
