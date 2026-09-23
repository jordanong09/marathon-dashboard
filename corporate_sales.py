"""Persistent corporate sales, order workflow, and registration utilization draft."""
from __future__ import annotations
import copy
import json
import uuid
from datetime import date
from pathlib import Path
import pandas as pd
import streamlit as st
from sales_store import stage, summarize, MILESTONES
from sales_backend import read_store, save_store, storage_label

SALES_PATH=Path(__file__).parent/'planning_data'/'corporate_sales.json'

def render_corporate_sales(data,categories,path=None):
    path=path or SALES_PATH
    st.subheader('Corporate Sales')
    st.caption('DRAFT · Reservations → verified payments → registration links → utilization. Records save independently of registration uploads.')
    try:
        backend_label=storage_label()
        st.caption('Storage: '+backend_label)
        snapshot_key='sales_records_'+backend_label+str(path)
        if snapshot_key not in st.session_state:
            st.session_state[snapshot_key]=read_store(path)
        records=copy.deepcopy(st.session_state[snapshot_key])
    except (OSError,ValueError) as error:
        st.error(f'Cannot read saved sales records: {error}. Existing files have not been changed.')
        return
    def commit(changed,action):
        try:
            saved=save_store(path,changed,records['revision'],action)
            st.session_state[snapshot_key]=saved
        except (ValueError,OSError) as error:
            st.error(f'Not saved: {error}')
            return
        st.session_state.sales_saved_notice=action+' — saved to '+backend_label+'.'
        st.rerun()
    if 'sales_saved_notice' in st.session_state:
        st.success(st.session_state.pop('sales_saved_notice'))
    if st.button('Reload saved sales records'):
        st.session_state.pop(snapshot_key,None)
        st.rerun()
    st.caption(f"Saved revision {records['revision']} · {records.get('saved_at','No records saved yet')}")
    st.download_button('Download sales backup',json.dumps(records,indent=2),'corporate-sales-backup.json','application/json')
    companies=records['companies']; orders=records['orders']
    names={c['id']:c['name'] for c in companies}
    available=[] if data.empty else sorted(data['Corporate Group'].dropna().astype(str).unique())
    matched={a.casefold() for c in companies for a in c['aliases']}
    missing=[a for a in available if a.casefold() not in matched]
    if missing:
        st.warning(f'{len(missing)} companies in the registration sheet have no linked sales record. Add or match them under Companies.')
        with st.expander('Companies awaiting a sales record'):
            st.write(missing)
    tab_names=['Overview','Companies','New order / top-up','Orders in progress','Company utilization','Daily activity']
    if 'sales_active_tab' not in st.session_state:
        requested=st.query_params.get('sales_view','Overview')
        st.session_state.sales_active_tab=requested if requested in tab_names else 'Overview'
    def remember_tab():
        st.query_params['sales_view']=st.session_state.sales_active_tab
    tabs=st.tabs(tab_names,key='sales_active_tab',on_change=remember_tab)
    summary=pd.DataFrame(summarize(orders,categories))
    summary['Group target']=summary.Category.map(records['targets']).fillna(0).astype(int)
    summary['Available to sell']=summary['Group target']-summary.Reserved
    summary['Paid progress %']=summary.Paid/summary['Group target'].replace(0,float('nan'))*100
    with tabs[0]:
        a,b,c,d=st.columns(4)
        a.metric('Reserved slots',f'{summary.Reserved.sum():,}')
        b.metric('Verified paid slots',f'{summary.Paid.sum():,}')
        c.metric('Released slots',f'{summary.Released.sum():,}')
        d.metric('Companies with active orders',len({o['company_id'] for o in orders if not o.get('cancelled')}))
        st.dataframe(summary,hide_index=True,width='stretch')
        if summary['Available to sell'].lt(0).any(): st.warning('Reserved places exceed the saved group target in one or more categories. Review targets before taking further orders.')
        with st.expander('Set group sales targets'):
            st.caption('These are persistent corporate-sales budgets. The earlier Management Slot Planning scenario remains separate in this draft.')
            with st.form('sales_targets'):
                edited=st.data_editor(summary[['Category','Group target']],disabled=['Category'],hide_index=True,width='stretch',column_config={'Group target':st.column_config.NumberColumn(min_value=0,step=1,required=True)})
                if st.form_submit_button('Save group targets'):
                    changed=copy.deepcopy(records); changed['targets']=dict(zip(edited.Category,edited['Group target'].astype(int)))
                    commit(changed,'Group targets updated')
    with tabs[1]:
        with st.form('sales_company'):
            name=st.text_input('Company name')
            aliases=st.multiselect('Names used in registration uploads',available)
            if st.form_submit_button('Save new company'):
                if not name.strip() or any(c['name'].casefold()==name.strip().casefold() for c in companies):
                    st.error('Enter a unique company name.')
                elif any(a.casefold() in matched for a in aliases): st.error('A registration name is already linked to another company.')
                else:
                    changed=copy.deepcopy(records); changed['companies'].append({'id':uuid.uuid4().hex,'name':name.strip(),'aliases':aliases})
                    commit(changed,'Company added: '+name.strip())
        if companies:
            company_id=st.selectbox('Company to match',list(names),format_func=names.get)
            company=next(c for c in companies if c['id']==company_id)
            with st.form('sales_aliases'):
                aliases=st.multiselect('Registration names for this company',sorted(set(available+company['aliases'])),default=company['aliases'])
                if st.form_submit_button('Save registration matching'):
                    other={a.casefold() for c in companies if c['id']!=company_id for a in c['aliases']}
                    if any(a.casefold() in other for a in aliases): st.error('That name is linked to another company.')
                    else:
                        changed=copy.deepcopy(records); next(c for c in changed['companies'] if c['id']==company_id)['aliases']=aliases
                        commit(changed,'Company matching updated: '+company['name'])
    with tabs[2]:
        if not companies: st.info('Add a company first. A registration upload is not required to record an order.')
        else:
            with st.form('sales_order'):
                company_id=st.selectbox('Ordering company',list(names),format_func=names.get)
                sent=st.date_input('Order form sent — reserves places',value=date.today(),max_value=date.today())
                reference=st.text_input('Customer order reference (optional)')
                quantities=st.data_editor(pd.DataFrame({'Category':categories,'Places':0}),disabled=['Category'],hide_index=True,width='stretch',column_config={'Places':st.column_config.NumberColumn(min_value=0,step=1,required=True)})
                if st.form_submit_button('Save order and reserve places'):
                    prior=[o for o in orders if o['company_id']==company_id]
                    order={'id':uuid.uuid4().hex,'company_id':company_id,'label':'Initial order' if not prior else f'Top-up {len(prior)}','reference':reference.strip(),
                        'sent_date':sent.isoformat(),'quantities':dict(zip(quantities.Category,quantities.Places.astype(int))), 'invoice':'','invoice_amount':0.0,'currency':'SGD','milestones':{},'cancelled':False,'notes':''}
                    changed=copy.deepcopy(records); changed['orders'].append(order); commit(changed,'Order created: '+names[company_id]+' / '+order['label'])
    with tabs[3]:
        display=[{'Order ID':o['id'],'Company':names[o['company_id']],'Order':o['label'],'Slots':sum(o['quantities'].values()),'Stage':stage(o),
            'Days awaiting action':None if stage(o) in ['✓ Complete','Cancelled / released'] else (date.today()-date.fromisoformat(max([o['sent_date']]+list(o['milestones'].values())))).days,
            'Sent':o['sent_date'],'Invoice':o['invoice']} for o in orders]
        st.dataframe(pd.DataFrame(display),hide_index=True,width='stretch')
        if orders:
            order_ids=[o['id'] for o in orders]
            if st.session_state.get('sales_selected_order') not in order_ids:
                requested=st.query_params.get('sales_order')
                st.session_state.sales_selected_order=requested if requested in order_ids else order_ids[0]
            def remember_order():
                st.query_params['sales_order']=st.session_state.sales_selected_order
            key=st.selectbox('Order to update',order_ids,key='sales_selected_order',on_change=remember_order,
                format_func=lambda key:next(names[o['company_id']]+' · '+o['label']+' · '+o['sent_date'] for o in orders if o['id']==key))
            o=next(o for o in orders if o['id']==key)
            with st.form('sales_workflow_'+key):
                invoice=st.text_input('Invoice reference',o['invoice'])
                amount=st.number_input('Invoice amount (SGD)',min_value=0.0,value=float(o['invoice_amount']),step=1.0)
                sent=st.date_input('Order form sent date',value=date.fromisoformat(o['sent_date']),max_value=date.today())
                milestones={}
                for label in MILESTONES:
                    value=st.date_input(label+' completion date',value=date.fromisoformat(o['milestones'][label]) if o['milestones'].get(label) else None,max_value=date.today(),key='milestone_'+key+label)
                    if value: milestones[label]=value.isoformat()
                updated_quantities=st.data_editor(pd.DataFrame({'Category':categories,'Places':[o['quantities'].get(c,0) for c in categories]}),disabled=['Category'],hide_index=True,width='stretch',column_config={'Places':st.column_config.NumberColumn(min_value=0,step=1,required=True)})
                cancelled=st.checkbox('Cancel this order and release its reserved allocation',value=o['cancelled'])
                notes=st.text_area('Notes / cancellation reason',o.get('notes',''))
                if st.form_submit_button('Save order progress'):
                    if cancelled and not notes.strip(): st.error('Enter a reason when cancelling an order.')
                    else:
                        changed=copy.deepcopy(records); item=next(x for x in changed['orders'] if x['id']==key)
                        item.update(invoice=invoice.strip(),invoice_amount=amount,sent_date=sent.isoformat(),milestones=milestones,cancelled=cancelled,notes=notes,
                            quantities=dict(zip(updated_quantities.Category,updated_quantities.Places.astype(int))))
                        commit(changed,'Order updated: '+names[o['company_id']]+' / '+o['label'])
            st.caption('Enter dates in sequence. Clear later milestones before reopening an earlier step. A completed order has all six dates, ending with links disseminated. Saving records does not send links or process payments.')
    with tabs[4]:
        if data.empty: st.info('Upload a registration master sheet to calculate utilization. Saved orders remain available without it.')
        for company in companies:
            company_orders=[o for o in orders if o['company_id']==company['id']]
            actual=data.iloc[0:0] if data.empty else data[data['Corporate Group'].fillna('').str.casefold().isin([a.casefold() for a in company['aliases']])]
            rows=pd.DataFrame(summarize(company_orders,categories))
            rows['Registered']=rows.Category.map(actual['Grouped Category'].value_counts() if not actual.empty else {}).fillna(0).astype(int)
            if data.empty or not company['aliases']:
                rows['Registered']=float('nan')
            rows['Unredeemed released places']=rows.Released-rows.Registered
            rows['Utilization %']=rows.Registered/rows.Released.replace(0,float('nan'))*100
            complete=sum(stage(o)=='✓ Complete' for o in company_orders)
            with st.expander(f"{company['name']} · {len(company_orders)} orders · {complete} complete · {rows.Released.sum():,} released places"):
                if not company['aliases']: st.warning('Registration-name matching has not been set; utilization is not yet verified.')
                if (rows.Registered>rows.Released).any(): st.warning('Registrations exceed disseminated allocations. Check order progress and company matching.')
                st.dataframe(rows,hide_index=True,width='stretch')
                for o in company_orders:
                    st.markdown(f"**{o['label']} · {stage(o)}**")
                    st.write({'Invoice':o['invoice'],'Invoice amount (SGD)':o['invoice_amount'],'Sent':o['sent_date'],**o['milestones']})
                    st.write({cat:n for cat,n in o['quantities'].items() if n})
        st.caption('Utilization is reconciled by company and category. Registrations are not attributed to individual invoices without an order/batch identifier in the master sheet.')
    with tabs[5]:
        activity=[]
        for o in orders:
            activity.append({'Date':o['sent_date'],'Company':names[o['company_id']],'Event':'Order form sent','Order':o['label'],'Slots':sum(o['quantities'].values()),'Current status':stage(o)})
            for label,when in o['milestones'].items(): activity.append({'Date':when,'Company':names[o['company_id']],'Event':label,'Order':o['label'],'Slots':sum(o['quantities'].values()),'Current status':stage(o)})
        if activity:
            frame=pd.DataFrame(activity).sort_values('Date',ascending=False)
            sent=frame[frame.Event.eq('Order form sent')]
            daily=sent.groupby('Date').agg(Orders=('Company','size'),Companies=('Company','nunique'),Slots=('Slots','sum'))
            daily['Top-ups']=sent.assign(Topup=sent.Order.ne('Initial order')).groupby('Date').Topup.sum()
            st.dataframe(daily.sort_index(ascending=False),width='stretch')
            st.dataframe(frame,hide_index=True,width='stretch')
            st.download_button('Download activity',frame.to_csv(index=False),'corporate-sales-activity.csv','text/csv')
            st.caption('Activity reflects saved order dates and current quantities, including cancelled orders. It is not a payment ledger. Previous revisions are retained in the configured storage.')
