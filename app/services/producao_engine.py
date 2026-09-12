import polars as pl
from datetime import datetime
from app.services import config_store as store
from app.services.carteira_engine import clean_name, col, load_carteira_combined, load_source, natural_key, text_expr

def _number(frame,name):return pl.col(name).cast(pl.Float64,strict=False).fill_null(0)

def _date_key(value):
    text=str(value or '').strip()
    for pattern in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y','%Y/%m/%d'):
        try:return (0,datetime.strptime(text[:10],pattern))
        except ValueError:pass
    return (1,text)

def build(filters=None):
    filters=filters or {};carteira,source,_,_=load_carteira_combined();onda,_,_=load_source('Onda')
    cd_onda=col(carteira,'CD_ONDA');onda_key=col(onda,'CD_ONDA');onda_name=col(onda,'DS_ONDA','DS_ONDA_VARCHAR2')
    produto=col(carteira,'QT_PRODUTO');cancelado=col(carteira,'QT_CANCELADO','QT_CANCELADA');separado=col(carteira,'QT_SEPARADO');pendente=col(carteira,'QTD_PENDENTE')
    classe=col(carteira,'CD_CLASSE','CLASSE');data_oficial=col(carteira,'DATA_OFICIAL','DATA OFICIAL');empresa=col(carteira,'CD_EMPRESA','EMPRESA','FILIAL')
    turno=col(carteira,'CD_TURNO NUMBER','CD_TURNO')
    turno_rota=col(carteira,'TURNO ROTA CHAR','TURNO_ROTA_CHAR','ROTA_CHAR','CD_ROTA','ROTA')
    missing=[label for label,value in [('CD_ONDA',cd_onda),('QT_PRODUTO',produto),('QT_CANCELADO',cancelado),('QT_SEPARADO',separado),('QTD_PENDENTE',pendente)] if not value]
    if not onda_key or not onda_name:missing.append('Onda: CD_ONDA/DS_ONDA')
    if missing:raise ValueError('Colunas obrigatórias ausentes: '+', '.join(missing))
    key='_ONDA_KEY';label='_ONDA_LABEL'
    mapping=onda.with_columns(text_expr(onda_key).alias(key),text_expr(onda_name).alias(label)).select([key,label]).unique(key,keep='first')
    data=carteira.with_columns(text_expr(cd_onda).alias(key)).join(mapping,on=key,how='left')
    source_label=col(carteira,'DS_ONDA','DS_ONDA_VARCHAR2')
    if source_label:data=data.with_columns(pl.when(text_expr(source_label)!='').then(text_expr(source_label)).otherwise(pl.col(label).fill_null('')).alias(label))
    data=data.with_columns(pl.when(pl.col(label).fill_null('')=='').then(pl.lit('Onda não cadastrada')).otherwise(pl.col(label)).alias(label))
    data=data.filter(text_expr(cd_onda)!='')
    options={}
    for name,column in {'empresa':empresa,'classe':classe,'data':data_oficial,'turno':turno,'turno_rota':turno_rota}.items():
        sort_key=_date_key if name=='data' else natural_key
        values=sorted((v for v in data.select(text_expr(column).alias('v')).unique().get_column('v').to_list() if v),key=sort_key) if column else []
        options[name]=values;selected=filters.get(name) or []
        if isinstance(selected,str):selected=[selected]
        if selected and column:data=data.filter(text_expr(column).is_in(selected))
    fixed=sorted((v for v in mapping.get_column(label).to_list() if v),key=natural_key)
    grouped=(data.group_by(label).agg(_number(data,produto).sum().alias('produzir'),_number(data,cancelado).sum().alias('cancelado'),_number(data,separado).sum().alias('separado'),_number(data,pendente).sum().alias('pendente')))
    values={row[label]:row for row in grouped.iter_rows(named=True)};rows=[]
    for wave in list(dict.fromkeys([*fixed,*sorted(values,key=natural_key)])):
        row=values.get(wave,{});produce=round(row.get('produzir') or 0);cancel=round(row.get('cancelado') or 0);separate=round(row.get('separado') or 0);pending=round(row.get('pendente') or 0)
        completed=((separate+cancel)/produce*100) if produce>0 else 0
        rows.append({'label':wave,'produzir':produce,'cancelado':cancel,'separado':separate,'pendente':pending,'concluido':round(min(completed,100),1)})
    totals={key:sum(row[key] for row in rows) for key in ('produzir','cancelado','separado','pendente')};totals['concluido']=round(((totals['separado']+totals['cancelado'])/totals['produzir']*100) if totals['produzir'] else 0,1)
    return {'rows':rows,'totals':totals,'filters':options,'meta':{'rows':data.height,'updated_at':source.get('last_run'),'status':source.get('status') or 'IDLE','status_message':source.get('status_message') or ''}}
