#!/usr/bin/env python3
"""
Dashboard de cartera DEGIRO - Saúl Trujillo
Uso: pip install yfinance && python portfolio_update.py
Genera: portfolio_dashboard.html
"""

import yfinance as yf
import json, os
from datetime import datetime, date

# ─────────────────────────────────────────────────────────
#  POSICIONES  (costes reales del historial DEGIRO)
#  Divisa = divisa nativa del mercado donde cotiza
# ─────────────────────────────────────────────────────────
POSITIONS = [
    # (nombre, ticker Yahoo Finance, qty, coste_eur, divisa, primera_compra)
    ("Adobe Inc",                "ADBE",      7,   1478.47, "USD", "2025-11-19"),
    ("QinetiQ Group PLC",        "QQ.L",      150,  711.27, "GBX", "2026-05-12"),  # Londres peniques
    ("Microsoft Corp",           "MSFT",      2,    638.99, "USD", "2026-03-26"),
    ("Italian Sea Group SpA",    "TISG.MI",   47,   418.41, "EUR", "2024-06-18"),  # Milán euros
    ("Greggs PLC",               "GRG.L",     22,   445.90, "GBX", "2025-03-04"),  # Londres peniques
    ("Wendy's Co",               "WEN",       37,   444.68, "USD", "2025-01-16"),
    ("PayPal Holdings Inc",      "PYPL",      7,    351.94, "USD", "2025-12-31"),
    ("FactSet Research Systems", "FDS",       2,    349.79, "USD", "2026-02-05"),
    ("Novo Nordisk A/S Class B", "NOVO-B.CO", 5,    245.83, "DKK", "2025-07-29"),  # Copenhague coronas
    ("ADR on Nice Ltd",          "NICE",      2,    235.02, "USD", "2025-09-02"),
    ("FRP Advisory Group PLC",   "FRP.L",     150,  221.76, "GBX", "2025-06-17"),  # Londres peniques
    ("Nomad Foods Ltd",          "NOMD",      18,   218.49, "USD", "2025-09-10"),
    ("Evolution AB",             "E3G1.MU",   3,    218.04, "EUR", "2024-12-23"),  # Xetra euros
    ("Euronet Worldwide Inc",    "EEFT",      3,    205.82, "USD", "2025-10-28"),
    ("Alphabet Inc Class A",     "GOOGL",     2,    205.23, "USD", "2022-09-23"),
    ("ADR on Novo Nordisk A/S",  "NVO",       6,    202.90, "USD", "2026-03-16"),  # NYSE ADR
    ("Brown-Forman Corp Class B","BF-B",      3,     91.59, "USD", "2025-02-07"),
]

BENCHMARKS = [
    ("S&P 500",    "SPY",  "USD"),
    ("MSCI World", "URTH", "USD"),
]

TOTAL_DEPOSITED = 8099.0
START_DATE      = date(2022, 7, 25)

# Tipos de cambio: cuántos EUR vale 1 unidad de cada divisa
FX_PAIRS = {
    "USD": "EURUSD=X",   # 1 USD = ? EUR
    "GBP": "EURGBP=X",   # 1 GBP = ? EUR  (GBX = GBP/100)
    "DKK": "EURDKK=X",   # 1 DKK = ? EUR
}

COLORS = [
    "#4f8ef7","#34d399","#a78bfa","#fbbf24","#f87171","#2dd4bf","#fb923c",
    "#c084fc","#86efac","#67e8f9","#fda4af","#a3e635","#fdba74","#7dd3fc",
    "#d8b4fe","#6ee7b7","#fcd34d",
]


# ─────────────────────────────────────────────────────────
#  FETCH HELPERS
# ─────────────────────────────────────────────────────────
def fetch_fx():
    """Descarga tipos de cambio a EUR."""
    fx = {"EUR": 1.0}
    print("  FX rates...", end=" ", flush=True)
    for cur, pair in FX_PAIRS.items():
        try:
            h = yf.Ticker(pair).history(period="5d")
            if not h.empty:
                # EURUSD=X da cuántos USD vale 1 EUR → invertimos
                rate = float(h["Close"].iloc[-1])
                fx[cur] = 1.0 / rate
        except Exception as e:
            print(f"\n    ⚠ FX {cur}: {e}")
    # GBX = penique = GBP/100
    fx["GBX"] = fx.get("GBP", 0.01175) / 100
    print(f"USD:{fx.get('USD',0.92):.4f}  GBX:{fx.get('GBX',0.01175):.5f}  DKK:{fx.get('DKK',0.134):.4f}")
    return fx


def fetch_ohlc(ticker, period="3y"):
    """Devuelve DataFrame con histórico diario de cierre."""
    h = yf.Ticker(ticker).history(period=period)
    if h.empty:
        return None
    h = h[["Close"]].copy()
    h.index = h.index.tz_localize(None)
    return h


def latest_price(h):
    """Último precio disponible."""
    if h is None or h.empty:
        return None
    return float(h["Close"].iloc[-1])


def price_on_or_after(h, target_date):
    """Primer precio en o después de target_date."""
    if h is None:
        return None
    mask = h.index.date >= target_date
    sub = h[mask]
    return float(sub["Close"].iloc[0]) if not sub.empty else None


# ─────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────
def main():
    print("\n🔄 Descargando datos de Yahoo Finance...\n")
    fx = fetch_fx()
    total_cost = sum(p[3] for p in POSITIONS)
    now = datetime.now()
    ytd_start = date(now.year, 1, 1)
    mtd_start = date(now.year, now.month, 1)

    # ── Posiciones ──
    pos_data = []
    hist_cache = {}   # ticker → DataFrame histórico

    for i, (name, tkr, qty, cost_eur, cur, buy_date) in enumerate(POSITIONS):
        print(f"  [{i+1:02d}/{len(POSITIONS)}] {name[:32]}...", end=" ", flush=True)
        try:
            h = fetch_ohlc(tkr, period="3y")
            if h is None:
                raise ValueError("sin datos")
            hist_cache[tkr] = h

            price     = latest_price(h)
            fxr       = fx.get(cur, 1.0)
            price_eur = price * fxr
            val_eur   = price_eur * qty
            pnl_eur   = val_eur - cost_eur
            pnl_pct   = pnl_eur / cost_eur * 100

            ytd_p = price_on_or_after(h, ytd_start)
            mtd_p = price_on_or_after(h, mtd_start)
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
            print(f"€{price_eur:.3f}  P&L:{pnl_pct:+.1f}%")
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
    bench_hist = {}
    for bname, btkr, bcur in BENCHMARKS:
        try:
            h = fetch_ohlc(btkr, period="3y")
            if h is None:
                raise ValueError("sin datos")
            bench_hist[btkr] = h
            price = latest_price(h)
            ytd_p = price_on_or_after(h, ytd_start)
            mtd_p = price_on_or_after(h, mtd_start)
            ytd_r = (price - ytd_p) / ytd_p * 100 if ytd_p else None
            mtd_r = (price - mtd_p) / mtd_p * 100 if mtd_p else None
            bench_data.append({"name": bname, "ticker": btkr, "cur": bcur,
                                "price": price, "ytd": ytd_r, "mtd": mtd_r})
            print(f"    {bname} ({btkr}): ${price:.2f}  YTD:{ytd_r:+.1f}%" if ytd_r else f"    {bname}: ${price:.2f}")
        except Exception as e:
            print(f"    {bname}: ERROR {e}")
            bench_data.append({"name": bname, "ticker": btkr, "cur": bcur,
                                "price": None, "ytd": None, "mtd": None})

    # ── Portfolio aggregates ──
    valid     = [p for p in pos_data if p.get("ok")]
    total_val = sum(p["val_eur"] for p in valid)
    total_pnl = total_val - total_cost
    pnl_pct   = total_pnl / total_cost * 100 if total_cost else 0
    years     = (date.today() - START_DATE).days / 365.25
    cagr      = ((1 + pnl_pct / 100) ** (1 / years) - 1) * 100 if years > 0 else 0

    yn = yd = mn = md = 0.0
    for p in valid:
        bd = date.fromisoformat(p["buy_date"])
        if p.get("ytd_ret") is not None and bd < ytd_start:
            yn += p["ytd_ret"] * p["cost_eur"]; yd += p["cost_eur"]
        if p.get("mtd_ret") is not None and bd < mtd_start:
            mn += p["mtd_ret"] * p["cost_eur"]; md += p["cost_eur"]

    portfolio = {
        "total_val": total_val, "total_cost": total_cost,
        "total_pnl": total_pnl, "pnl_pct": pnl_pct, "cagr": cagr,
        "ytd": yn / yd if yd > 0 else None,
        "mtd": mn / md if md > 0 else None,
        "updated": now.strftime("%d/%m/%Y %H:%M"),
        "deposited": TOTAL_DEPOSITED,
        "start_date": START_DATE.isoformat(),
    }

    # ── Gráfico histórico diario: cartera vs benchmarks desde inicio ──
    chart_data = build_chart_data(pos_data, bench_hist, fx, START_DATE)

    generate_html(pos_data, bench_data, portfolio, chart_data)

    print(f"\n✅  portfolio_dashboard.html generado")
    print(f"    Valor cartera : €{total_val:,.0f}")
    print(f"    P&L total     : €{total_pnl:+,.0f}  ({pnl_pct:+.1f}%)")
    print(f"    CAGR          : {cagr:+.1f}%")
    if portfolio["ytd"]: print(f"    YTD           : {portfolio['ytd']:+.1f}%")
    if portfolio["mtd"]: print(f"    MTD           : {portfolio['mtd']:+.1f}%")


# ─────────────────────────────────────────────────────────
#  HISTORICAL CHART DATA
#  Rentabilidad diaria normalizada a base 100 desde inicio
# ─────────────────────────────────────────────────────────
def build_chart_data(pos_data, bench_hist, fx, start_date):
    """
    Construye series diarias de rentabilidad acumulada (base 100)
    desde start_date para la cartera y los benchmarks.

    La cartera se calcula como un portfolio con rebalanceo en cada
    fecha de compra: antes de comprar una posición, su peso es 0;
    desde su fecha de compra contribuye con su valor de mercado.
    El NAV total se normaliza a 100 en la primera fecha disponible.
    """
    import pandas as pd

    print("\n  Construyendo gráfico histórico...", end=" ", flush=True)

    # ── 1. Descargar histórico de cada posición ──
    pos_hist = {}
    for p in pos_data:
        if not p.get("ok"):
            continue
        tkr = p["ticker"]
        try:
            h = yf.Ticker(tkr).history(period="5y")
            if h.empty:
                continue
            h = h[["Close"]].copy()
            h.index = h.index.tz_localize(None)
            pos_hist[tkr] = h
        except:
            continue

    # ── 2. Construir índice de fechas común desde start_date ──
    # Usamos el calendario de días hábiles de SPY como referencia
    ref_h = bench_hist.get("SPY")
    if ref_h is None or ref_h.empty:
        print("sin datos benchmark")
        return {}

    mask = ref_h.index.date >= start_date
    all_dates = ref_h[mask].index
    if all_dates.empty:
        return {}

    # ── 3. Para cada fecha, calcular el valor de la cartera ──
    # Método: para cada posición, su valor en una fecha dada es
    # precio(fecha) * qty * fx_rate, solo si fecha >= buy_date.
    # El valor total de la cartera en cada fecha es la suma de todas
    # las posiciones activas en esa fecha.

    portfolio_values = pd.Series(index=all_dates, dtype=float)

    for dt in all_dates:
        dt_date = dt.date()
        total = 0.0
        has_any = False
        for p in pos_data:
            if not p.get("ok"):
                continue
            buy_date = date.fromisoformat(p["buy_date"])
            if dt_date < buy_date:
                continue  # aún no comprada
            h = pos_hist.get(p["ticker"])
            if h is None:
                continue
            # Precio más reciente disponible hasta esta fecha
            mask_price = h.index <= dt
            sub = h[mask_price]
            if sub.empty:
                continue
            price = float(sub["Close"].iloc[-1])
            fxr = fx.get(p["cur"], 1.0)
            val = price * fxr * p["qty"]
            total += val
            has_any = True
        portfolio_values[dt] = total if has_any else None

    portfolio_values = portfolio_values.dropna()
    if portfolio_values.empty:
        print("sin datos cartera")
        return {}

    # Normalizar a base 100 en la primera fecha
    base = portfolio_values.iloc[0]
    portfolio_norm = (portfolio_values / base * 100).round(2)

    # ── 4. Benchmarks normalizados desde la misma primera fecha ──
    bench_out = {}
    first_dt = portfolio_norm.index[0]

    for bname, btkr, _ in BENCHMARKS:
        h = bench_hist.get(btkr)
        if h is None:
            continue
        # Precio del benchmark en la primera fecha de la cartera
        mask_base = h.index <= first_dt
        sub_base = h[mask_base]
        if sub_base.empty:
            continue
        base_price = float(sub_base["Close"].iloc[-1])

        # Serie desde first_dt
        mask_series = h.index >= first_dt
        s = h[mask_series]["Close"].copy()
        if s.empty:
            continue

        # Reindexar al mismo calendario que la cartera y ffill
        s = s.reindex(portfolio_norm.index, method="ffill")
        s_norm = (s / base_price * 100).round(2)
        bench_out[bname] = s_norm.dropna().tolist()

    dates  = [d.strftime("%Y-%m-%d") for d in portfolio_norm.index]
    values = portfolio_norm.tolist()

    # Alinear longitudes
    min_len = min(len(values), *[len(v) for v in bench_out.values()]) if bench_out else len(values)
    dates  = dates[:min_len]
    values = values[:min_len]
    for k in bench_out:
        bench_out[k] = bench_out[k][:min_len]

    print(f"OK ({len(dates)} días, cartera: {values[0]:.1f}→{values[-1]:.1f})")

    return {
        "dates":      dates,
        "portfolio":  values,
        "benchmarks": bench_out,
    }


# ─────────────────────────────────────────────────────────
#  HTML GENERATOR
# ─────────────────────────────────────────────────────────
def generate_html(pos_data, bench_data, portfolio, chart_data):
    pj  = json.dumps(pos_data,   ensure_ascii=False)
    bj  = json.dumps(bench_data, ensure_ascii=False)
    oj  = json.dumps(portfolio,  ensure_ascii=False)
    cj  = json.dumps(chart_data, ensure_ascii=False)
    n   = len(pos_data)
    upd = portfolio["updated"]

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
.card{{background:var(--bg2);border:1px solid var(--bd);border-radius:12px;padding:20px;}}
.ct{{font-size:13px;font-weight:600;color:var(--tx);margin-bottom:14px;}}
.cs{{font-size:11px;color:var(--mu);font-weight:400;margin-left:6px;}}
/* Chart historico full width */
.chart-full{{margin-bottom:14px;}}
.chart-legend{{display:flex;gap:20px;margin-bottom:12px;font-size:12px;}}
.chart-legend span{{display:flex;align-items:center;gap:6px;}}
.cleg-dot{{width:10px;height:3px;border-radius:2px;}}
/* Grid 2 col */
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;}}
/* Perf row */
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
.ft{{text-align:center;color:var(--mu);font-size:11px;padding:20px 0;border-top:1px solid var(--bd);margin-top:4px;}}
</style></head><body>

<div class="hdr">
  <div><h1>📊 Mi Cartera · DEGIRO</h1><p>Yahoo Finance · <span class="ok">✓ Actualizado {upd}</span></p></div>
  <div class="ts">Última actualización<br><strong style="color:var(--tx)">{upd}</strong><br><small>Ejecuta portfolio_update.py para refrescar</small></div>
</div>

<!-- KPIs -->
<div class="krow">
  <div class="kpi"><div class="lb">Valor cartera</div><div class="vl neu" id="kv">—</div><div class="sb">a precios actuales</div></div>
  <div class="kpi"><div class="lb">P&L Total</div><div class="vl" id="kp">—</div><div class="sb" id="ks">desde inicio</div></div>
  <div class="kpi"><div class="lb">Rentab. YTD</div><div class="vl" id="ky">—</div><div class="sb">año en curso pond.</div></div>
  <div class="kpi"><div class="lb">Rentab. MTD</div><div class="vl" id="km">—</div><div class="sb">mes en curso pond.</div></div>
  <div class="kpi"><div class="lb">Anualizada</div><div class="vl" id="ka">—</div><div class="sb">CAGR desde jul 2022</div></div>
</div>

<!-- GRAFICO HISTORICO DIARIO -->
<div class="card chart-full">
  <div class="ct">Evolución cartera vs benchmarks <span class="cs">rentabilidad acumulada diaria desde jul 2022 · base 100</span></div>
  <div class="chart-legend" id="chartLeg"></div>
  <div style="position:relative;height:320px;">
    <canvas id="histC" role="img" aria-label="Evolución histórica diaria de la cartera frente al SP500 y MSCI World"></canvas>
  </div>
</div>

<!-- GRAFICOS PESO Y PNL -->
<div class="g2">
  <div class="card">
    <div class="ct">Peso por posición <span class="cs">% sobre coste adquisición</span></div>
    <div style="position:relative;height:260px;"><canvas id="pieC" role="img" aria-label="Pesos por posición"></canvas></div>
    <div class="pie-leg" id="pieLeg"></div>
  </div>
  <div class="card">
    <div class="ct">P&L por posición <span class="cs">€ ganancia / pérdida</span></div>
    <div id="pnlW" style="position:relative;height:260px;"><canvas id="pnlC" role="img" aria-label="P&L por posición"></canvas></div>
  </div>
</div>

<!-- RENTABILIDADES COMPARADAS + BENCHMARKS -->
<div class="g32">
  <div class="card">
    <div class="ct">Rentabilidades comparadas</div>
    <div class="cb" id="compB"></div>
  </div>
  <div class="card">
    <div class="ct">Benchmarks · tiempo real</div>
    <div class="bg">
      <div class="bi"><div class="bn">S&P 500 (SPY)</div><div class="bv neu" id="bsp">—</div><div class="bs"><span id="bspy">YTD: —</span><span id="bspm">MTD: —</span></div></div>
      <div class="bi"><div class="bn">MSCI World (URTH)</div><div class="bv neu" id="bms">—</div><div class="bs"><span id="bmsy">YTD: —</span><span id="bmsm">MTD: —</span></div></div>
      <div class="bi"><div class="bn">Total depositado</div><div class="bv neu">€8.099</div><div class="bs"><span>jul 2022 → hoy</span></div></div>
      <div class="bi"><div class="bn">Inicio cartera</div><div class="bv neu">25/07/2022</div><div class="bs"><span>{round((date.today()-START_DATE).days/365.25,1)} años</span></div></div>
    </div>
  </div>
</div>

<!-- TABLA POSICIONES -->
<div class="pc">
  <div class="pt">
    Posiciones abiertas · {n} valores
    <span class="ph">Yahoo Finance · python portfolio_update.py para actualizar</span>
  </div>
  <table>
    <thead><tr>
      <th>Compañía</th><th>Div.</th><th>Acc.</th>
      <th>Coste medio (€)</th><th>Precio actual (€)</th>
      <th>Valor (€)</th><th>P&amp;L (€)</th><th>P&amp;L %</th><th>Peso</th>
    </tr></thead>
    <tbody id="posB"></tbody>
  </table>
</div>

<div class="ft">Datos: <strong>Yahoo Finance (yfinance)</strong> · Divisas: EURUSD=X, EURGBP=X, EURDKK=X · Generado: {upd}</div>

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
const sv   = (id,v) => {{const e=g(id);if(e)e.textContent=v;}};
const cl   = v => v===null||v===undefined?'neu':v>=0?'pos':'neg';

// ── KPIs ──
sv('kv','€'+fmt(PORT.total_val));
sv('kp',fE(PORT.total_pnl)); g('kp').className='vl '+cl(PORT.total_pnl);
sv('ks',fp1(PORT.pnl_pct)+' s/ coste');
if(PORT.ytd!==null){{sv('ky',fp1(PORT.ytd));g('ky').className='vl '+cl(PORT.ytd);}}
if(PORT.mtd!==null){{sv('km',fp1(PORT.mtd));g('km').className='vl '+cl(PORT.mtd);}}
sv('ka',fp1(PORT.cagr)); g('ka').className='vl '+cl(PORT.cagr);

const TC = POS.reduce((s,p)=>s+p.cost_eur,0);
const TV = POS.filter(p=>p.ok).reduce((s,p)=>s+(p.val_eur||0),0);

// ── GRÁFICO HISTÓRICO DIARIO ──
if(CHRT.dates && CHRT.dates.length) {{
  const BENCH_COLORS = {{'S&P 500':'#fbbf24','MSCI World':'#34d399'}};
  const datasets = [
    {{
      label:'Mi cartera',
      data: CHRT.portfolio,
      borderColor:'#4f8ef7',
      backgroundColor:'rgba(79,142,247,0.08)',
      borderWidth:2,
      pointRadius:0,
      fill:true,
      tension:0.2,
    }}
  ];
  Object.entries(CHRT.benchmarks||{{}}).forEach(([name,vals])=>{{
    datasets.push({{
      label:name,
      data:vals,
      borderColor:BENCH_COLORS[name]||'#a78bfa',
      backgroundColor:'transparent',
      borderWidth:1.5,
      borderDash:[4,2],
      pointRadius:0,
      fill:false,
      tension:0.2,
    }});
  }});

  // Leyenda manual
  g('chartLeg').innerHTML = datasets.map(d=>
    `<span><span class="cleg-dot" style="background:${{d.borderColor}};height:${{d.borderDash?'2px':'3px'}}"></span>${{d.label}}</span>`
  ).join('');

  // Submuestrear labels para no sobrecargar el eje X
  const n = CHRT.dates.length;
  const step = Math.max(1, Math.floor(n/12));
  const labelsFmt = CHRT.dates.map((d,i) => i%step===0 ? d.slice(0,7) : '');

  new Chart(g('histC'), {{
    type:'line',
    data:{{ labels: CHRT.dates, datasets }},
    options:{{
      responsive:true, maintainAspectRatio:false,
      interaction:{{ mode:'index', intersect:false }},
      plugins:{{
        legend:{{display:false}},
        tooltip:{{
          callbacks:{{
            label: ctx => {{ const d=(ctx.parsed.y-100).toFixed(1); return ` ${{ctx.dataset.label}}: ${{ctx.parsed.y.toFixed(1)}} (${{+d>=0?'+':''}}${{d}}%)`; }},
          }}
        }}
      }},
      scales:{{
        x:{{
          grid:{{color:'rgba(255,255,255,.04)'}},
          ticks:{{
            color:'#6b7585', font:{{size:10}},
            callback:(v,i) => labelsFmt[i] || null,
            maxRotation:0,
          }}
        }},
        y:{{
          grid:{{color:'rgba(255,255,255,.05)'}},
          ticks:{{color:'#6b7585', font:{{size:10}}, callback:v=>v.toFixed(0)}},
          title:{{display:true,text:'Base 100',color:'#6b7585',font:{{size:10}}}}
        }}
      }}
    }}
  }});
}}

// ── PIE CHART ──
const sP = [...POS].sort((a,b)=>b.cost_eur-a.cost_eur);
const pD = sP.map(p=>+(p.cost_eur/TC*100).toFixed(1));
const pC = sP.map(p=>p.color);
new Chart(g('pieC'),{{
  type:'doughnut',
  data:{{labels:sP.map(p=>p.name.split(' ').slice(0,2).join(' ')),datasets:[{{data:pD,backgroundColor:pC,borderWidth:0,hoverOffset:5}}]}},
  options:{{responsive:true,maintainAspectRatio:false,cutout:'60%',
    plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>` ${{c.label}}: ${{c.parsed.toFixed(1)}}%`}}}}}}}}
}});
g('pieLeg').innerHTML = sP.map((p,i)=>`<span><span class="ld" style="background:${{pC[i]}}"></span>${{p.name.split(' ').slice(0,2).join(' ')}} ${{pD[i]}}%</span>`).join('');

// ── PNL CHART ──
const wp = POS.filter(p=>p.ok&&p.pnl_eur!==undefined).sort((a,b)=>b.pnl_eur-a.pnl_eur);
const ph = Math.max(260, wp.length*26+50);
g('pnlW').style.height = ph+'px';
g('pnlW').innerHTML = '<canvas id="pnlC" role="img" aria-label="P&L por posición"></canvas>';
new Chart(g('pnlC'),{{
  type:'bar',
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

// ── BARRAS COMPARATIVAS ──
const spY=BENCH[0]?.ytd, msY=BENCH[1]?.ytd;
const bars=[
  {{l:'Mi cartera · total desde inicio', v:PORT.pnl_pct, c:'#4f8ef7'}},
  {{l:'Mi cartera · CAGR anualizada',    v:PORT.cagr,    c:'#a78bfa'}},
  ...(PORT.ytd!==null?[{{l:'Mi cartera · YTD', v:PORT.ytd, c:'#2dd4bf'}}]:[]),
  ...(spY!=null?[{{l:'S&P 500 (SPY) · YTD', v:spY, c:'#fbbf24'}}]:[]),
  ...(msY!=null?[{{l:'MSCI World (URTH) · YTD', v:msY, c:'#34d399'}}]:[]),
];
const mx = Math.max(...bars.map(b=>Math.abs(b.v)),1);
g('compB').innerHTML = bars.map(b=>`
  <div>
    <div class="bh">
      <span class="bn2">${{b.l}}</span>
      <span class="bvl" style="color:${{b.v>=0?'var(--gr)':'var(--rd)'}}">${{fp1(b.v)}}</span>
    </div>
    <div class="btrack"><div class="bfill" style="width:${{Math.max(Math.abs(b.v)/mx*100,2)}}%;background:${{b.c}}"></div></div>
  </div>`).join('');

// ── BENCHMARKS ──
const B = BENCH;
if(B[0]?.price){{sv('bsp','$'+fmt(B[0].price,2));}}
if(B[1]?.price){{sv('bms','$'+fmt(B[1].price,2));}}
[[B[0]?.ytd,'bspy'],[B[0]?.mtd,'bspm'],[B[1]?.ytd,'bmsy'],[B[1]?.mtd,'bmsm']].forEach(([v,id])=>{{
  if(v!=null){{
    const e=g(id); if(!e)return;
    e.textContent=(id.includes('y')?'YTD: ':'MTD: ')+fp1(v);
    e.style.color=v>=0?'var(--gr)':'var(--rd)';
  }}
}});

// ── TABLA POSICIONES ──
const sr = [...POS].sort((a,b)=>b.cost_eur-a.cost_eur);
g('posB').innerHTML = sr.map((p,i)=>{{
  const hp = p.ok && p.val_eur !== undefined;
  const w  = hp && TV>0 ? p.val_eur/TV*100 : p.cost_eur/TC*100;
  const pc = hp ? (p.pnl_eur>=0?'pos':'neg') : '';
  // Precio nativo con divisa
  const priceNative = hp ? `${{fmt(p.price, p.cur==='GBX'?1:p.cur==='DKK'?2:3)}} ${{p.cur}}` : '—';
  return `<tr>
    <td><div class="pn">${{p.name}}</div><div class="pk">${{p.ticker}}</div></td>
    <td><span class="badge">${{p.cur}}</span></td>
    <td class="mo" style="color:var(--mu)">${{p.qty}}</td>
    <td class="mo">€${{fmt(p.cost_eur/p.qty,2)}}</td>
    <td class="mo">${{hp?'<span style=\"color:var(--tx)\">€'+fmt(p.price_eur,3)+'</span><br><span style=\"font-size:10px;color:var(--mu)\">'+fmt(p.price, p.cur==='GBX'?1:p.cur==='DKK'?2:3)+' '+p.cur+'</span>':'—'}}</td>
    <td class="mo">${{hp?'€'+fmt(p.val_eur):'—'}}</td>
    <td class="mo ${{pc}}" style="font-weight:600">${{hp?fE(p.pnl_eur):'—'}}</td>
    <td class="mo ${{pc}}">${{hp?fp(p.pnl_pct):'—'}}</td>
    <td><div class="wb">
      <span style="font-size:11px;color:var(--mu)">${{w.toFixed(1)}}%</span>
      <div class="wbar" style="width:${{Math.max(w*2.2,2)}}px;background:${{p.color}}"></div>
    </div></td>
  </tr>`;
}}).join('');
</script></body></html>"""

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio_dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    try:
        import yfinance
    except ImportError:
        print("❌ Ejecuta: pip install yfinance")
        exit(1)
    main()
