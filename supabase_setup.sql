-- Run once in the Supabase SQL Editor. Does not replace existing records.
begin;
create schema if not exists marathon_private;
revoke all on schema marathon_private from public, anon, authenticated;
create table if not exists marathon_private.sales (
 id integer primary key check(id=1),
 document jsonb not null
);
create table if not exists marathon_private.sales_revision (
 revision bigint primary key,
 document jsonb not null,
 archived_at timestamptz not null default now()
);
alter table marathon_private.sales enable row level security;
alter table marathon_private.sales_revision enable row level security;
revoke all on all tables in schema marathon_private from public, anon, authenticated;
insert into marathon_private.sales values (1,'{"schema_version":1,"revision":0,"companies":[],"orders":[],"targets":{},"history":[]}') on conflict do nothing;
create or replace function public.marathon_sales_read() returns jsonb
language sql security definer set search_path = '' as $$
 select document from marathon_private.sales where id=1;
$$;
create or replace function public.marathon_sales_save(p_data jsonb, p_expected_revision bigint, p_action text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare current_doc jsonb; next_doc jsonb; next_revision bigint; saved_time timestamptz := clock_timestamp();
begin
 select document into strict current_doc from marathon_private.sales where id=1 for update;
 if (current_doc->>'revision')::bigint <> p_expected_revision then
  raise sqlstate 'PT409' using message='Stale revision';
 end if;
 if p_data->>'schema_version' is distinct from '1'
 or jsonb_typeof(p_data->'companies') is distinct from 'array'
 or jsonb_typeof(p_data->'orders') is distinct from 'array'
 or jsonb_typeof(p_data->'targets') is distinct from 'object' then
  raise exception 'Invalid sales document';
 end if;
 next_revision := p_expected_revision+1;
 next_doc := p_data || jsonb_build_object('revision',next_revision,'saved_at',saved_time,
 'history',(current_doc->'history') || jsonb_build_array(jsonb_build_object('at',saved_time,'action',p_action,'revision',next_revision)));
 insert into marathon_private.sales_revision(revision,document) values(p_expected_revision,current_doc);
 update marathon_private.sales set document=next_doc where id=1;
 return next_doc;
end;
$$;
revoke all on function public.marathon_sales_read() from public,anon,authenticated;
revoke all on function public.marathon_sales_save(jsonb,bigint,text) from public,anon,authenticated;
grant execute on function public.marathon_sales_read() to service_role;
grant execute on function public.marathon_sales_save(jsonb,bigint,text) to service_role;
commit;
