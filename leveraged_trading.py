"""Shared paper/backtest math for linear isolated-margin USDT perpetuals.

Base-asset units, constant user-assumed funding and maintenance margin. This is
an explicit simulation model, not the OKX tiered liquidation/order engine.
"""
import math
from technical_tools import PRESETS, combined_decision
from user_data import numeric


def options(body):
    market=body.get('market','spot');direction=body.get('direction','both')
    if market not in ('spot','perpetual') or direction not in ('both','long','short'):
        raise ValueError('Rynek: spot/perpetual; kierunek: both/long/short.')
    leverage=numeric(body.get('leverage',2 if market=='perpetual' else 1),1,10)
    if market=='spot' and leverage!=1:raise ValueError('Dźwignia wymaga rynku futures perpetual.')
    return {'market':market,'leverage':leverage,'direction':direction,
            'maintenance_margin':numeric(body.get('maintenance_margin',.5),.1,5),
            'funding_bps':numeric(body.get('funding_bps',1),-100,100)}


def signal(bar,ind,cfg):
    preset=PRESETS[cfg['preset']];d=combined_decision(bar,ind,preset['tools'],preset['strategy'])
    if cfg['market']=='spot':return {**d,'action':{'BUY':'LONG','SELL':'CLOSE','WAIT':'WAIT'}[d['action']]}
    checks=d['checks'];groups={g:[c for c in checks if c['group']==g] for g in ('trend','momentum','volume','regime','context')}
    def aligned(group,state):return bool(groups[group]) and all(c['state']==state for c in groups[group])
    setup=aligned('trend','bear') if preset['strategy']=='trend' else any(c['id']=='bollinger' and c['state']=='bear' for c in checks)
    context=[c for c in groups['context'] if c['id']!='fibonacci' and not (preset['strategy']=='range' and c['id']=='bollinger')]
    short=(not d['missingGroups'] and not d['unavailableTools'] and setup and aligned('momentum','bear') and aligned('volume','bear')
           and aligned('regime','bull') and all(c['state']=='bear' for c in context) and ind.get('atr') is not None and 0<ind['atr']/bar['close']<=.08)
    action='LONG' if d['action']=='BUY' else 'SHORT' if short else 'WAIT'
    # Direction restrictions apply to entries; opposite signals still close a position.
    return {**d,'action':action,'reason':{'LONG':'Zgodność grup dla pozycji long.','SHORT':'Zgodność grup dla pozycji short.','WAIT':'Brak pełnej zgodności grup dla wejścia futures.'}[action]}


def liquidation_price(p,cfg):
    reserve=cfg['maintenance_margin']/100+cfg['costs']/10000
    collateral=p['margin']-p.get('funding',0)
    side=p['side']
    return max(0,(p['entry']-side*collateral/p['units'])/(1-side*reserve))


def plan(cfg,cash,equity,entry,atr,side,now=0):
    if side not in (1,-1) or not all(math.isfinite(v) and v>0 for v in (cash,equity,entry,atr)):return None
    fee=cfg['costs']/10000;slip=cfg['slippage']/10000
    stop=entry-side*2*atr;target=entry+side*3*atr
    if min(stop,target)<=0:return None
    stop_fill=stop*(1-side*slip)
    per_unit=side*(entry-stop_fill)+(entry+stop_fill)*fee
    leverage=cfg['leverage'] if cfg['market']=='perpetual' else 1
    units=min(equity*cfg['risk']/100/per_unit,cash/(entry*(1/leverage+fee)),equity*cfg['max_exposure']/100*leverage/entry)
    if not math.isfinite(units) or units<=0:return None
    result={'entry':entry,'units':units,'side':side,'direction':'LONG' if side==1 else 'SHORT','stop':stop,'target':target,
            'notional':units*entry,'margin':units*entry/leverage,'entryFee':units*entry*fee,'funding':0.,
            'leverage':leverage,'riskBudget':equity*cfg['risk']/100,'estimatedStopLoss':per_unit*units,'lastFundingAt':now}
    result['liquidationPrice']=liquidation_price(result,cfg) if cfg['market']=='perpetual' else None
    if cfg['market']=='perpetual' and side*(stop_fill-result['liquidationPrice'])<=0:return None
    return result


def funding(p,mark,now,cfg):
    if cfg['market']!='perpetual':return
    periods=max(0,int(now//28800)-int(p['lastFundingAt']//28800))
    p['funding']+=periods*p['side']*p['units']*mark*cfg['funding_bps']/10000
    p['lastFundingAt']=max(p['lastFundingAt'],now)
    p['liquidationPrice']=liquidation_price(p,cfg)


def liquidated(p,mark,cfg):
    return cfg['market']=='perpetual' and p['side']*(mark-liquidation_price(p,cfg))<=0


def settlement(p,fill,cfg,liquidation=False):
    exit_fee=p['units']*fill*cfg['costs']/10000
    gross=p['side']*p['units']*(fill-p['entry'])
    credit=0. if liquidation else max(0.,p['margin']+gross-exit_fee-p.get('funding',0))
    return {'credit':credit,'pnl':credit-p['margin']-p['entryFee'],'grossPnl':gross,'exitFee':exit_fee,
            'funding':p.get('funding',0),'liquidated':liquidation,
            'liquidationAdjustment':credit-p['margin']-gross+exit_fee+p.get('funding',0)}


def value(cash,p,mark,cfg):
    if not p:return cash
    fill=mark*(1-p['side']*cfg['slippage']/10000)
    return cash+settlement(p,fill,cfg)['credit']
