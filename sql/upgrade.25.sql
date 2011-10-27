alter table stylesheets drop column scope;
alter table stylesheets add column scope text not null default 'all';