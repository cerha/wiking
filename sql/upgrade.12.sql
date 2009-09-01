alter table stylesheets add column media varchar(12) not null default 'all';
alter table stylesheets add column ord int;
update stylesheets set ord=10 where identifier='default.css';
insert into stylesheets (identifier, media, ord) values ('layout.css', 'screen', 20);
insert into stylesheets (identifier, media, ord) values ('print.css', 'print', 30);
