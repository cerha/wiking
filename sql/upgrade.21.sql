drop view panels;

alter table _panels add column identifier varchar(32);
alter table _panels add constraint _panels_unique_identifier_lang UNIQUE (identifier, lang);
update _panels p set identifier = (select identifier from _mapping m where m.mapping_id=p.mapping_id) where mapping_id is not null;

alter table _panels rename column ptitle to title;
update _panels p set title = (select title from pages x where x.lang=p.lang and x.mapping_id=p.mapping_id) where title is null and mapping_id is not null;
alter table _panels alter column title set not null;

create or replace view panels as
select _panels.*, _mapping.modname, _mapping.read_role_id
from _panels
     left outer join _mapping using (mapping_id)
     left outer join _pages using (mapping_id, lang);

create or replace rule panels_insert as
  on insert to panels do instead (
     insert into _panels 
        (lang, identifier, title, ord, mapping_id, size, content, _content, published)
     VALUES
        (new.lang, new.identifier, new.title, new.ord, new.mapping_id, new.size, 
	 new.content, new._content, new.published)
);

create or replace rule panels_update as
  on UPDATE to panels do instead (
    UPDATE _panels SET
	lang = new.lang,
	identifier = new.identifier,
	title = new.title,
	ord = new.ord,
	mapping_id = new.mapping_id,
	size = new.size,
	content = new.content,
	_content = new._content,
	published = new.published
    where _panels.panel_id = old.panel_id;
);

create or replace rule panels_delete as
  on delete to panels do instead (
     delete from _panels
     where _panels.panel_id = old.panel_id;
);
