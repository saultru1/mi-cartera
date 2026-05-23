#!/usr/bin/env python3
"""
Dashboard de cartera DEGIRO - Saúl Trujillo
Datos: historial completo PDF DEGIRO 24/05/2022 - 23/05/2026
Uso: pip install yfinance && python portfolio_update.py
"""

import yfinance as yf
import json, os
from datetime import datetime, date

# ─────────────────────────────────────────────────────────
#  POSICIONES ABIERTAS  (calculadas del historial DEGIRO)
#  cost_eur = coste total EUR incl. comisiones y FX
# ─────────────────────────────────────────────────────────
POSITIONS = [
    # (nombre, ticker yfinance, qty, cost_eur, divisa, primera_compra)
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
    ("Euronet Worldwide Inc",    "EEFT",      3,    205.82, "USD", "2025-10-28"),
    ("Alphabet Inc Class A",     "GOOGL",     2,    205.23, "USD", "2022-09-23"),
    ("ADR on Novo Nordisk A/S",  "NVO",       6,    202.90, "USD", "2026-03-16"),
    ("Brown-Forman Corp Class B","BF-B",      3,     91.59, "USD", "2025-02-07"),
]

BENCHMARKS  = [("S&P 500", "SPY"), ("MSCI World", "URTH")]
TOTAL_DEPOSITED = 8099.0
START_DATE  = date(2022, 7, 25)
FX_TICKERS  = {"USD":"EURUSD=X","GBP":"EURGBP=X","DKK":"EURDKK=X","SEK":"EURSEK=X"}
COLORS = ["#4f8ef7","#34d399","#a78bfa","#fbbf24","#f87171","#2dd4bf","#fb923c",
          "#c084fc","#86efac","#67e8f9","#fda4af","#a3e635","#fdba74","#7dd3fc",
          "#d8b4fe","#6ee7b7"]


def fetch_fx():
    fx = {"EUR": 1.0}
    print("  FX rates...", end=" ", flush=True)
    for cur, tkr in FX_TICKERS.items():
        try:
            h = yf.Ticker(tkr).history(period="2d")
            if not h.empty:
                fx[cur] = 1.0 / float(h["Close"].iloc[-1])
        except: pass
    fx["GBX"] = fx.get("GBP", 0.01175) / 100
    print(f"OK (1 USD ≈ {fx.get('USD',0.92):.4f} EUR)")
    return fx


def fetch_ticker(tkr):
    h = yf.Ticker(tkr).history(period="6mo")
    if h.empty: return None, None, None
    price = float(h["Close"].iloc[-1])
    now = datetime.now()
    def first(df, d):
        m = df[df.index.date >= d]
        return float(m["Close"].iloc[0]) if not m.empty else None
    return price, first(h, date(now.year,1,1)), first(h, date(now.year,now.month,1))


def main():
    print("\n🔄 Yahoo Finance → portfolio_dashboard.html\n")
    fx = fetch_fx()
    total_cost = sum(p[3] for p in POSITIONS)
    pos_data = []

    for i, (name, tkr, qty, cost_eur, cur, buy_date) in enumerate(POSITIONS):
        print(f"  [{i+1:02d}/{len(POSITIONS)}] {name[:28]}...", end=" ", flush=True)
        try:
            price, ytd_p, mtd_p = fetch_ticker(tkr)
            if not price: raise ValueError("sin datos")
            fxr = fx.get(cur, 1.0)
            p_eur = price * fxr
            v_eur = p_eur * qty
            pnl   = v_eur - cost_eur
            pnl_p = pnl / cost_eur * 100
            ytd_r = (price-ytd_p)/ytd_p*100 if ytd_p else None
            mtd_r = (price-mtd_p)/mtd_p*100 if mtd_p else None
            pos_data.append({"name":name,"ticker":tkr,"qty":qty,"cost_eur":cost_eur,
                "cur":cur,"buy_date":buy_date,"price":price,"price_eur":p_eur,
                "val_eur":v_eur,"pnl_eur":pnl,"pnl_pct":pnl_p,
                "ytd_ret":ytd_r,"mtd_ret":mtd_r,"ok":True,"color":COLORS[i%len(COLORS)]})
            print(f"€{p_eur:.2f}  {pnl_p:+.1f}%")
        except Exception as e:
            print(f"ERROR: {e}")
            pos_data.append({"name":name,"ticker":tkr,"qty":qty,"cost_eur":cost_eur,
                "cur":cur,"buy_date":buy_date,"ok":False,"color":COLORS[i%len(COLORS)]})

    print("\n  Benchmarks...")
    bench_data = []
    now = datetime.now()
    for bname, btkr in BENCHMARKS:
        try:
            price, ytd_p, mtd_p = fetch_ticker(btkr)
            ytd_r = (price-ytd_p)/ytd_p*100 if (price and ytd_p) else None
            mtd_r = (price-mtd_p)/mtd_p*100 if (price and mtd_p) else None
            bench_data.append({"name":bname,"ticker":btkr,"price":price,"ytd":ytd_r,"mtd":mtd_r})
            print(f"    {bname}: ${price:.2f}  YTD:{ytd_r:+.1f}%" if ytd_r else f"    {bname}: ${price:.2f}")
        except Exception as e:
            print(f"    {bname}: ERROR {e}")
            bench_data.append({"name":bname,"ticker":btkr,"price":None,"ytd":None,"mtd":None})

    valid    = [p for p in pos_data if p.get("ok")]
    total_v  = sum(p["val_eur"] for p in valid)
    total_pnl = total_v - total_cost
    pnl_pct   = total_pnl/total_cost*100 if total_cost else 0
    years     = (date.today()-START_DATE).days/365.25
    cagr      = ((1+pnl_pct/100)**(1/years)-1)*100 if years>0 else 0

    yn=yd=mn=md=0.0
    for p in valid:
        bd=date.fromisoformat(p["buy_date"])
        ys=date(now.year,1,1); ms=date(now.year,now.month,1)
        if p.get("ytd_ret") is not None and bd<ys: yn+=p["ytd_ret"]*p["cost_eur"]; yd+=p["cost_eur"]
        if p.get("mtd_ret") is not None and bd<ms: mn+=p["mtd_ret"]*p["cost_eur"]; md+=p["cost_eur"]

    portfolio = {"total_val":total_v,"total_cost":total_cost,"total_pnl":total_pnl,
        "pnl_pct":pnl_pct,"cagr":cagr,"ytd":yn/yd if yd>0 else None,
        "mtd":mn/md if md>0 else None,"updated":now.strftime("%d/%m/%Y %H:%M"),
        "deposited":TOTAL_DEPOSITED}

    generate_html(pos_data, bench_data, portfolio)

    print(f"\n✅  portfolio_dashboard.html generado")
    print(f"    Valor  : €{total_v:,.0f}  (DEGIRO: €6.467)")
    print(f"    P&L    : €{total_pnl:+,.0f}  ({pnl_pct:+.1f}%)")
    print(f"    CAGR   : {cagr:+.1f}%")
    if portfolio["ytd"]: print(f"    YTD    : {portfolio['ytd']:+.1f}%")
    if portfolio["mtd"]: print(f"    MTD    : {portfolio['mtd']:+.1f}%")


def generate_html(pos_data, bench_data, portfolio):
    pj = json.dumps(pos_data, ensure_ascii=False)
    bj = json.dumps(bench_data, ensure_ascii=False)
    oj = json.dumps(portfolio, ensure_ascii=False)
    n  = len(pos_data)
    upd = portfolio['updated']

    html = f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Mi Cartera · {upd}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
:root{{--bg:#0e1117;--bg2:#161b27;--bg3:#1e2535;--bg4:#252d40;--bd:rgba(255,255,255,.07);--tx:#dde1ea;--mu:#6b7585;--bl:#4f8ef7;--gr:#34d399;--rd:#f87171;--am:#fbbf24;--fn:'Inter',system-ui,sans-serif;--mo:'JetBrains Mono','Fira Mono',monospace;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
html{{background:var(--bg);color:var(--tx);font-family:var(--fn);font-size:14px;}}
body{{min-height:100vh;padding:28px 32px;max-width:1380px;margin:0 auto;}}
.hdr{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px;flex-wrap:wrap;gap:12px;}}
.hdr h1{{font-size:20px;font-weight:600;letter-spacing:-.5px;color:#fff;}}
.hdr p{{color:var(--mu);font-size:12px;margin-top:4px;}}
.ts{{font-size:11px;color:var(--mu);text-align:right;line-height:1.8;}}
.ok{{display:inline-block;background:rgba(52,211,153,.15);color:var(--gr);border-radius:4px;padding:2px 8px;font-size:11px;font-weight:500;}}
.kpi-row{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:16px;}}
.kpi{{background:var(--bg2);border:1px solid var(--bd);border-radius:10px;padding:14px 16px;}}
.kpi .lb{{font-size:10px;color:var(--mu);text-transform:uppercase;letter-spacing:.6px;margin-bottom:8px;}}
.kpi .vl{{font-size:22px;font-weight:700;font-family:var(--mo);letter-spacing:-1px;line-height:1;}}
.kpi .sb{{font-size:11px;color:var(--mu);margin-top:6px;}}
.pos{{color:var(--gr);}}.neg{{color:var(--rd);}}.neu{{color:var(--tx);}}
.cr{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;}}
.cd{{background:var(--bg2);border:1px solid var(--bd);border-radius:12px;padding:20px;}}
.ct{{font-size:13px;font-weight:600;color:var(--tx);margin-bottom:14px;}}
.cs{{font-size:11px;color:var(--mu);font-weight:400;margin-left:6px;}}
.pr{{display:grid;grid-template-columns:3fr 2fr;gap:14px;margin-bottom:14px;}}
.cb{{display:flex;flex-direction:column;gap:12px;}}
.bh{{display:flex;justify-content:space-between;font-size:12px;margin-bottom:5px;}}
.bn{{color:var(--mu);}}.bv{{font-weight:600;font-family:var(--mo);}}
.bt{{height:7px;background:var(--bg4);border-radius:4px;overflow:hidden;}}
.bf{{height:100%;border-radius:4px;}}
.bg{{display:grid;grid-template-columns:1fr 1fr;gap:8px;}}
.bi{{background:var(--bg3);border-radius:8px;padding:12px 14px;}}
.bi .bn{{font-size:11px;color:var(--mu);margin-bottom:5px;font-weight:500;}}
.bi .bv{{font-size:17px;font-weight:700;font-family:var(--mo);}}
.bi .bs{{font-size:11px;color:var(--mu);margin-top:4px;display:flex;gap:10px;flex-wrap:wrap;}}
.pl{{display:flex;flex-wrap:wrap;gap:8px 14px;margin-top:12px;font-size:11px;color:var(--mu);}}
.pl span{{display:flex;align-items:center;gap:5px;}}
.ld{{width:8px;height:8px;border-radius:2px;flex-shrink:0;}}
.pc{{background:var(--bg2);border:1px solid var(--bd);border-radius:12px;padding:20px;margin-bottom:16px;}}
.pt{{font-size:13px;font-weight:600;margin-bottom:16px;display:flex;justify-content:space-between;}}
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
  <div><h1>📊 Mi Cartera · DEGIRO</h1><p>Yahoo Finance · <span class="ok">✓ {upd}</span></p></div>
  <div class="ts">Actualizado<br><strong style="color:var(--tx)">{upd}</strong><br><small>Ejecuta portfolio_update.py</small></div>
</div>
<div class="kpi-row">
  <div class="kpi"><div class="lb">Valor cartera</div><div class="vl neu" id="kv">—</div><div class="sb">precios actuales</div></div>
  <div class="kpi"><div class="lb">P&L Total</div><div class="vl" id="kp">—</div><div class="sb" id="ks">desde inicio</div></div>
  <div class="kpi"><div class="lb">Rentab. YTD</div><div class="vl" id="ky">—</div><div class="sb">año en curso</div></div>
  <div class="kpi"><div class="lb">Rentab. MTD</div><div class="vl" id="km">—</div><div class="sb" id="kms">mes en curso</div></div>
  <div class="kpi"><div class="lb">Anualizada</div><div class="vl" id="ka">—</div><div class="sb">CAGR desde jul 2022</div></div>
</div>
<div class="cr">
  <div class="cd"><div class="ct">Peso por posición <span class="cs">% coste adquisición</span></div>
    <div style="position:relative;height:260px;"><canvas id="pieC"></canvas></div>
    <div class="pl" id="pieLeg"></div></div>
  <div class="cd"><div class="ct">P&L por posición <span class="cs">€ ganancia / pérdida</span></div>
    <div id="pnlW" style="position:relative;height:260px;"><canvas id="pnlC"></canvas></div></div>
</div>
<div class="pr">
  <div class="cd"><div class="ct">Rentabilidades comparadas</div><div class="cb" id="compB"></div></div>
  <div class="cd"><div class="ct">Benchmarks · tiempo real</div>
    <div class="bg">
      <div class="bi"><div class="bn">S&P 500 (SPY)</div><div class="bv neu" id="bsp">—</div><div class="bs"><span id="bspy">YTD: —</span><span id="bspm">MTD: —</span></div></div>
      <div class="bi"><div class="bn">MSCI World (URTH)</div><div class="bv neu" id="bms">—</div><div class="bs"><span id="bmsy">YTD: —</span><span id="bmsm">MTD: —</span></div></div>
      <div class="bi"><div class="bn">Total depositado</div><div class="bv neu">€8.099</div><div class="bs"><span>25/07/2022 → hoy</span></div></div>
      <div class="bi"><div class="bn">Valor DEGIRO actual</div><div class="bv neu">€6.467,77</div><div class="bs"><span>a 22/05/2026</span></div></div>
    </div></div>
</div>
<div class="pc">
  <div class="pt">Posiciones abiertas · {n} valores <span class="ph">Yahoo Finance · python portfolio_update.py para actualizar</span></div>
  <table><thead><tr><th>Compañía</th><th>Div.</th><th>Acc.</th><th>Coste medio (€)</th><th>Precio actual (€)</th><th>Valor (€)</th><th>P&amp;L (€)</th><th>P&amp;L %</th><th>Peso</th></tr></thead>
  <tbody id="posB"></tbody></table>
</div>
<div class="ft">Datos: <strong>Yahoo Finance (yfinance)</strong> · Script: portfolio_update.py · {upd}</div>
<script>
const POS={pj},BENCH={bj},PORT={oj};
const fmt=(n,d=0)=>(+n).toLocaleString('es-ES',{{minimumFractionDigits:d,maximumFractionDigits:d}});
const fp=v=>(v>=0?'+':'')+v.toFixed(1)+'%';
const fE=v=>(v>=0?'':'−')+'€'+fmt(Math.abs(v));
const g=id=>document.getElementById(id);
const sv=(id,v)=>{{const e=g(id);if(e)e.textContent=v;}};
const cl=v=>v===null||v===undefined?'neu':v>=0?'pos':'neg';

sv('kv','€'+fmt(PORT.total_val));
sv('kp',fE(PORT.total_pnl));g('kp').className='vl '+cl(PORT.total_pnl);
sv('ks',fp(PORT.pnl_pct)+' s/ coste');
if(PORT.ytd!==null){{sv('ky',fp(PORT.ytd));g('ky').className='vl '+cl(PORT.ytd);}}
if(PORT.mtd!==null){{sv('km',fp(PORT.mtd));g('km').className='vl '+cl(PORT.mtd);}}
sv('ka',fp(PORT.cagr));g('ka').className='vl '+cl(PORT.cagr);

const TC=POS.reduce((s,p)=>s+p.cost_eur,0);
const TV=POS.filter(p=>p.ok).reduce((s,p)=>s+(p.val_eur||0),0);
const sP=[...POS].sort((a,b)=>b.cost_eur-a.cost_eur);
const pD=sP.map(p=>+(p.cost_eur/TC*100).toFixed(1));
const pC=sP.map(p=>p.color);
new Chart(g('pieC'),{{type:'doughnut',
  data:{{labels:sP.map(p=>p.name.split(' ').slice(0,2).join(' ')),datasets:[{{data:pD,backgroundColor:pC,borderWidth:0,hoverOffset:5}}]}},
  options:{{responsive:true,maintainAspectRatio:false,cutout:'60%',plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>` ${{c.label}}: ${{c.parsed.toFixed(1)}}%`}}}}}}}}
}});
g('pieLeg').innerHTML=sP.map((p,i)=>`<span><span class="ld" style="background:${{pC[i]}}"></span>${{p.name.split(' ').slice(0,2).join(' ')}} ${{pD[i]}}%</span>`).join('');

const wp=POS.filter(p=>p.ok&&p.pnl_eur!==undefined).sort((a,b)=>b.pnl_eur-a.pnl_eur);
const ph=Math.max(260,wp.length*26+50);
g('pnlW').style.height=ph+'px';
g('pnlW').innerHTML='<canvas id="pnlC"></canvas>';
new Chart(g('pnlC'),{{type:'bar',
  data:{{labels:wp.map(p=>p.name.split(' ').slice(0,2).join(' ')),datasets:[{{data:wp.map(p=>+p.pnl_eur.toFixed(2)),backgroundColor:wp.map(p=>p.pnl_eur>=0?'rgba(52,211,153,.75)':'rgba(248,113,113,.75)'),borderRadius:3,borderWidth:0}}]}},
  options:{{indexAxis:'y',responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>`${{c.parsed.x>=0?'+':''}}€${{fmt(c.parsed.x)}}`}}}}}},
    scales:{{x:{{grid:{{color:'rgba(255,255,255,.05)'}},ticks:{{color:'#6b7585',font:{{size:10}},callback:v=>'€'+fmt(v)}}}},y:{{grid:{{display:false}},ticks:{{color:'#9ca3af',font:{{size:11}}}}}}}}}}
}});

const spY=BENCH[0]?.ytd,msY=BENCH[1]?.ytd;
const bars=[
  {{l:'Mi cartera · total desde inicio',v:PORT.pnl_pct,c:'#4f8ef7'}},
  {{l:'Mi cartera · CAGR anualizada',v:PORT.cagr,c:'#a78bfa'}},
  ...(PORT.ytd!==null?[{{l:'Mi cartera · YTD',v:PORT.ytd,c:'#2dd4bf'}}]:[]),
  ...(spY!==null?[{{l:'S&P 500 · YTD',v:spY,c:'#fbbf24'}}]:[]),
  ...(msY!==null?[{{l:'MSCI World · YTD',v:msY,c:'#34d399'}}]:[]),
];
const mx=Math.max(...bars.map(b=>Math.abs(b.v)),1);
g('compB').innerHTML=bars.map(b=>`<div><div class="bh"><span class="bn">${{b.l}}</span><span class="bv" style="color:${{b.v>=0?'var(--gr)':'var(--rd)'}}">${{fp(b.v)}}</span></div><div class="bt"><div class="bf" style="width:${{Math.max(Math.abs(b.v)/mx*100,2)}}%;background:${{b.c}}"></div></div></div>`).join('');

const B=BENCH;
if(B[0]?.price){{sv('bsp','$'+fmt(B[0].price,2));}}
if(B[1]?.price){{sv('bms','$'+fmt(B[1].price,2));}}
if(B[0]?.ytd!==null){{sv('bspy','YTD: '+fp(B[0].ytd));g('bspy').style.color=B[0].ytd>=0?'var(--gr)':'var(--rd)';}}
if(B[0]?.mtd!==null){{sv('bspm','MTD: '+fp(B[0].mtd));g('bspm').style.color=B[0].mtd>=0?'var(--gr)':'var(--rd)';}}
if(B[1]?.ytd!==null){{sv('bmsy','YTD: '+fp(B[1].ytd));g('bmsy').style.color=B[1].ytd>=0?'var(--gr)':'var(--rd)';}}
if(B[1]?.mtd!==null){{sv('bmsm','MTD: '+fp(B[1].mtd));g('bmsm').style.color=B[1].mtd>=0?'var(--gr)':'var(--rd)';}}

const sr=[...POS].sort((a,b)=>b.cost_eur-a.cost_eur);
g('posB').innerHTML=sr.map((p,i)=>{{
  const hp=p.ok&&p.val_eur!==undefined;
  const w=hp&&TV>0?p.val_eur/TV*100:p.cost_eur/TC*100;
  const pc=hp?(p.pnl_eur>=0?'pos':'neg'):'';
  return `<tr>
    <td><div class="pn">${{p.name}}</div><div class="pk">${{p.ticker}}</div></td>
    <td><span class="badge">${{p.cur}}</span></td>
    <td class="mo" style="color:var(--mu)">${{p.qty}}</td>
    <td class="mo">€${{fmt(p.cost_eur/p.qty,2)}}</td>
    <td class="mo">${{hp?'€'+fmt(p.price_eur,2):'<span style="color:var(--mu)">—</span>'}}</td>
    <td class="mo">${{hp?'€'+fmt(p.val_eur):'—'}}</td>
    <td class="mo ${{pc}}" style="font-weight:600">${{hp?fE(p.pnl_eur):'—'}}</td>
    <td class="mo ${{pc}}">${{hp?fp(p.pnl_pct):'—'}}</td>
    <td><div class="wb"><span style="font-size:11px;color:var(--mu)">${{w.toFixed(1)}}%</span><div class="wbar" style="width:${{Math.max(w*2.2,2)}}px;background:${{p.color}}"></div></div></td>
  </tr>`;
}}).join('');
</script></body></html>"""

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio_dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    try: import yfinance
    except ImportError: print("❌ pip install yfinance"); exit(1)
    main()
