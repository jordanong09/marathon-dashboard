"""Draft management allocation matrices; each registration is counted once."""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import streamlit as st
from admin_dashboard import clean_codes


def seed_programmes(data, categories, category_mapper):
    rows = []
    for parent, column in [('Complimentary','Complimentary Programme'),('Groups','Corporate Group')]:
        for name in sorted(data[column].dropna().astype(str).unique()):
            rows.append(dict(id=f'{parent}:{name}', parent=parent, name=name, field=column,
                value=name, codes=[], eligible=list(categories), pool=None))
    for file in sorted((Path(__file__).parent/'promo_lists').glob('*.xlsx')):
        frame = pd.read_excel(file, dtype=str)
        eligible = sorted({category_mapper(v.strip()) for cell in frame['Categories'].dropna() for v in cell.split(',')} & set(categories))
        limits = pd.to_numeric(frame['Usage'].str.split('/').str[-1],errors='coerce')
        rows.append(dict(id='Campaigns:'+file.stem,parent='Campaigns',name=file.stem,field='code',value='',
            codes=clean_codes(frame['Promo Code']).tolist(),eligible=eligible,pool=int(limits.sum()) if limits.notna().all() else None))
    for market in ['Singapore','International']:
        rows.append(dict(id='Retail:'+market,parent='Retail',name='Local retail' if market=='Singapore' else 'International retail',
            field='Market',value=market,codes=[],eligible=list(categories),pool=None))
    return rows


def registered_matrix(data, programmes, categories, promo_column):
    """Resolve independent programme rules; send overlaps and ineligible matches to review."""
    output = pd.DataFrame(0,index=[p['id'] for p in programmes]+['Review:Unresolved'],columns=categories+['Unmapped'],dtype=int)
    codes = clean_codes(data[promo_column]) if promo_column else pd.Series('',index=data.index)
    masks = []
    explicit = [p for p in programmes if p['field'] != 'Market']
    for p in explicit:
        masks.append(codes.isin(p['codes']) if p['field']=='code' else data[p['field']].eq(p['value']).fillna(False))
    matches = pd.DataFrame({p['id']:m.to_numpy() for p,m in zip(explicit,masks)},index=range(len(data)))
    totals = matches.sum(axis=1) if not matches.empty else pd.Series(0,index=range(len(data)))
    overlap = int(totals.gt(1).sum())
    ineligible = 0
    category=data['Grouped Category'].reset_index(drop=True)
    category=category.where(category.isin(categories),'Unmapped')
    chosen=pd.Series('Review:Unresolved',index=range(len(data)))
    public=(data['Complimentary Programme'].fillna('').eq('') & data['Corporate Group'].fillna('').eq('')).reset_index(drop=True)
    for p in programmes:
        candidate=(matches[p['id']] & totals.eq(1)) if p['field']!='Market' else (totals.eq(0) & public & data['Market'].reset_index(drop=True).eq(p['value']))
        eligible=category.isin(p['eligible'])
        ineligible+=int((candidate & ~eligible).sum())
        chosen.loc[candidate & eligible]=p['id']
    counts=pd.crosstab(chosen,category)
    output=counts.reindex(index=output.index,columns=output.columns,fill_value=0)
    return output, overlap, ineligible


def grouped_table(matrix, programmes, expanded):
    """Display subtotals and optional children without counting subtotals twice."""
    rows, labels = [], []
    for parent in ['Complimentary','Groups','Campaigns','Retail','Review']:
        members = [p for p in programmes if p['parent']==parent]
        ids = [p['id'] for p in members]
        if parent=='Review':
            ids=['Review:Unresolved']
        if not ids:
            continue
        rows.append(matrix.reindex(ids).sum(min_count=1)); labels.append(parent+' — subtotal')
        if parent in expanded:
            for p in members:
                rows.append(matrix.loc[p['id']]); labels.append('↳ '+p['name'])
    rows.append(matrix.sum(min_count=1)); labels.append('TOTAL — all allocations')
    result=pd.DataFrame(rows,index=labels)
    result['Total']=result.sum(axis=1,min_count=1)
    return result


def render_slot_planning(data, categories, promo_column, category_mapper):
    st.subheader('Management Slot Planning')
    from sales_store import summarize
    from sales_backend import read_store
    sales_path=Path(__file__).parent/'planning_data'/'corporate_sales.json'
    with st.expander('Saved corporate sales commitments'):
        try:
            sales=read_store(sales_path)
            committed=pd.DataFrame(summarize(sales['orders'],categories))
            committed['Group target']=committed.Category.map(sales['targets']).fillna(0)
            committed['Available to sell']=committed['Group target']-committed.Reserved
            st.dataframe(committed,hide_index=True,width='stretch')
            st.caption('Live saved corporate orders. These are commitments, not additional participant registrations. The draft allocation matrices below remain separate scenarios.')
        except (ValueError,OSError) as error:
            st.error(f'Cannot read corporate commitments: {error}')
    st.caption('DRAFT · Full uploaded registration file · Programme rows × race category columns. Sidebar filters do not change these totals.')
    if 'planning_programmes' not in st.session_state:
        st.session_state.planning_programmes=seed_programmes(data,categories,category_mapper)
        st.session_state.planning_allocations={}
        st.session_state.planning_baseline={}
    programmes=st.session_state.planning_programmes
    with st.expander('Programme rules & category eligibility'):
        selected=st.selectbox('Programme to configure',[p['id'] for p in programmes],format_func=lambda key:next(p['name'] for p in programmes if p['id']==key))
        p=next(p for p in programmes if p['id']==selected)
        with st.form('programme_rules'):
            eligible=st.multiselect('Eligible race categories',categories,default=p['eligible'])
            pool=st.number_input('Shared pool limit across eligible categories (0 = not specified)',min_value=0,value=p['pool'] or 0,step=1)
            if st.form_submit_button('Apply programme rules'):
                p['eligible']=eligible; p['pool']=pool or None
                st.rerun()
        with st.form('new_campaign'):
            name=st.text_input('New promo allocation name')
            code_text=st.text_area('Exact promo codes, one per line')
            eligible_new=st.multiselect('Applicable categories',categories)
            if st.form_submit_button('Add promo allocation'):
                key='Campaigns:'+name.strip()
                if not name.strip() or not code_text.strip() or not eligible_new or any(p['id']==key for p in programmes):
                    st.error('Enter a unique name, at least one code, and an eligible category.')
                else:
                    programmes.append(dict(id=key,parent='Campaigns',name=name.strip(),field='code',value='',codes=list(set(code_text.splitlines())),eligible=eligible_new,pool=None))
                    st.rerun()
        st.caption('Codes do not define eligibility by themselves. Each programme has explicit category rules. Conflicting matches go to Review, never to two allocations. Ordinary unmapped discount codes remain retail.')
    actual, overlaps, ineligible=registered_matrix(data,programmes,categories,promo_column)
    if overlaps or ineligible or actual.loc['Review:Unresolved'].sum():
        st.warning(f"Review required: {overlaps:,} overlapping programme matches; {ineligible:,} ineligible category matches. {actual.loc['Review:Unresolved'].sum():,} rows are held in Review, outside programme totals.")
    names={p['id']:p['name'] for p in programmes}
    allocation=st.session_state.planning_allocations
    plan=pd.DataFrame(0,index=actual.index,columns=actual.columns,dtype=float)
    for p in programmes:
        for cat in categories:
            plan.loc[p['id'],cat]=allocation.get(p['id'],{}).get(cat,0) if cat in p['eligible'] else float('nan')
    with st.expander('Edit planned allocation',expanded=True):
        parent=st.selectbox('Allocation group',['Complimentary','Groups','Campaigns','Retail'])
        members=[p for p in programmes if p['parent']==parent]
        st.caption('Edit a programme below. Ineligible categories are excluded. Zero is a draft allocation of zero; it is not a capacity setting.')
        if members:
            key=st.selectbox('Allocation programme',[p['id'] for p in members],format_func=lambda key:names[key])
            p=next(p for p in members if p['id']==key)
            with st.form('edit_allocation_'+key):
                editable=pd.DataFrame([{'Programme':p['name'],**{cat:int(plan.loc[key,cat]) for cat in p['eligible']}}])
                changed=st.data_editor(editable,hide_index=True,disabled=['Programme'],width='stretch',
                    column_config={cat:st.column_config.NumberColumn(min_value=0,step=1,required=True) for cat in p['eligible']})
                if st.form_submit_button('Apply draft allocation'):
                    allocation[key]={cat:int(changed.iloc[0][cat]) for cat in p['eligible']}
                    st.rerun()
    remaining=plan-actual
    a,b,c,d=st.columns(4)
    a.metric('Planned places',f'{int(plan.sum().sum()):,}')
    b.metric('Registered rows',f'{len(data):,}')
    c.metric('Unfilled allocated places',f'{int(remaining.clip(lower=0).sum().sum()):,}')
    d.metric('Registrations above allocation',f'{int(-remaining.clip(upper=0).sum().sum()):,}')
    st.caption('Unfilled places may still be promised to groups or sponsors. This draft does not record commitments, so remaining places are not automatically releasable. Category capacity is not changed by this scenario.')
    expanded=st.multiselect('Expand programme rows',['Complimentary','Groups','Campaigns','Retail'],default=['Campaigns','Retail'])
    for title,matrix in [('1 · Planned allocation',plan),('2 · Registered',actual),('3 · Remaining allocation',remaining)]:
        st.markdown('### '+title)
        display=grouped_table(matrix,programmes,expanded)
        st.dataframe(display.style.format('{:,.0f}',na_rep='—').map(lambda v:'color:#B42318;background-color:#FFF0ED' if pd.notna(v) and v<0 else ''),width='stretch')
        st.download_button('Download '+title.split(' · ')[1],display.to_csv(),'slot-'+title[0]+'.csv','text/csv')
    st.caption('— = ineligible. Negative remaining = registrations exceed the current draft allocation. Review is included in the overall reconciliation. Crew Challenge stays a separate category in these matrices.')
    pools=[]
    for p in programmes:
        if p['pool']:
            used=int(actual.loc[p['id']].sum()); assigned=int(plan.loc[p['id']].sum())
            pools.append({'Programme':p['name'],'Shared pool':p['pool'],'Assigned across categories':assigned,'Registered':used,'Pool remaining':p['pool']-used,'Unassigned pool':p['pool']-assigned})
    if pools:
        st.markdown('### Shared campaign pools')
        st.dataframe(pd.DataFrame(pools),hide_index=True,width='stretch')
        if any(p['Unassigned pool']<0 or p['Pool remaining']<0 for p in pools):
            st.warning('A shared pool is exceeded. Review the category assignments or registrations before using this scenario.')
    if st.button('Set current draft as comparison baseline'):
        st.session_state.planning_baseline=json.loads(json.dumps(allocation))
        st.success('Comparison baseline saved for this session.')
    baseline=st.session_state.planning_baseline
    if baseline:
        changes=[]
        for p in programmes:
            for cat in categories:
                before=baseline.get(p['id'],{}).get(cat,0); after=allocation.get(p['id'],{}).get(cat,0)
                if before!=after: changes.append({'Programme':p['name'],'Category':cat,'Baseline':before,'Draft':after,'Change':after-before})
        st.dataframe(pd.DataFrame(changes),hide_index=True,width='stretch') if changes else st.info('No allocation changes from the comparison baseline.')
    st.download_button('Save draft scenario',json.dumps({'programmes':programmes,'allocations':allocation,'baseline':baseline},indent=2),'slot-planning-draft.json','application/json')
    st.caption('Draft settings survive navigation during this session. The downloaded JSON is a record of this draft; importing saved scenarios is not part of this first version.')
