#!/usr/bin/env python3
"""
Dashboard de cartera DEGIRO - Saúl Trujillo
Uso: pip install yfinance pandas && python portfolio_update.py
"""

import yfinance as yf
import pandas as pd
import json, os, warnings
from datetime import datetime, date

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────
#  ⚠️  ACTUALIZA ESTOS 2 VALORES CADA VEZ QUE CORRAS EL SCRIPT
#  Los encuentras en DEGIRO → pantalla principal
# ─────────────────────────────────────────────────────────
CASH_IN_ACCOUNT   = 1992.78   # "EUR" en DEGIRO
TOTAL_ACCOUNT_VAL = 8460.55   # "Cuenta Completa" en DEGIRO
# ─────────────────────────────────────────────────────────

TOTAL_DEPOSITED = 8099.00
START_DATE      = date(2022, 7, 25)

# ─────────────────────────────────────────────────────────
#  POSICIONES ABIERTAS
# ─────────────────────────────────────────────────────────
POSITIONS = [
    # (nombre, ticker, qty, coste_eur, divisa_nativa, fecha_primera_compra)
    ("Adobe Inc",                "ADBE",      7,   1478.47, "USD", "2025-11-19"),
    ("QinetiQ Group PLC",        "QQ.L",      150,  711.27, "GBX", "2026-05-12"),
    ("Microsoft Corp",           "MSFT",      2,    638.99, "USD", "2026-03-26"),
    ("Greggs PLC",               "GRG.L",     22,   445.90, "GBX", "2025-03-04"),
    ("Wendy's Co",               "WEN",       37,   444.68, "USD", "2025-01-16"),
    ("Italian Sea Group SpA",    "TISG.MI",   47,   418.41, "EUR", "2024-06-18"),
    ("PayPal Holdings Inc",      "PYPL",      7,    351.94, "USD", "2025-12-31"),
    ("FactSet Research Systems", "FDS",       2,    349.79, "USD", "2026-02-05"),
    ("Novo Nordisk A/S Class B", "NOVO-B.CO", 5,    245.83, "DKK", "2025-07-29"),
    ("ADR on Nice Ltd",          "NICE",      2,    235.02, "USD", "2025-09-02"),
    ("FRP Advisory Group PLC",   "FRP.L",     150,  221.76, "GBX", "2025-06-17"),
    ("Nomad Foods Ltd",          "NOMD",      18,   218.49, "USD", "2025-09-10"),
    ("Evolution AB",             "E3G1.MU",   3,    218.04, "EUR", "2024-12-23"),
    ("Euronet Worldwide Inc",    "EEFT",      3,    205.82, "USD", "2025-10-28"),
    ("Alphabet Inc Class A",     "GOOGL",     2,    205.23, "USD", "2022-09-23"),
    ("ADR on Novo Nordisk A/S",  "NVO",       6,    202.90, "USD", "2026-03-16"),
    ("Brown-Forman Corp Class B","BF-B",      3,     91.59, "USD", "2025-02-07"),
]

BENCHMARKS = [("S&P 500", "SPY"), ("MSCI World", "URTH")]

FX_PAIRS = {"USD": "EURUSD=X", "GBP": "EURGBP=X", "DKK": "EURDKK=X"}

COLORS = ["#4f8ef7","#34d399","#a78bfa","#fbbf24","#f87171","#2dd4bf","#fb923c",
          "#c084fc","#86efac","#67e8f9","#fda4af","#a3e635","#fdba74","#7dd3fc",
          "#d8b4fe","#6ee7b7","#fcd34d"]


# ─────────────────────────────────────────────────────────
#  FX
# ─────────────────────────────────────────────────────────
def fetch_fx():
    fx = {"EUR": 1.0}
    print("  FX rates...", end=" ", flush=True)
    for cur, pair in FX_PAIRS.items():
        try:
            h = yf.Ticker(pair).history(period="5d")
            if not h.empty:
                fx[cur] = 1.0 / float(h["Close"].iloc[-1])
        except:
            pass
    fx["GBX"] = fx.get("GBP", 0.01175) / 100
    print(f"USD:{fx.get('USD',0.92):.4f} GBP:{fx.get('GBP',1.175):.4f} DKK:{fx.get('DKK',0.134):.4f}")
    return fx


# ─────────────────────────────────────────────────────────
#  HISTÓRICO DIARIO
# ─────────────────────────────────────────────────────────
def fetch_hist(ticker, period="5y"):
    try:
        h = yf.Ticker(ticker).history(period=period)
        if h.empty:
            return None
        h = h[["Close"]].copy()
        h.index = h.index.tz_localize(None)
        return h
    except:
        return None


def first_price_on_or_after(h, target_date):
    if h is None:
        return None
    mask = h.index.date >= target_date
    sub  = h[mask]
    return float(sub["Close"].iloc[0]) if not sub.empty else None


def last_price(h):
    if h is None or h.empty:
        return None
    return float(h["Close"].iloc[-1])


# ─────────────────────────────────────────────────────────
#  GRÁFICO HISTÓRICO DIARIO CORRECTO
#
#  Metodología:
#  - Cada día calculamos la rentabilidad de cada posición desde
#    su fecha de compra: ret_i(t) = price(t)/price(buy_date) - 1
#  - La rentabilidad de la cartera ese día es la media ponderada
#    de las rentabilidades de las posiciones activas, ponderadas
#    por su coste de adquisición
#  - Los benchmarks se normalizan a 100 en el mismo primer día
#    que la primera posición de la cartera (julio 2022)
# ─────────────────────────────────────────────────────────
def build_chart(pos_hist_map, bench_hists, fx):
    print("\n  Construyendo gráfico histórico...", end=" ", flush=True)

    # Calendario de referencia: días hábiles desde START_DATE
    ref = bench_hists.get("SPY")
    if ref is None:
        print("sin datos")
        return {}

    mask = ref.index.date >= START_DATE
    cal  = ref[mask].index
    if cal.empty:
        print("sin datos")
        return {}

    total_cost = sum(p[3] for p in POSITIONS)

    # Para cada ticker, construir serie de retorno diario desde buy_date
    # ret_series[ticker] = Serie con índice = fechas, valores = % retorno desde compra
    ret_series = {}
    weights    = {}

    for p in POSITIONS:
        name, tkr, qty, cost_eur, cur, buy_date_str = p
        buy_date = date.fromisoformat(buy_date_str)
        h = pos_hist_map.get(tkr)
        if h is None:
            continue

        fxr = fx.get(cur, 1.0)

        # Precio de compra = primer precio disponible en o después de buy_date
        buy_mask  = h.index.date >= buy_date
        buy_sub   = h[buy_mask]
        if buy_sub.empty:
            continue
        price_buy = float(buy_sub["Close"].iloc[0]) * fxr  # en EUR

        # Serie de precios en EUR desde buy_date
        prices_eur = h[buy_mask]["Close"] * fxr

        # Retorno acumulado desde compra: (price_t / price_buy) - 1
        ret = (prices_eur / price_buy) - 1.0
        ret.name = tkr
        ret_series[tkr] = ret
        weights[tkr]    = cost_eur / total_cost

    if not ret_series:
        print("sin datos posiciones")
        return {}

    # DataFrame con todas las series, reindexado al calendario
    df = pd.DataFrame(ret_series)
    df = df.reindex(cal, method="ffill")

    # Para cada día, solo contribuyen las posiciones ya compradas
    portfolio_ret = pd.Series(index=cal, dtype=float)
    for dt in cal:
        dt_date = dt.date()
        total_w = 0.0
        val     = 0.0
        for p in POSITIONS:
            _, tkr, _, cost_eur, _, buy_date_str = p
            if date.fromisoformat(buy_date_str) > dt_date:
                continue
            if tkr not in df.columns:
                continue
            r = df.loc[dt, tkr]
            if pd.isna(r):
                continue
            w = weights.get(tkr, 0)
            val     += r * w
            total_w += w
        portfolio_ret[dt] = (val / total_w) if total_w > 0 else 0.0

    # Convertir a base 100
    portfolio_b100 = (1 + portfolio_ret) * 100

    # Benchmarks: base 100 desde el primer día del calendario
    bench_out = {}
    first_dt  = cal[0]
    BENCH_COLORS = {"S&P 500": "#fbbf24", "MSCI World": "#34d399"}

    for bname, btkr in BENCHMARKS:
        h = bench_hists.get(btkr)
        if h is None:
            continue
        # Precio base en el primer día del calendario
        base_mask = h.index <= first_dt
        if base_mask.sum() == 0:
            continue
        base_price = float(h[base_mask]["Close"].iloc[-1])

        # Serie reindexada y normalizada
        s = h.reindex(cal, method="ffill")["Close"]
        s_b100 = (s / base_price * 100).round(2)
        bench_out[bname] = {
            "values": s_b100.fillna(method="ffill").tolist(),
            "color":  BENCH_COLORS.get(bname, "#a78bfa")
        }

    dates  = [d.strftime("%Y-%m-%d") for d in cal]
    values = portfolio_b100.round(2).tolist()

    print(f"OK ({len(dates)} días · cartera: {values[0]:.1f}→{values[-1]:.1f})")
    return {"dates": dates, "portfolio": values, "benchmarks": bench_out}


# ─────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────
def main():
    print("\n🔄 Yahoo Finance → portfolio_dashboard.html\n")

    fx  = fetch_fx()
    now = datetime.now()
    ytd_start = date(now.year, 1, 1)
    mtd_start = date(now.year, now.month, 1)

    # ── Descargar históricos de posiciones ──
    pos_hist_map = {}
    pos_data     = []
    total_cost   = sum(p[3] for p in POSITIONS)

    for i, (name, tkr, qty, cost_eur, cur, buy_date) in enumerate(POSITIONS):
        print(f"  [{i+1:02d}/{len(POSITIONS)}] {name[:32]}...", end=" ", flush=True)
        try:
            h = fetch_hist(tkr, period="5y")
            if h is None:
                raise ValueError("sin datos")
            pos_hist_map[tkr] = h

            fxr       = fx.get(cur, 1.0)
            price     = last_price(h)
            price_eur = price * fxr
            val_eur   = price_eur * qty
            pnl_eur   = val_eur - cost_eur
            pnl_pct   = pnl_eur / cost_eur * 100

            ytd_p = first_price_on_or_after(h, ytd_start)
            mtd_p = first_price_on_or_after(h, mtd_start)
            ytd_r = (price - ytd_p) / ytd_p * 100 if ytd_p else None
            mtd_r = (price - mtd_p) / mtd_p * 100 if mtd_p else None

            pos_data.append({
                "name": name, "ticker": tkr, "qty": qty,
                "cost_eur": cost_eur, "cur": cur, "buy_date": buy_date,
                "price": price, "price_eur": price_eur,
                "val_eur": val_eur, "pnl_eur": pnl_eur, "pnl_pct": pnl_pct,
                "ytd_ret": ytd_r, "mtd_ret": mtd_r,
                "ok": True, "color": COLORS[i % len(COLORS)],
            })
            print(f"€{price_eur:.3f}  P&L posición:{pnl_pct:+.1f}%")
        except Exception as e:
            print(f"ERROR: {e}")
            pos_data.append({
                "name": name, "ticker": tkr, "qty": qty,
                "cost_eur": cost_eur, "cur": cur, "buy_date": buy_date,
                "ok": False, "color": COLORS[i % len(COLORS)],
            })

    # ── Benchmarks ──
    print("\n  Benchmarks...")
    bench_data = []
    bench_hists = {}
    for bname, btkr in BENCHMARKS:
        try:
            h = fetch_hist(btkr, period="5y")
            if h is None:
                raise ValueError("sin datos")
            bench_hists[btkr] = h
            price = last_price(h)
            ytd_p = first_price_on_or_after(h, ytd_start)
            mtd_p = first_price_on_or_after(h, mtd_start)
            ytd_r = (price - ytd_p) / ytd_p * 100 if ytd_p else None
            mtd_r = (price - mtd_p) / mtd_p * 100 if mtd_p else None
            bench_data.append({"name": bname, "ticker": btkr,
                                "price": price, "ytd": ytd_r, "mtd": mtd_r})
            print(f"    {bname}: ${price:.2f}  YTD:{ytd_r:+.1f}%" if ytd_r else f"    {bname}: ${price:.2f}")
        except Exception as e:
            print(f"    {bname}: ERROR {e}")
            bench_data.append({"name": bname, "ticker": btkr,
                                "price": None, "ytd": None, "mtd": None})

    # ── Rentabilidades REALES (cuenta completa) ──
    real_pnl     = TOTAL_ACCOUNT_VAL - TOTAL_DEPOSITED   # +361.55
    real_pnl_pct = real_pnl / TOTAL_DEPOSITED * 100      # +4.46%
    years        = (date.today() - START_DATE).days / 365.25
    cagr         = ((1 + real_pnl_pct/100)**(1/years) - 1)*100 if years > 0 else 0

    # YTD y MTD: media ponderada de posiciones abiertas (mejor proxy disponible)
    valid = [p for p in pos_data if p.get("ok")]
    yn = yd = mn = md = 0.0
    for p in valid:
        bd = date.fromisoformat(p["buy_date"])
        if p.get("ytd_ret") is not None and bd < ytd_start:
            yn += p["ytd_ret"] * p["cost_eur"]; yd += p["cost_eur"]
        if p.get("mtd_ret") is not None and bd < mtd_start:
            mn += p["mtd_ret"] * p["cost_eur"]; md += p["cost_eur"]

    total_val_open = sum(p["val_eur"] for p in valid)

    portfolio = {
        "account_val":  TOTAL_ACCOUNT_VAL,
        "open_val":     total_val_open,
        "cash":         CASH_IN_ACCOUNT,
        "total_cost":   total_cost,
        "total_pnl":    real_pnl,
        "pnl_pct":      real_pnl_pct,
        "cagr":         cagr,
        "ytd":          yn/yd if yd > 0 else None,
        "mtd":          mn/md if md > 0 else None,
        "updated":      now.strftime("%d/%m/%Y %H:%M"),
        "deposited":    TOTAL_DEPOSITED,
        "start_date":   START_DATE.isoformat(),
    }

    # ── Gráfico histórico ──
    chart_data = build_chart(pos_hist_map, bench_hists, fx)

    generate_html(pos_data, bench_data, portfolio, chart_data)

    print(f"\n✅  portfolio_dashboard.html generado")
    print(f"    Valor posiciones abiertas: €{total_val_open:,.0f}")
    print(f"    Cash en cuenta:            €{CASH_IN_ACCOUNT:,.2f}")
    print(f"    Cuenta completa DEGIRO:    €{TOTAL_ACCOUNT_VAL:,.2f}")
    print(f"    Total depositado:          €{TOTAL_DEPOSITED:,.2f}")
    print(f"    P&L REAL:                  €{real_pnl:+,.2f} ({real_pnl_pct:+.2f}%)")
    print(f"    CAGR:                      {cagr:+.2f}%")
    if portfolio["ytd"]: print(f"    YTD posiciones abiertas:   {portfolio['ytd']:+.1f}%")
    if portfolio["mtd"]: print(f"    MTD posiciones abiertas:   {portfolio['mtd']:+.1f}%")


# ─────────────────────────────────────────────────────────
#  HTML
# ─────────────────────────────────────────────────────────
def generate_html(pos_data, bench_data, portfolio, chart_data):
    pj  = json.dumps(pos_data,   ensure_ascii=False)
    bj  = json.dumps(bench_data, ensure_ascii=False)
    oj  = json.dumps(portfolio,  ensure_ascii=False)
    cj  = json.dumps(chart_data, ensure_ascii=False)
    n   = len(pos_data)
    upd = portfolio["updated"]
    years_str = f"{(date.today()-START_DATE).days/365.25:.1f} años"

    html = f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Mi Cartera · {upd}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
:root{{--bg:#0e1117;--bg2:#161b27;--bg3:#1e2535;--bg4:#252d40;
  --bd:rgba(255,255,255,.07);--tx:#dde1ea;--mu:#6b7585;
  --bl:#4f8ef7;--gr:#34d399;--rd:#f87171;--am:#fbbf24;--pu:#a78bfa;
  --fn:'Inter',system-ui,sans-serif;--mo:'JetBrains Mono','Fira Mono',monospace;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
html{{background:var(--bg);color:var(--tx);font-family:var(--fn);font-size:14px;}}
body{{min-height:100vh;padding:28px 32px;max-width:1400px;margin:0 auto;}}
.hdr{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px;flex-wrap:wrap;gap:12px;}}
.hdr h1{{font-size:20px;font-weight:600;letter-spacing:-.5px;color:#fff;}}
.hdr p{{color:var(--mu);font-size:12px;margin-top:4px;}}
.ts{{font-size:11px;color:var(--mu);text-align:right;line-height:1.8;}}
.ok{{display:inline-block;background:rgba(52,211,153,.15);color:var(--gr);border-radius:4px;padding:2px 8px;font-size:11px;font-weight:500;}}
.krow{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:16px;}}
.kpi{{background:var(--bg2);border:1px solid var(--bd);border-radius:10px;padding:14px 16px;}}
.kpi .lb{{font-size:10px;color:var(--mu);text-transform:uppercase;letter-spacing:.6px;margin-bottom:8px;}}
.kpi .vl{{font-size:22px;font-weight:700;font-family:var(--mo);letter-spacing:-1px;line-height:1;}}
.kpi .sb{{font-size:11px;color:var(--mu);margin-top:6px;}}
.pos{{color:var(--gr);}}.neg{{color:var(--rd);}}.neu{{color:var(--tx);}}
.card{{background:var(--bg2);border:1px solid var(--bd);border-radius:12px;padding:20px;margin-bottom:14px;}}
.ct{{font-size:13px;font-weight:600;color:var(--tx);margin-bottom:14px;}}
.cs{{font-size:11px;color:var(--mu);font-weight:400;margin-left:6px;}}
.cleg{{display:flex;gap:20px;margin-bottom:12px;font-size:12px;color:var(--mu);}}
.cleg span{{display:flex;align-items:center;gap:6px;}}
.cleg-line{{height:3px;width:16px;border-radius:2px;}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;}}
.g32{{display:grid;grid-template-columns:3fr 2fr;gap:14px;margin-bottom:14px;}}
.cb{{display:flex;flex-direction:column;gap:12px;}}
.bh{{display:flex;justify-content:space-between;font-size:12px;margin-bottom:5px;}}
.bn2{{color:var(--mu);}}.bvl{{font-weight:600;font-family:var(--mo);}}
.btrack{{height:7px;background:var(--bg4);border-radius:4px;overflow:hidden;}}
.bfill{{height:100%;border-radius:4px;}}
.bg{{display:grid;grid-template-columns:1fr 1fr;gap:8px;}}
.bi{{background:var(--bg3);border-radius:8px;padding:12px 14px;}}
.bi .bn{{font-size:11px;color:var(--mu);margin-bottom:5px;font-weight:500;}}
.bi .bv{{font-size:17px;font-weight:700;font-family:var(--mo);}}
.bi .bs{{font-size:11px;color:var(--mu);margin-top:4px;display:flex;gap:10px;flex-wrap:wrap;}}
.pie-leg{{display:flex;flex-wrap:wrap;gap:8px 14px;margin-top:12px;font-size:11px;color:var(--mu);}}
.pie-leg span{{display:flex;align-items:center;gap:5px;}}
.ld{{width:8px;height:8px;border-radius:2px;flex-shrink:0;}}
.pc{{background:var(--bg2);border:1px solid var(--bd);border-radius:12px;padding:20px;margin-bottom:16px;}}
.pt{{font-size:13px;font-weight:600;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;}}
.ph{{font-size:11px;color:var(--mu);font-weight:400;}}
table{{width:100%;border-collapse:collapse;}}
th{{font-size:10px;color:var(--mu);text-align:right;padding:6px 10px;font-weight:500;text-transform:uppercase;letter-spacing:.4px;border-bottom:1px solid var(--bd);white-space:nowrap;}}
th:first-child{{text-align:left;}}
td{{font-size:12px;padding:10px 10px;border-bottom:1px solid rgba(255,255,255,.03);text-align:right;}}
td:first-child{{text-align:left;}}
tr:last-child td{{border-bottom:none;}}
tr:hover td{{background:rgba(255,255,255,.02);}}
.pn{{font-weight:500;font-size:13px;color:var(--tx);}}
.pk{{font-family:var(--mo);font-size:10px;color:var(--mu);margin-top:2px;}}
.badge{{display:inline-block;background:var(--bg4);border-radius:3px;padding:2px 6px;font-size:10px;font-family:var(--mo);color:var(--mu);}}
.wb{{display:flex;align-items:center;gap:7px;justify-content:flex-end;}}
.wbar{{height:4px;border-radius:2px;opacity:.65;}}
.mo{{font-family:var(--mo);}}
.note{{font-size:11px;color:var(--am);background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.2);border-radius:6px;padding:8px 12px;margin-bottom:14px;}}
.ft{{text-align:center;color:var(--mu);font-size:11px;padding:20px 0;border-top:1px solid var(--bd);margin-top:4px;}}
</style></head><body>

<div class="hdr">
  <div><h1>📊 Mi Cartera · DEGIRO</h1><p>Yahoo Finance · <span class="ok">✓ {upd}</span></p></div>
  <div class="ts">Última actualización<br><strong style="color:var(--tx)">{upd}</strong><br><small>python portfolio_update.py</small></div>
</div>

<p class="note">⚠️ P&L y CAGR calculados sobre el valor total de la cuenta DEGIRO (cartera + cash) vs total depositado. Actualiza <code>TOTAL_ACCOUNT_VAL</code> y <code>CASH_IN_ACCOUNT</code> en el script antes de ejecutar.</p>

<div class="krow">
  <div class="kpi"><div class="lb">Cuenta completa</div><div class="vl neu" id="kv">—</div><div class="sb" id="kv-sub">cartera + cash</div></div>
  <div class="kpi"><div class="lb">P&L Real</div><div class="vl" id="kp">—</div><div class="sb" id="ks">vs total depositado</div></div>
  <div class="kpi"><div class="lb">YTD posiciones</div><div class="vl" id="ky">—</div><div class="sb">pond. por coste</div></div>
  <div class="kpi"><div class="lb">MTD posiciones</div><div class="vl" id="km">—</div><div class="sb" id="kms">mes en curso</div></div>
  <div class="kpi"><div class="lb">CAGR real</div><div class="vl" id="ka">—</div><div class="sb">desde jul 2022 · {years_str}</div></div>
</div>

<!-- GRÁFICO HISTÓRICO -->
<div class="card">
  <div class="ct">Evolución vs benchmarks <span class="cs">retorno acumulado ponderado · base 100 desde jul 2022</span></div>
  <div class="cleg" id="chartLeg"></div>
  <div style="position:relative;height:320px;">
    <canvas id="histC" role="img" aria-label="Evolución histórica de la cartera frente al SP500 y MSCI World"></canvas>
  </div>
</div>

<!-- PIE + PNL -->
<div class="g2">
  <div class="card" style="margin-bottom:0">
    <div class="ct">Peso por posición <span class="cs">% sobre coste adquisición</span></div>
    <div style="position:relative;height:260px;"><canvas id="pieC"></canvas></div>
    <div class="pie-leg" id="pieLeg"></div>
  </div>
  <div class="card" style="margin-bottom:0">
    <div class="ct">P&L por posición <span class="cs">€ sobre coste</span></div>
    <div id="pnlW" style="position:relative;height:260px;"><canvas id="pnlC"></canvas></div>
  </div>
</div>
<div style="margin-bottom:14px"></div>

<!-- COMPARATIVA + BENCHMARKS -->
<div class="g32">
  <div class="card" style="margin-bottom:0">
    <div class="ct">Comparativa de rentabilidades</div>
    <div class="cb" id="compB"></div>
  </div>
  <div class="card" style="margin-bottom:0">
    <div class="ct">Benchmarks</div>
    <div class="bg">
      <div class="bi"><div class="bn">S&P 500 (SPY)</div><div class="bv neu" id="bsp">—</div><div class="bs"><span id="bspy">YTD: —</span><span id="bspm">MTD: —</span></div></div>
      <div class="bi"><div class="bn">MSCI World (URTH)</div><div class="bv neu" id="bms">—</div><div class="bs"><span id="bmsy">YTD: —</span><span id="bmsm">MTD: —</span></div></div>
      <div class="bi"><div class="bn">Depositado</div><div class="bv neu">€8.099</div><div class="bs"><span>desde jul 2022</span></div></div>
      <div class="bi"><div class="bn">Cash en cuenta</div><div class="bv neu" id="kCash">—</div><div class="bs"><span>actualizar en script</span></div></div>
    </div>
  </div>
</div>
<div style="margin-bottom:14px"></div>

<!-- TABLA -->
<div class="pc">
  <div class="pt">Posiciones abiertas · {n} valores <span class="ph">precios Yahoo Finance</span></div>
  <table>
    <thead><tr>
      <th>Compañía</th><th>Div.</th><th>Acc.</th>
      <th>Coste medio (€)</th><th>Precio nativo</th><th>Precio (€)</th>
      <th>Valor (€)</th><th>P&amp;L posición (€)</th><th>P&amp;L %</th><th>Peso</th>
    </tr></thead>
    <tbody id="posB"></tbody>
  </table>
</div>

<div class="ft">Yahoo Finance (yfinance) · Divisas: EURUSD=X EURGBP=X EURDKK=X · {upd}</div>

<script>
const POS  = {pj};
const BENCH= {bj};
const PORT = {oj};
const CHRT = {cj};

const fmt  = (n,d=0) => (+n).toLocaleString('es-ES',{{minimumFractionDigits:d,maximumFractionDigits:d}});
const fp   = v => (v>=0?'+':'')+v.toFixed(2)+'%';
const fp1  = v => (v>=0?'+':'')+v.toFixed(1)+'%';
const fE   = v => (v>=0?'':'−')+'€'+fmt(Math.abs(v));
const g    = id => document.getElementById(id);
const sv   = (id,v) => {{ const e=g(id); if(e) e.textContent=v; }};
const cl   = v => v==null?'neu':v>=0?'pos':'neg';

// KPIs
sv('kv', '€'+fmt(PORT.account_val));
sv('kv-sub', 'cartera €'+fmt(PORT.open_val)+' + cash €'+fmt(PORT.cash));
sv('kp', fE(PORT.total_pnl)); g('kp').className='vl '+cl(PORT.total_pnl);
sv('ks', fp(PORT.pnl_pct)+' vs depositado');
sv('kCash', '€'+fmt(PORT.cash,2));
if(PORT.ytd!=null){{sv('ky',fp1(PORT.ytd));g('ky').className='vl '+cl(PORT.ytd);}}
if(PORT.mtd!=null){{sv('km',fp1(PORT.mtd));g('km').className='vl '+cl(PORT.mtd);}}
sv('ka', fp(PORT.cagr)); g('ka').className='vl '+cl(PORT.cagr);

const TC = POS.reduce((s,p)=>s+p.cost_eur,0);
const TV = POS.filter(p=>p.ok).reduce((s,p)=>s+(p.val_eur||0),0);

// ── GRÁFICO HISTÓRICO ──
if(CHRT.dates && CHRT.dates.length){{
  const datasets = [{{
    label:'Mi cartera',
    data: CHRT.portfolio,
    borderColor:'#4f8ef7',
    backgroundColor:'rgba(79,142,247,0.07)',
    borderWidth:2, pointRadius:0, fill:true, tension:0.1,
  }}];

  const benchEntries = Object.entries(CHRT.benchmarks||{{}});
  benchEntries.forEach(([name,b])=>{{
    datasets.push({{
      label:name,
      data:b.values,
      borderColor:b.color,
      backgroundColor:'transparent',
      borderWidth:1.5,
      borderDash:[5,3],
      pointRadius:0, fill:false, tension:0.1,
    }});
  }});

  // Leyenda
  g('chartLeg').innerHTML = datasets.map(d=>
    `<span><span class="cleg-line" style="background:${{d.borderColor}};height:${{d.borderDash?'2':'3'}}px"></span>${{d.label}}</span>`
  ).join('');

  const n = CHRT.dates.length;
  const step = Math.max(1, Math.floor(n/14));

  new Chart(g('histC'),{{
    type:'line',
    data:{{ labels:CHRT.dates, datasets }},
    options:{{
      responsive:true, maintainAspectRatio:false,
      interaction:{{mode:'index',intersect:false}},
      plugins:{{
        legend:{{display:false}},
        tooltip:{{
          callbacks:{{
            label: ctx => {{
              const v = ctx.parsed.y;
              const ret = (v - 100).toFixed(1);
              const sign = ret >= 0 ? '+' : '';
              return ` ${{ctx.dataset.label}}: ${{v.toFixed(1)}} (${{sign}}${{ret}}%)`;
            }}
          }}
        }}
      }},
      scales:{{
        x:{{
          grid:{{color:'rgba(255,255,255,.04)'}},
          ticks:{{
            color:'#6b7585', font:{{size:10}}, maxRotation:0,
            callback:(v,i) => i%step===0 ? CHRT.dates[i].slice(0,7) : null
          }}
        }},
        y:{{
          grid:{{color:'rgba(255,255,255,.05)'}},
          ticks:{{color:'#6b7585',font:{{size:10}},callback:v=>v.toFixed(0)}},
          title:{{display:true,text:'Base 100',color:'#6b7585',font:{{size:10}}}}
        }}
      }}
    }}
  }});
}}

// ── PIE ──
const sP=[...POS].sort((a,b)=>b.cost_eur-a.cost_eur);
const pD=sP.map(p=>+(p.cost_eur/TC*100).toFixed(1));
const pC=sP.map(p=>p.color);
new Chart(g('pieC'),{{type:'doughnut',
  data:{{labels:sP.map(p=>p.name.split(' ').slice(0,2).join(' ')),datasets:[{{data:pD,backgroundColor:pC,borderWidth:0,hoverOffset:5}}]}},
  options:{{responsive:true,maintainAspectRatio:false,cutout:'60%',
    plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>` ${{c.label}}: ${{c.parsed.toFixed(1)}}%`}}}}}}}}
}});
g('pieLeg').innerHTML=sP.map((p,i)=>`<span><span class="ld" style="background:${{pC[i]}}"></span>${{p.name.split(' ').slice(0,2).join(' ')}} ${{pD[i]}}%</span>`).join('');

// ── PNL CHART ──
const wp=POS.filter(p=>p.ok&&p.pnl_eur!==undefined).sort((a,b)=>b.pnl_eur-a.pnl_eur);
const ph=Math.max(260,wp.length*26+50);
g('pnlW').style.height=ph+'px';
g('pnlW').innerHTML='<canvas id="pnlC"></canvas>';
new Chart(g('pnlC'),{{type:'bar',
  data:{{labels:wp.map(p=>p.name.split(' ').slice(0,2).join(' ')),
    datasets:[{{data:wp.map(p=>+p.pnl_eur.toFixed(2)),
      backgroundColor:wp.map(p=>p.pnl_eur>=0?'rgba(52,211,153,.75)':'rgba(248,113,113,.75)'),
      borderRadius:3,borderWidth:0}}]}},
  options:{{indexAxis:'y',responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>`${{c.parsed.x>=0?'+':''}}€${{fmt(c.parsed.x)}}`}}}}}},
    scales:{{
      x:{{grid:{{color:'rgba(255,255,255,.05)'}},ticks:{{color:'#6b7585',font:{{size:10}},callback:v=>'€'+fmt(v)}}}},
      y:{{grid:{{display:false}},ticks:{{color:'#9ca3af',font:{{size:11}}}}}}
    }}
  }}
}});

// ── COMPARATIVA ──
const spY=BENCH[0]?.ytd, msY=BENCH[1]?.ytd;
const bars=[
  {{l:'Mi cartera · REAL total', v:PORT.pnl_pct, c:'#4f8ef7'}},
  {{l:'Mi cartera · CAGR anualizado', v:PORT.cagr, c:'#a78bfa'}},
  ...(PORT.ytd!=null?[{{l:'Posiciones abiertas · YTD', v:PORT.ytd, c:'#2dd4bf'}}]:[]),
  ...(spY!=null?[{{l:'S&P 500 (SPY) · YTD', v:spY, c:'#fbbf24'}}]:[]),
  ...(msY!=null?[{{l:'MSCI World (URTH) · YTD', v:msY, c:'#34d399'}}]:[]),
];
const mx=Math.max(...bars.map(b=>Math.abs(b.v)),1);
g('compB').innerHTML=bars.map(b=>`
  <div><div class="bh">
    <span class="bn2">${{b.l}}</span>
    <span class="bvl" style="color:${{b.v>=0?'var(--gr)':'var(--rd)'}}">${{fp1(b.v)}}</span>
  </div><div class="btrack"><div class="bfill" style="width:${{Math.max(Math.abs(b.v)/mx*100,2)}}%;background:${{b.c}}"></div></div></div>`
).join('');

// ── BENCHMARKS ──
const B=BENCH;
if(B[0]?.price) sv('bsp','$'+fmt(B[0].price,2));
if(B[1]?.price) sv('bms','$'+fmt(B[1].price,2));
[[B[0]?.ytd,'bspy','YTD'],[B[0]?.mtd,'bspm','MTD'],
 [B[1]?.ytd,'bmsy','YTD'],[B[1]?.mtd,'bmsm','MTD']].forEach(([v,id,lbl])=>{{
  if(v!=null){{
    const e=g(id); if(!e) return;
    e.textContent=lbl+': '+fp1(v);
    e.style.color=v>=0?'var(--gr)':'var(--rd)';
  }}
}});

// ── TABLA ──
const sr=[...POS].sort((a,b)=>b.cost_eur-a.cost_eur);
g('posB').innerHTML=sr.map((p,i)=>{{
  const hp=p.ok&&p.val_eur!==undefined;
  const w=hp&&TV>0?p.val_eur/TV*100:p.cost_eur/TC*100;
  const pc=hp?(p.pnl_eur>=0?'pos':'neg'):'';
  const priceNat = hp ? fmt(p.price, p.cur==='GBX'?1:p.cur==='DKK'?2:3)+' '+p.cur : '—';
  return `<tr>
    <td><div class="pn">${{p.name}}</div><div class="pk">${{p.ticker}}</div></td>
    <td><span class="badge">${{p.cur}}</span></td>
    <td class="mo" style="color:var(--mu)">${{p.qty}}</td>
    <td class="mo">€${{fmt(p.cost_eur/p.qty,2)}}</td>
    <td class="mo" style="font-size:11px;color:var(--mu)">${{priceNat}}</td>
    <td class="mo">${{hp?'€'+fmt(p.price_eur,3):'—'}}</td>
    <td class="mo">${{hp?'€'+fmt(p.val_eur):'—'}}</td>
    <td class="mo ${{pc}}" style="font-weight:600">${{hp?fE(p.pnl_eur):'—'}}</td>
    <td class="mo ${{pc}}">${{hp?fp(p.pnl_pct):'—'}}</td>
    <td><div class="wb"><span style="font-size:11px;color:var(--mu)">${{w.toFixed(1)}}%</span>
      <div class="wbar" style="width:${{Math.max(w*2.2,2)}}px;background:${{p.color}}"></div></div></td>
  </tr>`;
}}).join('');
</script></body></html>"""

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio_dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    try: import yfinance, pandas
    except ImportError: print("❌ pip install yfinance pandas"); exit(1)
    main()
