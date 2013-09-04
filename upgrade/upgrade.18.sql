alter table roles add column auto boolean not null default false;
insert into roles (role_id, system, auto) values ('anyone', 't', 't');
insert into roles (role_id, system, auto) values ('authenticated', 't', 't');
insert into roles (role_id, system, auto) values ('owner', 't', 't');
insert into roles (role_id, system, auto) values ('user', 't', 't');
insert into roles (role_id, system, auto) values ('registered', 't', 't');

drop view mapping;
drop view pages;
drop view panels;

alter table _mapping add column read_role_id name not null default 'anyone' references roles on update cascade;
alter table _mapping add column write_role_id name not null default 'content_admin' references roles on update cascade on delete set default;
update _mapping set read_role_id='user' where private;
alter table _mapping drop column private;
alter table _mapping drop column owner;


create or replace view mapping as select * from _mapping;

create or replace view pages as 
select m.mapping_id ||'.'|| l.lang as page_id, l.lang, 
       m.mapping_id, m.identifier, m.parent, m.modname, 
       m.hidden, m.ord, m.tree_order, m.read_role_id, m.write_role_id,
       coalesce(p.published, false) as published,
       coalesce(p.title, m.identifier) as title_or_identifier, 
       p.title, p.description, p.content, p._title, p._description, p._content
from _mapping m cross join languages l
     left outer join _pages p using (mapping_id, lang);

create or replace rule pages_insert as
  on insert to pages do instead (
     insert into _mapping (identifier, parent, modname, read_role_id, write_role_id, hidden, ord)
     values (new.identifier, new.parent, new.modname, new.read_role_id, new.write_role_id, new.hidden, 
             coalesce(new.ord, (select max(ord)+100 from _mapping 
                                where coalesce(parent, 0)=coalesce(new.parent, 0)), 100));
     update _mapping set tree_order = _mapping_tree_order(mapping_id);
     insert into _pages (mapping_id, lang, published, 
                         title, description, content, _title, _description, _content)
     select (select mapping_id from _mapping where identifier=new.identifier),
            new.lang, new.published, 
            new.title, new.description, new.content, new._title, new._description, new._content
     returning mapping_id ||'.'|| lang, 
       lang, mapping_id, null::varchar(32), null::int, null::text, null::boolean, null::int, 
       null::text, null::name, null::name,
       published, title, title, description, content, _title,
       _description, _content
);

create or replace rule pages_update as
  on update to pages do instead (
    update _mapping set
        identifier = new.identifier,
        parent = new.parent,
        modname = new.modname,
        read_role_id = new.read_role_id,
        write_role_id = new.write_role_id,
        hidden = new.hidden,
        ord = new.ord
    where _mapping.mapping_id = old.mapping_id;
    update _mapping set tree_order = _mapping_tree_order(mapping_id);
    update _pages set
        published = new.published,
        title = new.title,
        description = new.description,
        content = new.content,
        _title = new._title,
        _description = new._description,
        _content = new._content
    where mapping_id = old.mapping_id and lang = new.lang;
    insert into _pages (mapping_id, lang, published, 
                        title, description, content, _title, _description, _content) 
           select old.mapping_id, new.lang, new.published, 
                  new.title, new.description, new.content, 
                  new._title, new._description, new._content
           where new.lang not in (select lang from _pages where mapping_id=old.mapping_id)
                 and (new.title is not null or new.description is not null 
                      or new.content is not null 
                      or new._title is not null or new._description is not null 
                      or new._content is not null);
);

create or replace rule pages_delete as
  on delete to pages do instead (
     delete from _mapping where mapping_id = old.mapping_id;
);

create or replace view panels as 
select _panels.*, _mapping.modname, _mapping.identifier, _mapping.read_role_id, _pages.title as mtitle
from _panels 
     left outer join _mapping using (mapping_id) 
     left outer join _pages using (mapping_id, lang);

create or replace rule panels_insert as
  on insert to panels do instead (
     insert into _panels 
        (lang, ptitle, ord, mapping_id, size, content, _content, published)
     VALUES
        (new.lang, new.ptitle, new.ord, new.mapping_id, new.size, 
	 new.content, new._content, new.published)
);

create or replace rule panels_update as
  on UPDATE to panels do instead (
    UPDATE _panels SET
	lang = new.lang,
	ptitle = new.ptitle,
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

