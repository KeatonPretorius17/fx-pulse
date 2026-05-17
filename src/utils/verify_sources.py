import requests, yfinance as yf, os, zipfile, io, csv
from fredapi import Fred
from dotenv import load_dotenv
import oandapyV20
import oandapyV20.endpoints.instruments as instruments

load_dotenv()

FRED_KEY    = os.getenv("FRED_API_KEY")
OANDA_TOKEN = os.getenv("OANDA_API_TOKEN")

def check_oanda():
    print("\n[1] Oanda — FOREX prices (GBP/USD, EUR/GBP)")
    client = oandapyV20.API(access_token=OANDA_TOKEN, environment="practice")
    params = {"count": 3, "granularity": "D"}
    for pair in ["GBP_USD", "EUR_GBP"]:
        r = instruments.InstrumentsCandles(instrument=pair, params=params)
        client.request(r)
        candles = r.response["candles"]
        for c in candles:
            print(f"  {pair} | {c['time'][:10]} | close: {c['mid']['c']}")
    print("✓ OK")

def check_yfinance_etf():
    print("\n[2] yfinance — ETF prices")
    for ticker in ["SPY", "GLD", "TLT"]:
        df = yf.Ticker(ticker).history(period="3d")
        print(f"  {ticker}: latest close = {df['Close'].iloc[-1]:.2f}")
    print("✓ OK")

def check_fred():
    print("\n[3] FRED — US and UK interest rates")
    fred = Fred(api_key=FRED_KEY)
    series = {
        "DFF":    "Fed Funds Rate",
        "T10Y2Y": "10Y-2Y Spread",
    }
    for code, label in series.items():
        val = fred.get_series(code).iloc[-1]
        print(f"  {label}: {val:.2f}")
    print("✓ OK")

def check_boe():
    print("\n[4] BoE — Bank Rate")
    url = (
        "https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp"
        "?csv.x=yes&Datefrom=01/Jan/2025&Dateto=now"
        "&SeriesCodes=IUMABEDR&CSVF=TN&UsingCodes=Y"
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=10)
    lines = [l for l in resp.text.strip().split("\n") if l.strip()]
    for line in lines[-3:]:
        print(" ", line[:80])
    print("✓ OK")

def check_cftc():
    print("\n[5] CFTC — COT positioning (GBP futures)")
    url = "https://www.cftc.gov/files/dea/history/fut_fin_txt_2025.zip"
    resp = requests.get(url, timeout=30)
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    content = z.read(z.namelist()[0]).decode("utf-8", errors="replace")
    reader = csv.reader(content.strip().split("\n"))
    rows = list(reader)
    header = rows[0]
    gbp_rows = [r for r in rows[1:] if r and r[0] == "BRITISH POUND - CHICAGO MERCANTILE EXCHANGE"]
    print(f"  GBP rows found: {len(gbp_rows)}")
    if gbp_rows:
        latest = gbp_rows[-1]
        print(f"  Latest date: {latest[2]}")
        print(f"  Contract: {latest[0]}")
    print("✓ OK")

check_oanda()
check_yfinance_etf()
check_fred()
check_boe()
check_cftc()
print("\n✓ All five sources verified. Step 1 complete.")