drop view cms_v_pages;
drop index cms_pages_unique_tree_order;
alter table cms_pages add column kind text;
update cms_pages set kind='page';
alter table cms_pages alter column kind set not null;
create unique index cms_pages_unique_tree_order on cms_pages (ord, coalesce(parent, 0), site, kind);

create or replace function cms_pages_update_order () returns trigger as $$
begin
  if new.ord is null then
    new.ord := coalesce((select max(ord)+1 from cms_pages
                         where site = new.site and kind = new.kind
                         and coalesce(parent, 0)=coalesce(new.parent, 0)), 1);
  else
    -- This trigger has a problem with the order of application of changes
    -- during the recursion.  When the modified page 'ord' is smaller than the
    -- original and there are no empty ord slots in between the old and new
    -- value, the following statement recourses up the the initially modified
    -- row and the final value is the value set by the statement rather than
    -- new.ord of the original call (the intended new value).  The work around
    -- is to set the ord to zero first in the page update rule.
    update cms_pages set ord=ord+1
    where site = new.site and kind = new.kind and coalesce(parent, 0) = coalesce(new.parent, 0)
           and ord = new.ord and page_id != new.page_id;
  end if;
  return new;
end;
$$ language plpgsql;

alter table cms_page_texts add column creator int references users;
alter table cms_page_texts add column created timestamp default now();
alter table cms_page_texts add column published_since timestamp;

insert into cms_page_history (page_id, lang, uid, timestamp, comment, content,
                              changed_lines, inserted_lines, deleted_lines)
select page_id, lang, (select uid from role_members where role_id='admin' order by uid limit 1),
       current_timestamp(0) at time zone 'GMT',
       case when lang='cs' then 'Počáteční verze' else 'Initial version' end,
       _content, 0,
       coalesce(array_upper(string_to_array(content, E'\n'), 1), 0), 0 from cms_page_texts
       where (page_id, lang) not in (select page_id, lang from cms_page_history);

update cms_page_texts t set creator=x.uid, created=x.timestamp, published_since=x.timestamp
from (select page_id, lang, uid, timestamp 
      from cms_page_history h 
      where history_id=(select min(history_id) from cms_page_history 
                        where page_id=h.page_id and lang=h.lang)) as x
where x.page_id=t.page_id and x.lang=t.lang;

alter table cms_page_texts alter column creator set not null;
alter table cms_page_texts alter column created set not null;

create or replace view cms_v_pages as
select p.page_id ||'.'|| l.lang as page_key, p.site, p.kind, l.lang,
       p.page_id, p.identifier, p.parent, p.modname,
       p.menu_visibility, p.foldable, p.ord, p.tree_order,
       p.read_role_id, p.write_role_id,
       coalesce(t.published, false) as published,
       t.creator, t.created, t.published_since,
       coalesce(t.title, p.identifier) as title_or_identifier,
       t.title, t.description, t.content, t._title, t._description, t._content
from cms_pages p cross join cms_languages l
     left outer join cms_page_texts t using (page_id, lang);

create or replace rule cms_v_pages_insert as
  on insert to cms_v_pages do instead (
     insert into cms_pages (site, kind, identifier, parent, modname, read_role_id, write_role_id,
                            menu_visibility, foldable, ord)
     values (new.site, new.kind, new.identifier, new.parent, new.modname,
             new.read_role_id, new.write_role_id, new.menu_visibility, new.foldable, new.ord);
     update cms_pages set tree_order = cms_page_tree_order(page_id) where site=new.site and kind=new.kind;
     insert into cms_page_texts (page_id, lang, published,
          	    	 	 creator, created, published_since,
                                 title, description, content,
                                 _title, _description, _content)
     select page_id, new.lang, new.published,
	    new.creator, new.created, new.published_since,
            new.title, new.description, new.content,
            new._title, new._description, new._content
     from cms_pages where identifier=new.identifier and site=new.site and kind=new.kind
     returning page_id ||'.'|| lang, null::text, null::text,
       lang, page_id, null::text, null::int, null::text, null::text, null::boolean,
       null::int, null::text, null::name, null::name,
       published, creator, created, published_since, title, title, description, content, _title,
       _description, _content;
);

create or replace rule cms_v_pages_update as
  on update to cms_v_pages do instead (
    -- Set the ord=0 first to work around the problem with recursion order in
    -- cms_pages_update_order trigger (see the comment there for more info).
    update cms_pages set ord=0 where cms_pages.page_id = old.page_id and new.ord < old.ord;
    update cms_pages set
        site = new.site,
        kind = new.kind,
        identifier = new.identifier,
        parent = new.parent,
        modname = new.modname,
        read_role_id = new.read_role_id,
        write_role_id = new.write_role_id,
        menu_visibility = new.menu_visibility,
        foldable = new.foldable,
        ord = new.ord
    where cms_pages.page_id = old.page_id;
    update cms_pages set tree_order = cms_page_tree_order(page_id) where site=new.site and kind=new.kind;
    update cms_page_texts set
        published = new.published,
        title = new.title,
        description = new.description,
	creator = new.creator,
	created = new.created,
	published_since = new.published_since,
        content = new.content,
        _title = new._title,
        _description = new._description,
        _content = new._content
    where page_id = old.page_id and lang = new.lang;
    insert into cms_page_texts (page_id, lang, published,
           	                creator, created, published_since,
                                title, description, content,
                                _title, _description, _content)
           select old.page_id, new.lang, new.published,
      	    	  new.creator, new.created, new.published_since,
                  new.title, new.description, new.content,
                  new._title, new._description, new._content
           where new.lang not in (select lang from cms_page_texts where page_id=old.page_id)
               	 and coalesce(new.title, new.description, new.content,
                              new._title, new._description, new._content) is not null;
);

create or replace rule cms_v_pages_delete as
  on delete to cms_v_pages do instead (
     delete from cms_pages where page_id = old.page_id;
);

create table cms_publications (
       -- bibliographic data of the original (paper) books
       page_id int unique not null references cms_pages on delete cascade,
       author text not null, -- full name or a comma separated list of names
       isbn text,
       cover_image int references cms_page_attachments on delete set null,
       illustrator text, -- full name or a comma separated list of names
       publisher text, -- full name of the publisher
       published_year int, -- year published
       edition int, -- first, second, ...
       notes text -- any other additional info, such as translator(s), reviewer(s) etc.
);

create or replace view cms_v_publications as
select *
from cms_v_pages pages join cms_publications publications using (page_id);

create or replace rule cms_v_publications_insert as
  on insert to cms_v_publications do instead (
     insert into cms_v_pages (site, kind, identifier, parent, modname, read_role_id, write_role_id,
                              menu_visibility, foldable, ord, lang, published,
			      creator, created, published_since,
                              title, description, content, _title, _description, _content)
     values (new.site, new.kind, new.identifier, new.parent, new.modname,
             new.read_role_id, new.write_role_id, new.menu_visibility, new.foldable, new.ord,
             new.lang, new.published, new.creator, new.created, new.published_since,
	     new.title, new.description, new.content,
             new._title, new._description, new._content);
     insert into cms_publications (page_id, author, isbn, cover_image, illustrator,
                                   publisher, published_year, edition, notes)
     select page_id, new.author, new.isbn, new.cover_image, new.illustrator,
            new.publisher, new.published_year, new.edition, new.notes
     from cms_pages where identifier=new.identifier and site=new.site and kind=new.kind
     returning page_id, page_id ||'.'|| (select min(lang) from cms_page_texts where page_id=cms_publications.page_id), null::text,
       null::text, null::char(2), null::text, null::int, null::text, null::text, null::boolean,
       null::int, null::text, null::name, null::name,
       null::bool, null::int, null::timestamp, null::timestamp, null::text, null::text,
       null::text, null::text, null::text, null::text, null::text,
       author, isbn, cover_image, illustrator,
       publisher, published_year, edition, notes;
);

create or replace rule cms_v_publications_update as
  on update to cms_v_publications do instead (
    update cms_v_pages set
        site = new.site,
        kind = new.kind,
        identifier = new.identifier,
        parent = new.parent,
        modname = new.modname,
        read_role_id = new.read_role_id,
        write_role_id = new.write_role_id,
        menu_visibility = new.menu_visibility,
        foldable = new.foldable,
        ord = new.ord,
	lang = new.lang,
        published = new.published,
	creator = new.creator,
	created = new.created,
	published_since = new.published_since,
        title = new.title,
        description = new.description,
        content = new.content,
        _title = new._title,
        _description = new._description,
        _content = new._content
    where page_id = old.page_id and lang = old.lang;
    update cms_publications set
	author = new.author,
	isbn = new.isbn,
	cover_image = new.cover_image,
	illustrator = new.illustrator,
	publisher = new.publisher,
	published_year = new.published_year,
	edition = new.edition,
	notes = new.notes
    where page_id = old.page_id;
);

create or replace rule cms_v_publications_delete as
  on delete to cms_v_publications do instead (
     delete from cms_pages where page_id = old.page_id;
);

create or replace function is_child_page (integer, integer) returns bool as $$
   select case when (select parent from cms_pages where page_id=$1) = $2 then true
   when (select parent from cms_pages where page_id=$1) is null then false
   else is_child_page((select parent from cms_pages where page_id=$1), $2) end
$$ language sql stable;

update cms_pages set modname='Publications' where modname='EBooks';
update cms_pages set kind='publication' where parent in (select page_id from cms_pages where modname='Publications');
update cms_pages p set kind='chapter' from (select x.page_id from cms_pages x join cms_pages y on x.page_id!=y.page_id and y.kind='publication' and is_child_page(x.page_id, y.page_id)) chapters where p.page_id=chapters.page_id;
insert into cms_publications (page_id, author) select page_id, '?' from cms_pages where kind = 'publication';

update cms_page_texts t
       set content=replace(content, 'src="'||old_url, 'src="'||new_url),
           _content=replace(_content, 'src="'||old_url, 'src="'||new_url)
       from (select y.page_id,
                    '/'||y.identifier||'/attachments/' as old_url,
                    '/'||x.identifier||'/data/'||y.identifier||'/attachments/' as new_url
             from cms_pages x join cms_pages y on (x.page_id=y.parent)
             where x.modname='Publications'
             union
             select z.page_id,
                    '/'||z.identifier||'/attachments/' as old_url,
                    '/'||x.identifier||'/data/'||y.identifier||'/chapters/'||z.identifier||'/attachments/' as new_url
             from cms_pages x join cms_pages y on (x.page_id=y.parent)
                  join cms_pages z on (is_child_page(z.page_id, y.page_id))
             where x.modname='Publications'
       ) pages
       where t.page_id=pages.page_id;

drop function is_child_page(integer, integer);

create table cms_publication_languages (
       -- list of content languages available for given publication
       page_id int not null references cms_publications(page_id) on delete cascade,
       lang text not null, -- language code
       unique (page_id, lang)
);

create table cms_publication_indexes (
       -- list of indexes available for given publication
       index_id serial primary key,
       page_id int not null references cms_publications(page_id) on delete cascade,
       title text not null,
       unique (page_id, title)
);

