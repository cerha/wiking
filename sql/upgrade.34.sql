alter table users alter column login type varchar(64);

create table cms_discussions (
	comment_id serial primary key,
	page_id int not null references cms_pages on delete cascade,
	lang char(2) not null references cms_languages(lang) on update cascade,
	author int not null references users,
	"timestamp" timestamp not null default now(),
	in_reply_to int references cms_discussions on delete set null,
	tree_order text not null,
	text text not null
);
create index cms_discussions_tree_order_index on cms_discussions (tree_order);

create or replace function cms_discussions_trigger_before_insert() returns trigger as $$
declare
  parent_tree_order text := '';
begin
  if new.in_reply_to is not null then
    parent_tree_order := (select tree_order||'.' from cms_discussions where comment_id=new.in_reply_to);
  end if;
  new.tree_order := parent_tree_order || to_char(new.comment_id, 'FM000000000');
  return new;
end;
$$ language plpgsql;

create trigger cms_discussions_trigger_before_insert before insert on cms_discussions
for each row execute procedure cms_discussions_trigger_before_insert();

insert into cms_discussions (page_id, lang, author, timestamp, text) select page_id, lang, author, timestamp, content from cms_news where page_id in (select page_id from cms_pages where modname='Discussions');
delete from cms_news where page_id in (select page_id from cms_pages where modname='Discussions');

update cms_database_version set version=34;
