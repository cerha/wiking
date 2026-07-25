alter table cms_news add column days_displayed int;
update cms_news set days_displayed=90;
alter table cms_news alter column days_displayed set not null;
create or replace function cms_recent_timestamp(ts timestamp, max_days int) returns boolean as $$
select (current_date - $1::date) < $2;
$$ language sql stable;
