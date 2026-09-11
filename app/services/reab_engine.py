import polars as pl
from app.services import config_store as store
from app.services.carteira_engine import (AGING_SCHEMA, CLASS_SCHEMA, clean_name,
    col, load_source, load_carteira_combined, matrix_rows, natural_key, supplemental_sources, text_expr)

STORE_SOURCE_NAMES=('LOJAS','LOJA','FILIAIS','FILIAL','REAB','LOJAS_REAB','CADASTRO_LOJAS')
# NºLoja é a identidade da loja. “Filial” (1500) é apenas a filial expedidora
# e nunca pode ser usada como rótulo de todas as linhas.
STORE_NUMBER_KEYS=('N_LOJA','NLOJA','NOLOJA','NO_LOJA','NUMERO_LOJA','NUM_LOJA','NU_LOJA','CD_LOJA','COD_LOJA')
DATA_STORE_KEYS=('CD_ROTA','N_LOJA','NLOJA','NOLOJA','NO_LOJA','NUMERO_LOJA','NUM_LOJA','NU_LOJA','CD_LOJA','COD_LOJA','CD_CLIENTE','CLIENTE','CD_EMPRESA_DESTINO','CD_FILIAL_DESTINO')
COMPANY_KEYS=('CD_EMPRESA','EMPRESA','FILIAL','CD_FILIAL')
STORE_LABELS=('LOJA_COMPLETA','LOJA COMPLETA','DS_LOJA','NM_LOJA','LOJA','FILIAL_COMPLETA','DS_FILIAL')

def related_source_names():
    names={'CARTEIRA'}
    names.update(clean_name(s['name']) for s in store.list_sources() if clean_name(s['name']) in STORE_SOURCE_NAMES)
    names.update(clean_name(s['name']) for s in supplemental_sources())
    return names

def _store_dimension(carteira,empresa):
    direct=col(carteira,*STORE_LABELS)
    if direct:
        number=col(carteira,*STORE_NUMBER_KEYS)
        expression=(text_expr(number)+pl.lit(' - ')+text_expr(direct)) if number and number!=direct else text_expr(direct)
        prepared=carteira.with_columns(expression.alias('_LOJA_COMPLETA'))
        labels=sorted((v for v in prepared.select(pl.col('_LOJA_COMPLETA')).unique().get_column('_LOJA_COMPLETA').to_list() if v),key=natural_key)
        return prepared,labels,None
    source=next((s for s in store.list_sources() if clean_name(s['name']) in STORE_SOURCE_NAMES),None)
    if source:
        lojas,_,_=load_source(source['name'])
        key=col(lojas,*STORE_NUMBER_KEYS); label=col(lojas,*STORE_LABELS)
        if key and label:
            mapping=(lojas.with_columns(text_expr(key).alias('_LOJA_KEY'),
                (text_expr(key)+pl.lit(' - ')+text_expr(label)).alias('_LOJA_COMPLETA'))
                .filter(pl.col('_LOJA_KEY')!='').select(['_LOJA_KEY','_LOJA_COMPLETA']).unique('_LOJA_KEY',keep='first'))
            labels=sorted((v for v in mapping.get_column('_LOJA_COMPLETA').to_list() if v),key=natural_key)
            mapping_keys=set(mapping.get_column('_LOJA_KEY').to_list())
            candidates=[candidate for candidate in DATA_STORE_KEYS if candidate in carteira.columns]
            scored=[]
            for candidate in candidates:
                values=set(carteira.select(text_expr(candidate).alias('v')).get_column('v').to_list())
                scored.append((len(values & mapping_keys),candidate))
            data_key=max(scored)[1] if scored and max(scored)[0]>0 else None
            if not data_key:
                raise ValueError('A lista de lojas foi encontrada, mas nenhum NºLoja corresponde aos valores de CD_ROTA da Carteira.')
            joined=carteira.with_columns(text_expr(data_key).alias('_LOJA_KEY')).join(mapping,on='_LOJA_KEY',how='left')
            joined=joined.filter(pl.col('_LOJA_COMPLETA').is_not_null())
            return joined,labels,source['name']
    fallback=carteira.with_columns(text_expr(empresa).alias('_LOJA_COMPLETA'))
    labels=sorted((v for v in fallback.select(pl.col('_LOJA_COMPLETA')).unique().get_column('_LOJA_COMPLETA').to_list() if v),key=natural_key)
    return fallback,labels,None

def build(filters=None):
    filters=filters or {}; carteira,source,_,_=load_carteira_combined()
    qtd=col(carteira,'QTD_PENDENTE'); aging=col(carteira,'DS'); classe=col(carteira,'CD_CLASSE')
    rota=col(carteira,'CD_ROTA'); status=col(carteira,'STATUS_SEPARACAO'); empresa=col(carteira,*COMPANY_KEYS)
    missing=[name for name,value in [('CD_EMPRESA',empresa),('QTD_PENDENTE',qtd),('DS',aging),('CD_CLASSE',classe)] if not value]
    if missing:raise ValueError('Colunas obrigatórias ausentes: '+', '.join(missing))
    data,store_rows,store_source=_store_dimension(carteira,empresa)
    data=data.filter((text_expr(empresa)!='')&(text_expr(qtd)!='')); left_data=data
    options={}
    for key,column in {'empresa':empresa,'classe':classe,'rota':rota,'status':status}.items():
        if not column:options[key]=[];continue
        values=[v for v in data.select(text_expr(column).alias('v')).unique().get_column('v').to_list() if v]
        if key=='status':values=[v for v in values if clean_name(v) in ('PENDENTE','EM_SEPARACAO','AGUARDANDO_LIBERACAO')]
        options[key]=sorted(values,key=natural_key)
        selected=filters.get(key) or []
        if isinstance(selected,str):selected=[selected]
        if selected:
            data=data.filter(text_expr(column).is_in(selected))
            if key!='classe':left_data=left_data.filter(text_expr(column).is_in(selected))
    status_selected=bool(filters.get('status'))
    if status_selected:
        positive=pl.col(qtd).cast(pl.Float64,strict=False).fill_null(0)>0
        data=data.filter(positive);left_data=left_data.filter(positive)
    aging_columns=list(dict.fromkeys([*AGING_SCHEMA,*(v for v in data.select(text_expr(aging).alias('v')).unique().get_column('v').to_list() if v)]))
    class_columns=list(dict.fromkeys([*CLASS_SCHEMA,*(v for v in data.select(text_expr(classe).alias('v')).unique().get_column('v').to_list() if v)]))
    left_data=left_data.filter(text_expr(classe)=='ZCHP')
    fixed_rows=None if status_selected else store_rows
    return {'matrix_aging':matrix_rows(left_data,'_LOJA_COMPLETA',aging,qtd,aging_columns,fixed_rows,'Loja Completa'),
        'matrix_class':matrix_rows(data,'_LOJA_COMPLETA',classe,qtd,class_columns,fixed_rows,'Loja Completa'),'filters':options,
        'meta':{'rows':data.height,'updated_at':source.get('last_run'),'status':source.get('status') or 'IDLE','status_message':source.get('status_message') or '',
        'total_pending':round(data.select(pl.col(qtd).cast(pl.Float64,strict=False).fill_null(0).sum()).item() or 0),'store_source':store_source}}
