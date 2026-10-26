#!/usr/bin/env python3
"""MPD Radar: solo publica puntuaciones amplias, nunca cotizaciones de API."""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
SYMBOLS=['XLK','SMH','XLV','XLI','XLE','XLF','XLY','XLP','XLU','HACK']
ALL=SYMBOLS+['SPY']
OUT=Path('site/radar-data.json')

def api_quote(symbol, key):
    url='https://api.twelvedata.com/quote?'+urlencode({'symbol':symbol,'apikey':key})
    with urlopen(Request(url,headers={'User-Agent':'MPD-Radar/2.0'}),timeout=22) as r:
        item=json.load(r)
    if 'code' in item or 'error' in item or item.get('status')=='error':
        raise RuntimeError(str(item.get('message',item))[:160])
    return item

def change(item):
    # Diferencias de nombres entre respuestas/versiones de la API.
    try:
        p=item.get('percent_change')
        if p is not None and str(p).strip()!='': return float(str(p).replace('%',''))
        price=float(item.get('close') or item.get('price'))
        prev=float(item['previous_close'])
        return (price/prev-1)*100 if prev>0 else None
    except (ValueError,TypeError,KeyError,ZeroDivisionError): return None

def score(x, scale=1):
    return max(1,min(10,round(5+float(x)*scale))) if x is not None else None

def main():
    key=os.getenv('TWELVE_DATA_API_KEY','').strip()
    if not key:
        print('FALTA SECRETO TWELVE_DATA_API_KEY: no se publican datos simulados',file=sys.stderr)
        sys.exit(2)
    responses={}
    # Basic: 8 créditos/minuto. Usamos hasta 7 y esperamos 65 segundos.
    for i,symbol in enumerate(ALL):
        if i==7:
            print('Esperando 65 s para respetar el límite del plan Basic',flush=True)
            time.sleep(65)
        try:
            responses[symbol]=change(api_quote(symbol,key))
            print(symbol,'OK' if responses[symbol] is not None else 'Sin cambio válido',flush=True)
        except Exception as exc:
            print(f'{symbol}: ERROR {exc}',file=sys.stderr,flush=True)
            responses[symbol]=None
        time.sleep(0.45)
    spy=responses['SPY']
    assets=[]
    for symbol in SYMBOLS:
        v=responses[symbol]
        relative=score(v-spy,1.8) if v is not None and spy is not None else None
        assets.append({'symbol':symbol,'momentum_score':score(v,1.25),'relative_score':relative,
                       'status':'Dato diario recibido' if relative is not None else 'Dato no disponible'})
    payload={'schema':1,'source':'Twelve Data','generated_at':datetime.now(timezone.utc).isoformat(),
             'comparison':'SPY','disclaimer':'Puntuaciones diarias derivadas; no son señales de compra',
             'assets':assets}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Resultado: ',len([a for a in assets if a['relative_score'] is not None]),'ETF calculados.')

if __name__=='__main__':main()
