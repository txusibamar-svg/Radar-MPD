#!/usr/bin/env python3
"""MPD 2.2: análisis MANUAL de 1 mar y exactamente 3 ballenas.
No publica precios, porcentajes exactos ni una recomendación automatizada.
"""
import json, os, sys, time, math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CANDIDATES={
'XLK':(['MSFT','AAPL','CRM'],['ADBE','INTC','PYPL']),
'SMH':(['NVDA','AVGO','TSM'],['AMD','INTC','GFS']),
'XLV':(['LLY','JNJ','ABBV'],['PFE','MRNA','BAX']),
'XLI':(['CAT','GE','DE'],['BA','MMM','FDX']),
'XLE':(['XOM','CVX','COP'],['SLB','HAL','OXY']),
'XLF':(['JPM','BRK.B','GS'],['C','PYPL','PGR']),
'XLY':(['AMZN','TSLA','MCD'],['NKE','SBUX','LULU']),
'XLP':(['COST','WMT','PG'],['KHC','GIS','CPB']),
'XLU':(['NEE','SO','DUK'],['AES','AEP','D']),
'HACK':(['PANW','CRWD','FTNT'],['S','RBRK','TENB'])
}

def fail(msg):
    print('ERROR:', msg, file=sys.stderr);sys.exit(2)

def daily(symbol,key):
    args={'symbol':symbol,'interval':'1day','outputsize':'85','apikey':key}
    url='https://api.twelvedata.com/time_series?'+urlencode(args)
    with urlopen(Request(url,headers={'User-Agent':'MPD-Radar/2.2'}),timeout=28) as response:
        blob=json.load(response)
    if blob.get('status')=='error' or 'code' in blob:
        raise ValueError(blob.get('message','API error'))
    rows=[]
    for p in blob.get('values',[]):
        try:
            v=float(p['close'])
            if math.isfinite(v) and v>0:rows.append((p['datetime'][:10],v))
        except (KeyError,ValueError,TypeError):pass
    rows=sorted(dict(rows).items())
    if len(rows)<68:raise ValueError('Histórico insuficiente para tres meses (mínimo 68 sesiones)')
    return dict(rows)

def ret(series,days):
    ordered=sorted(series.items());end=ordered[-1][1]
    start=ordered[-days-1][1]
    return (end/start-1)*100

def bucket(v):
    # Tramos deliberadamente amplios, no publicamos rendimientos exactos.
    return max(1,min(10,round(5+v/2.2)))

def main():
    key=os.getenv('TWELVE_DATA_API_KEY','').strip()
    if not key:fail('Falta TWELVE_DATA_API_KEY (secreto de GitHub)')
    sector=os.getenv('MAR','').upper().strip();phase=os.getenv('FASE','').strip()
    symbols=[os.getenv(f'BALLENA_{i}','').upper().strip() for i in range(1,4)]
    if sector not in CANDIDATES:fail('MAR no válido')
    if phase not in ['extendido','recuperacion']:fail('FASE debe ser extendido o recuperacion')
    leaders,laggards=CANDIDATES[sector]
    if len(set(symbols))!=3 or any(x not in leaders+laggards for x in symbols):
        fail('Selecciona tres tickers distintos de las seis candidatas del mar')
    nleader=sum(s in leaders for s in symbols)
    if nleader!=(1 if phase=='extendido' else 2):
        fail('La proporción no cumple la regla MPD 1+2 / 2+1')
    # 3 acciones + ETF del mar + SPY = 5 créditos aprox, siempre con límite inferior a 8/min.
    prices={};errors={}
    for index,sym in enumerate([sector,'SPY']+symbols):
        try:
            prices[sym]=daily(sym,key)
            print(sym,'histórico diario OK',flush=True)
        except Exception as exc:
            errors[sym]=str(exc)[:160]
            print(sym,'sin histórico:',errors[sym],flush=True)
        time.sleep(0.7)
    def scores(sym):
        if sym not in prices:return None
        if sector not in prices or 'SPY' not in prices:return None
        result={}
        for label,days in [('5d',5),('1m',21),('3m',63)]:
            # Histórico alineado por fechas con el ETF y SPY; si falta ventana -> sin evaluar.
            dates=sorted(set(prices[sym])&set(prices[sector])&set(prices['SPY']))
            if len(dates)<=days:return None
            a,b=dates[-1],dates[-days-1]
            relative=(prices[sym][a]/prices[sym][b]-prices[sector][a]/prices[sector][b])*100
            vs_spy=(prices[sym][a]/prices[sym][b]-prices['SPY'][a]/prices['SPY'][b])*100
            result[label]={'vs_mar':bucket(relative),'vs_spy':bucket(vs_spy),'tendencia':'supera al mar' if relative>0.5 else ('rezagada frente al mar' if relative<-.5 else 'similar al mar')}
        result['fecha_cotizacion']=dates[-1]
        return result
    arr=[]
    for sym in symbols:
        obj=scores(sym)
        arr.append({'symbol':sym,'rol':'líder' if sym in leaders else 'rezagada',
                    'status':'Evaluación relativa disponible' if obj else 'Histórico insuficiente o no disponible',
                    'periodos':obj or {},'BEC':None,'NRR':None,'ICP':None,'POT':None,
                    'punto_dulce':None,'veredicto':'Vigilar; requiere valoración y confirmación técnica'})
    generated=datetime.now(timezone.utc).isoformat()
    payload={'schema':2,'fecha':generated,'source':'Twelve Data',
             'mar':sector,'fase':phase,'seleccion':symbols,'ballenas':arr,
             'errores':errors,'valido':sum(bool(x['periodos']) for x in arr)==3,
             'nota':'Comparaciones publicadas como tramos orientativos; no se redistribuyen cotizaciones ni retornos exactos. No es una recomendación.'}
    Path('pesca-data.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Informe preparado:',len(arr),'ballenas; evaluaciones completas:',sum(bool(x['periodos']) for x in arr))

if __name__=='__main__':main()
