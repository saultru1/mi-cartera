#!/usr/bin/env python3
"""
Dashboard de cartera - DEGIRO
Descarga precios de Yahoo Finance y genera portfolio_dashboard.html

Uso:
    pip install yfinance
    python portfolio_update.py
"""

import yfinance as yf
import json, os
from datetime import datetime, date

# ─────────────────────────────────────────────────────────────
#  POSICIONES  (datos reales DEGIRO a 22/05/2026)
#  BEP = precio medio de coste en divisa local (columna DEGIRO)
#  cost_eur = BEP * qty convertido a EUR al tipo de cambio aprox
# ─────────────────────────────────────────────────────────────
POSITIONS = [
    # nombre,                    ticker,       qty,  bep_local,  divisa,  cost_eur,     fecha_primera_compra
    ("Adobe Inc",                "ADBE",        7,   245.686,    "USD",   1480.47,      "2025-11-19"),
    ("ADR on Nice Ltd",          "NICE",        2,   135.20,     "USD",   235.02,       "2025-09-02"),
    ("ADR on Novo Nordisk A/S",  "NVO",         6,   38.47,      "USD",   202.90,       "2026-03-16"),
    ("Alphabet Inc Class A",     "GOOGL",       2,   99.03,      "USD",   205.23,       "2022-09-23"),
    ("Brown-Forman Corp Class B","BF-B",        3,   30.77,      "USD",   91.59,        "2025-02-07"),
    ("Euronet Worldwide Inc",    "EEFT",        3,   79.04,      "USD",   205.82,       "2025-10-28"),
    ("Evolution AB",             "EVO.ST",      3,   71.38,      "EUR",   218.04,       "2024-12-23"),
    ("Factset Research Systems", "FDS",         2,   204.56,     "USD",   349.79,       "2026-02-05"),
    ("FRP Advisory Group PLC",   "FRP.L",       150, 123.00,     "GBX",   221.76,       "2025-06-17"),
    ("Greggs PLC",               "GRG.L",       22,  1670.45,    "GBX",   445.90,       "2025-03-04"),
    ("Italian Sea Group SpA",    "TISG.MI",     47,  8.694,      "EUR",   418.41,       "2024-06-18"),
    ("Microsoft Corp",           "MSFT",        2,   366.40,     "USD",   638.99,       "2026-03-26"),
    ("Nomad Foods Ltd",          "NOMD",        18,  14.07,      "USD",   218.49,       "2025-09-10"),
    ("Novo Nordisk A/S Class B", "NOVO-B.CO",   5,   358.60,     "DKK",   245.83,       "2025-07-29"),
    ("PayPal Holdings Inc",      "PYPL",        7,   58.014,     "USD",   351.94,       "2026-01-16"),
    ("QinetiQ Group PLC",        "QQ.L",        150, 405.80,     "GBX",   711.27,       "2026-05-12"),
    ("Wendy's Co",               "WEN",         37,  12.818,     "USD",   444.68,       "2025-01-16"),
]

BENCHMARKS = [
    ("S&P 500",    "SPY"),
    ("MSCI World", "URTH"),
]

TOTAL_DEPOSITED = 8099.0
START_DATE       = date(2022, 7, 25)

FX_TICKERS = {
    "USD": "EURUSD=X",
    "GBP": "EURGBP=X",
    "DKK": "EURDKK=X",
    "SEK": "EURSEK=X",
}

COLORS = [
    "#4f8ef7","#34d399","#a78bfa","#fbbf24","#f87171",
    "#2dd4bf","#fb923c","#c084fc","#86efac","#67e8f9",
    "#fda4af","#a3e635","#fdba74","#7dd3fc","#d8b4fe",
    "#6ee7b7","#fcd34d",
]


def fetch_fx():
    fx = {"EUR": 1.0}
    print("  Descargando FX rates...", end=" ", flush=True)
    for cur, ticker in FX_TICKERS.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2d")
            if not hist.empty:
                rate = float(hist["Close"].iloc[-1])
                fx[cur] = 1.0 / rate
        except Exception as e:
            print(f"\n    ⚠ FX {cur}: {e}")
    fx["GBX"] = fx.get("GBP", 0.01175) / 100
    print(f"OK  (1 USD ≈ {fx.get('USD', 0.92):.4f} EUR)")
    return fx


def fetch_ticker(ticker):
    t = yf.Ticker(ticker)
    hist = t.history(period="6mo")
    if hist.empty:
        return None, None, None
    price = float(hist["Close"].iloc[-1])
    now = datetime.now()

    def first_close_on_or_after(df, target_date):
        mask = df.index.date >= target_date
        subset = df[mask]
        return float(subset["Close"].iloc[0]) if not subset.empty else None

    ytd_p = first_close_on_or_after(hist, date(now.year, 1, 1))
    mtd_p = first_close_on_or_after(hist, date(now.year, now.month, 1))
    return price, ytd_p, mtd_p


def main():
    print("\n🔄 Descargando datos de Yahoo Finance...\n")
    fx = fetch_fx()

    total_cost = sum(p[5] for p in POSITIONS)
    pos_data = []

    for i, (name, ticker, qty, bep_local, cur, cost_eur, buy_date) in enumerate(POSITIONS):
        print(f"  [{i+1:02d}/{len(POSITIONS)}] {name} ({ticker})...", end=" ", flush=True)
        try:
            price, ytd_p, mtd_p = fetch_ticker(ticker)
            if price is None:
                raise ValueError("Sin datos")

            fx_rate   = fx.get(cur, 1.0)
            price_eur = price * fx_rate
            val_eur   = price_eur * qty
            pnl_eur   = val_eur - cost_eur
            pnl_pct   = (pnl_eur / cost_eur) * 100
            ytd_ret   = ((price - ytd_p) / ytd_p * 100) if ytd_p else None
            mtd_ret   = ((price - mtd_p) / mtd_p * 100) if mtd_p else None

            pos_data.append({
                "name": name, "ticker": ticker, "qty": qty,
                "cost_eur": cost_eur, "cur": cur, "buy_date": buy_date,
                "price": price, "price_eur": price_eur,
                "val_eur": val_eur, "pnl_eur": pnl_eur, "pnl_pct": pnl_pct,
                "ytd_ret": ytd_ret, "mtd_ret": mtd_ret,
                "ok": True, "color": COLORS[i % len(COLORS)],
            })
            print(f"€{price_eur:.2f}  P&L: {pnl_pct:+.1f}%")
        except Exception as e:
            print(f"ERROR: {e}")
            pos_data.append({
                "name": name, "ticker": ticker, "qty": qty,
                "cost_eur": cost_eur, "cur": cur, "buy_date": buy_date,
                "ok": False, "color": COLORS[i % len(COLORS)],
            })

    print("\n  Descargando benchmarks...")
    bench_data = []
    now = datetime.now()
    for bname, bticker in BENCHMARKS:
        try:
            price, ytd_p, mtd_p = fetch_ticker(bticker)
            ytd_ret = ((price - ytd_p) / ytd_p * 100) if (price and ytd_p) else None
            mtd_ret = ((price - mtd_p) / mtd_p * 100) if (price and mtd_p) else None
            bench_data.append({"name": bname, "ticker": bticker,
                                "price": price, "ytd": ytd_ret, "mtd": mtd_ret})
            ytd_str = f"  YTD: {ytd_ret:+.1f}%" if ytd_ret else ""
            print(f"    {bname}: ${price:.2f}{ytd_str}")
        except Exception as e:
            print(f"    {bname}: ERROR {e}")
            bench_data.append({"name": bname, "ticker": bticker,
                                "price": None, "ytd": None, "mtd": None})

    # Aggregates
    valid     = [p for p in pos_data if p.get("ok")]
    total_val = sum(p["val_eur"] for p in valid)
    total_pnl = total_val - total_cost
    pnl_pct   = (total_pnl / total_cost) * 100 if total_cost else 0
    years     = (date.today() - START_DATE).days / 365.25
    cagr      = ((1 + pnl_pct / 100) ** (1 / years) - 1) * 100 if years > 0 else 0

    ytd_num = ytd_den = mtd_num = mtd_den = 0.0
    for p in valid:
        bd        = date.fromisoformat(p["buy_date"])
        ytd_start = date(now.year, 1, 1)
        mtd_start = date(now.year, now.month, 1)
        if p.get("ytd_ret") is not None and bd < ytd_start:
            ytd_num += p["ytd_ret"] * p["cost_eur"]; ytd_den += p["cost_eur"]
        if p.get("mtd_ret") is not None and bd < mtd_start:
            mtd_num += p["mtd_ret"] * p["cost_eur"]; mtd_den += p["cost_eur"]

    portfolio = {
        "total_val":  total_val,
        "total_cost": total_cost,
        "total_pnl":  total_pnl,
        "pnl_pct":    pnl_pct,
        "cagr":       cagr,
        "ytd":        ytd_num / ytd_den if ytd_den > 0 else None,
        "mtd":        mtd_num / mtd_den if mtd_den > 0 else None,
        "updated":    datetime.now().strftime("%d/%m/%Y %H:%M"),
        "deposited":  TOTAL_DEPOSITED,
    }

    generate_html(pos_data, bench_data, portfolio)

    print(f"\n✅  Dashboard generado: portfolio_dashboard.html")
    print(f"    Valor cartera : €{total_val:,.0f}  (DEGIRO muestra €6.467,77)")
    print(f"    P&L total     : €{total_pnl:+,.0f}  ({pnl_pct:+.1f}%)")
    print(f"    CAGR          : {cagr:+.1f}%")
    if portfolio["ytd"]: print(f"    YTD           : {portfolio['ytd']:+.1f}%")
    if portfolio["mtd"]: print(f"    MTD           : {portfolio['mtd']:+.1f}%")


def generate_html(pos_data, bench_data, portfolio):
    pos_json   = json.dumps(pos_data,   ensure_ascii=False)
    bench_json = json.dumps(bench_data, ensure_ascii=False)
    port_json  = json.dumps(portfolio,  ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mi Cartera · {portfolio['updated']}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
:root{{--bg:#0e1117;--bg2:#161b27;--bg3:#1e2535;--bg4:#252d40;--border:rgba(255,255,255,0.07);--text:#dde1ea;--muted:#6b7585;--blue:#4f8ef7;--green:#34d399;--red:#f87171;--amber:#fbbf24;--purple:#a78bfa;--font:'Inter',system-ui,sans-serif;--mono:'JetBrains Mono','Fira Mono',monospace;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
html{{background:var(--bg);color:var(--text);font-family:var(--font);font-size:14px;}}
body{{min-height:100vh;padding:28px 32px;max-width:1380px;margin:0 auto;}}
.hdr{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px;}}
.hdr h1{{font-size:20px;font-weight:600;letter-spacing:-.5px;color:#fff;}}
.hdr p{{color:var(--muted);font-size:12px;margin-top:4px;}}
.ts{{font-size:11px;color:var(--muted);text-align:right;line-height:1.8;}}
.badge-ok{{display:inline-block;background:rgba(52,211,153,.15);color:var(--green);border-radius:4px;padding:2px 8px;font-size:11px;font-weight:500;}}
.kpi-row{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:16px;}}
.kpi{{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:14px 16px;}}
.kpi .lbl{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.6px;margin-bottom:8px;}}
.kpi .val{{font-size:22px;font-weight:700;font-family:var(--mono);letter-spacing:-1px;line-height:1;}}
.kpi .sub{{font-size:11px;color:var(--muted);margin-top:6px;}}
.pos{{color:var(--green);}}.neg{{color:var(--red);}}.neu{{color:var(--text);}}
.charts-row{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;}}
.card{{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:20px;}}
.card-title{{font-size:13px;font-weight:600;color:var(--text);margin-bottom:14px;}}
.card-sub{{font-size:11px;color:var(--muted);font-weight:400;margin-left:6px;}}
.perf-row{{display:grid;grid-template-columns:3fr 2fr;gap:14px;margin-bottom:14px;}}
.comp-bars{{display:flex;flex-direction:column;gap:12px;}}
.bar-hdr{{display:flex;justify-content:space-between;font-size:12px;margin-bottom:5px;}}
.bar-name{{color:var(--muted);}}.bar-val{{font-weight:600;font-family:var(--mono);}}
.bar-track{{height:7px;background:var(--bg4);border-radius:4px;overflow:hidden;}}
.bar-fill{{height:100%;border-radius:4px;}}
.bench-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;}}
.bench-item{{background:var(--bg3);border-radius:8px;padding:12px 14px;}}
.bn{{font-size:11px;color:var(--muted);margin-bottom:5px;font-weight:500;}}
.bv{{font-size:17px;font-weight:700;font-family:var(--mono);}}
.bs{{font-size:11px;color:var(--muted);margin-top:4px;display:flex;gap:10px;flex-wrap:wrap;}}
.pie-legend{{display:flex;flex-wrap:wrap;gap:8px 14px;margin-top:12px;font-size:11px;color:var(--muted);}}
.pie-legend span{{display:flex;align-items:center;gap:5px;}}
.ldot{{width:8px;height:8px;border-radius:2px;flex-shrink:0;}}
.pos-card{{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:16px;}}
.pos-card-title{{font-size:13px;font-weight:600;margin-bottom:16px;display:flex;justify-content:space-between;}}
.hint{{font-size:11px;color:var(--muted);font-weight:400;}}
table{{width:100%;border-collapse:collapse;}}
th{{font-size:10px;color:var(--muted);text-align:right;padding:6px 10px;font-weight:500;text-transform:uppercase;letter-spacing:.4px;border-bottom:1px solid var(--border);white-space:nowrap;}}
th:first-child{{text-align:left;}}
td{{font-size:12px;padding:10px 10px;border-bottom:1px solid rgba(255,255,255,0.03);text-align:right;}}
td:first-child{{text-align:left;}}
tr:last-child td{{border-bottom:none;}}
tr:hover td{{background:rgba(255,255,255,.02);}}
.pname{{font-weight:500;font-size:13px;color:var(--text);}}
.ptick{{font-family:var(--mono);font-size:10px;color:var(--muted);margin-top:2px;}}
.badge{{display:inline-block;background:var(--bg4);border-radius:3px;padding:2px 6px;font-size:10px;font-family:var(--mono);color:var(--muted);}}
.wb{{display:flex;align-items:center;gap:7px;justify-content:flex-end;}}
.wbar{{height:4px;border-radius:2px;opacity:.65;}}
.mono{{font-family:var(--mono);}}
.footer{{text-align:center;color:var(--muted);font-size:11px;padding:20px 0;border-top:1px solid var(--border);margin-top:4px;}}
</style>
</head>
<body>
<div class="hdr">
  <div>
    <h1>📊 Mi Cartera · DEGIRO</h1>
    <p>Datos descargados de Yahoo Finance · <span class="badge-ok">✓ Actualizado</span></p>
  </div>
  <div class="ts">
    Última actualización<br>
    <strong style="color:var(--text)">{portfolio['updated']}</strong><br>
    <small>Ejecuta portfolio_update.py para refrescar</small>
  </div>
</div>
<div class="kpi-row">
  <div class="kpi"><div class="lbl">Valor cartera</div><div class="val neu" id="kv"></div><div class="sub">a precios actuales</div></div>
  <div class="kpi"><div class="lbl">P&L Total</div><div class="val" id="kpnl"></div><div class="sub" id="kpnl-sub"></div></div>
  <div class="kpi"><div class="lbl">Rentab. YTD</div><div class="val" id="kytd"></div><div class="sub">ponderado por posición</div></div>
  <div class="kpi"><div class="lbl">Rentab. MTD</div><div class="val" id="kmtd"></div><div class="sub" id="kmtd-sub"></div></div>
  <div class="kpi"><div class="lbl">Anualizada</div><div class="val" id="kanual"></div><div class="sub">CAGR desde jul 2022</div></div>
</div>
<div class="charts-row">
  <div class="card">
    <div class="card-title">Peso por posición <span class="card-sub">% sobre coste adquisición</span></div>
    <div style="position:relative;height:260px;"><canvas id="pieC" role="img" aria-label="Pesos por posición"></canvas></div>
    <div class="pie-legend" id="pieLeg"></div>
  </div>
  <div class="card">
    <div class="card-title">P&L por posición <span class="card-sub">€ ganancia / pérdida</span></div>
    <div id="pnlWrap" style="position:relative;height:260px;"><canvas id="pnlC" role="img" aria-label="P&L por posición"></canvas></div>
  </div>
</div>
<div class="perf-row">
  <div class="card">
    <div class="card-title">Rentabilidades comparadas</div>
    <div class="comp-bars" id="compBars"></div>
  </div>
  <div class="card">
    <div class="card-title">Benchmarks</div>
    <div class="bench-grid" id="benchGrid"></div>
  </div>
</div>
<div class="pos-card">
  <div class="pos-card-title">
    Posiciones abiertas · {len(pos_data)} valores
    <span class="hint">Yahoo Finance · ejecuta portfolio_update.py para actualizar</span>
  </div>
  <table>
    <thead><tr>
      <th>Compañía</th><th>Div.</th><th>Acc.</th>
      <th>Coste medio (€)</th><th>Precio actual (€)</th>
      <th>Valor (€)</th><th>P&amp;L (€)</th><th>P&amp;L %</th><th>Peso</th>
    </tr></thead>
    <tbody id="posBody"></tbody>
  </table>
</div>
<div class="footer">
  Datos: <strong>Yahoo Finance (yfinance)</strong> · Generado: {portfolio['updated']}
</div>
<script>
const POS   = {pos_json};
const BENCH = {bench_json};
const PORT  = {port_json};
const fmt  = (n,d=0) => (+n).toLocaleString('es-ES',{{minimumFractionDigits:d,maximumFractionDigits:d}});
const fp   = v => (v>=0?'+':'')+v.toFixed(1)+'%';
const fmtE = v => (v>=0?'':'−')+'€'+fmt(Math.abs(v));
const g    = id => document.getElementById(id);
const sv   = (id,v) => {{ const e=g(id); if(e) e.textContent=v; }};
const cls  = v => v===null||v===undefined?'neu':v>=0?'pos':'neg';

sv('kv','€'+fmt(PORT.total_val));
sv('kpnl',fmtE(PORT.total_pnl)); g('kpnl').className='val '+cls(PORT.total_pnl);
sv('kpnl-sub',fp(PORT.pnl_pct)+' sobre coste');
if(PORT.ytd!==null){{sv('kytd',fp(PORT.ytd));g('kytd').className='val '+cls(PORT.ytd);}}
else{{sv('kytd','—');}}
if(PORT.mtd!==null){{sv('kmtd',fp(PORT.mtd));g('kmtd').className='val '+cls(PORT.mtd);}}
else{{sv('kmtd','—');}}
sv('kanual',fp(PORT.cagr)); g('kanual').className='val '+cls(PORT.cagr);

const totalCost = POS.reduce((s,p)=>s+p.cost_eur,0);
const totalVal  = POS.filter(p=>p.ok).reduce((s,p)=>s+(p.val_eur||0),0);

const sortedPie = [...POS].sort((a,b)=>b.cost_eur-a.cost_eur);
const pieData   = sortedPie.map(p=>+(p.cost_eur/totalCost*100).toFixed(1));
const pieColors = sortedPie.map(p=>p.color);
new Chart(g('pieC'),{{type:'doughnut',
  data:{{labels:sortedPie.map(p=>p.name.split(' ').slice(0,2).join(' ')),
         datasets:[{{data:pieData,backgroundColor:pieColors,borderWidth:0,hoverOffset:5}}]}},
  options:{{responsive:true,maintainAspectRatio:false,cutout:'60%',
    plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>` ${{c.label}}: ${{c.parsed.toFixed(1)}}%`}}}}}}}}
}});
g('pieLeg').innerHTML=sortedPie.map((p,i)=>
  `<span><span class="ldot" style="background:${{pieColors[i]}}"></span>${{p.name.split(' ').slice(0,2).join(' ')}} ${{pieData[i]}}%</span>`
).join('');

const wpnl=POS.filter(p=>p.ok&&p.pnl_eur!==undefined).sort((a,b)=>b.pnl_eur-a.pnl_eur);
const pnlH=Math.max(260,wpnl.length*26+50);
g('pnlWrap').style.height=pnlH+'px';
g('pnlWrap').innerHTML='<canvas id="pnlC" role="img" aria-label="P&L por posición"></canvas>';
new Chart(g('pnlC'),{{type:'bar',
  data:{{labels:wpnl.map(p=>p.name.split(' ').slice(0,2).join(' ')),
         datasets:[{{data:wpnl.map(p=>+p.pnl_eur.toFixed(2)),
           backgroundColor:wpnl.map(p=>p.pnl_eur>=0?'rgba(52,211,153,.75)':'rgba(248,113,113,.75)'),
           borderRadius:3,borderWidth:0}}]}},
  options:{{indexAxis:'y',responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>`${{c.parsed.x>=0?'+':''}}€${{fmt(c.parsed.x)}}`}}}}}},
    scales:{{
      x:{{grid:{{color:'rgba(255,255,255,.05)'}},ticks:{{color:'#6b7585',font:{{size:10}},callback:v=>'€'+fmt(v)}}}},
      y:{{grid:{{display:false}},ticks:{{color:'#9ca3af',font:{{size:11}}}}}}
    }}}}
}});

const spYtd=BENCH[0]?.ytd, msciYtd=BENCH[1]?.ytd;
const bars=[
  {{l:'Mi cartera · total desde inicio',v:PORT.pnl_pct,c:'#4f8ef7'}},
  {{l:'Mi cartera · CAGR anualizada',v:PORT.cagr,c:'#a78bfa'}},
  ...(PORT.ytd!==null?[{{l:'Mi cartera · YTD',v:PORT.ytd,c:'#2dd4bf'}}]:[]),
  ...(spYtd!==null?[{{l:'S&P 500 (SPY) · YTD',v:spYtd,c:'#fbbf24'}}]:[]),
  ...(msciYtd!==null?[{{l:'MSCI World (URTH) · YTD',v:msciYtd,c:'#34d399'}}]:[]),
];
const maxV=Math.max(...bars.map(b=>Math.abs(b.v)),1);
g('compBars').innerHTML=bars.map(b=>`
  <div>
    <div class="bar-hdr">
      <span class="bar-name">${{b.l}}</span>
      <span class="bar-val" style="color:${{b.v>=0?'var(--green)':'var(--red)'}}">${{fp(b.v)}}</span>
    </div>
    <div class="bar-track"><div class="bar-fill" style="width:${{Math.max(Math.abs(b.v)/maxV*100,2)}}%;background:${{b.c}}"></div></div>
  </div>`).join('');

g('benchGrid').innerHTML=[
  ...BENCH.map(b=>{{
    const yc=b.ytd>=0?'var(--green)':'var(--red)';
    const mc=b.mtd>=0?'var(--green)':'var(--red)';
    return `<div class="bench-item">
      <div class="bn">${{b.name}} (${{b.ticker}})</div>
      <div class="bv neu">${{b.price?'$'+fmt(b.price,2):'—'}}</div>
      <div class="bs">
        <span style="color:${{yc}}">YTD: ${{b.ytd!==null?fp(b.ytd):'—'}}</span>
        <span style="color:${{mc}}">MTD: ${{b.mtd!==null?fp(b.mtd):'—'}}</span>
      </div></div>`;
  }}),
  `<div class="bench-item"><div class="bn">Total depositado</div><div class="bv neu">€${{fmt(PORT.deposited)}}</div><div class="bs"><span>DEGIRO</span></div></div>`,
  `<div class="bench-item"><div class="bn">Valor cartera DEGIRO</div><div class="bv neu">€6.467,77</div><div class="bs"><span>a 22/05/2026</span></div></div>`,
].join('');

const sorted=[...POS].sort((a,b)=>b.cost_eur-a.cost_eur);
g('posBody').innerHTML=sorted.map((p,i)=>{{
  const hp=p.ok&&p.val_eur!==undefined;
  const w=hp&&totalVal>0?p.val_eur/totalVal*100:p.cost_eur/totalCost*100;
  const pc=hp?(p.pnl_eur>=0?'pos':'neg'):'';
  return `<tr>
    <td><div class="pname">${{p.name}}</div><div class="ptick">${{p.ticker}}</div></td>
    <td><span class="badge">${{p.cur}}</span></td>
    <td class="mono" style="color:var(--muted)">${{p.qty}}</td>
    <td class="mono">€${{fmt(p.cost_eur/p.qty,2)}}</td>
    <td class="mono">${{hp?'€'+fmt(p.price_eur,2):'<span style="color:var(--muted)">—</span>'}}</td>
    <td class="mono">${{hp?'€'+fmt(p.val_eur):'—'}}</td>
    <td class="mono ${{pc}}" style="font-weight:600">${{hp?fmtE(p.pnl_eur):'—'}}</td>
    <td class="mono ${{pc}}">${{hp?fp(p.pnl_pct):'—'}}</td>
    <td><div class="wb">
      <span style="font-size:11px;color:var(--muted)">${{w.toFixed(1)}}%</span>
      <div class="wbar" style="width:${{Math.max(w*2.2,2)}}px;background:${{p.color}}"></div>
    </div></td>
  </tr>`;
}}).join('');
</script>
</body>
</html>"""

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio_dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    try:
        import yfinance
    except ImportError:
        print("❌ Ejecuta: pip install yfinance"); exit(1)
    main()
