create or replace function cms_pages_update_order () returns trigger as $$
begin
  if new.ord is null then
    new.ord := coalesce((select max(ord)+1 from cms_pages
                         where site=new.site
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
    where site = new.site and coalesce(parent, 0) = coalesce(new.parent, 0)
           and ord = new.ord and page_id != new.page_id;
  end if;
  return new;
end;
$$ language plpgsql;

create trigger cms_pages_trigger_before before insert or update on cms_pages
for each row execute procedure cms_pages_update_order();

create or replace rule cms_v_pages_insert as
  on insert to cms_v_pages do instead (
     insert into cms_pages (site, identifier, parent, modname, read_role_id, write_role_id,
                            menu_visibility, foldable, ord)
     values (new.site, new.identifier, new.parent, new.modname,
             new.read_role_id, new.write_role_id, new.menu_visibility, new.foldable, new.ord);
     update cms_pages set tree_order = cms_page_tree_order(page_id);
     insert into cms_page_texts (page_id, lang, published,
                                 title, description, content,
                                 _title, _description, _content)
     select (select page_id from cms_pages where identifier=new.identifier and site=new.site),
            new.lang, new.published,
            new.title, new.description, new.content,
            new._title, new._description, new._content
     returning page_id ||'.'|| lang, null::text,
       lang, page_id, null::varchar(32), null::int, null::text, null::text, null::boolean,
       null::int, null::text, null::name, null::name,
       published, title, title, description, content, _title,
       _description, _content
);

create or replace rule cms_v_pages_update as
  on update to cms_v_pages do instead (
    -- Set the ord=0 first to work around avoid problem with recursion order in
    -- cms_pages_update_order trigger (see the comment there for more info).
    update cms_pages set ord=0 where cms_pages.page_id = old.page_id and new.ord < old.ord;
    update cms_pages set
        site = new.site,
        identifier = new.identifier,
        parent = new.parent,
        modname = new.modname,
        read_role_id = new.read_role_id,
        write_role_id = new.write_role_id,
        menu_visibility = new.menu_visibility,
        foldable = new.foldable,
        ord = new.ord
    where cms_pages.page_id = old.page_id;
    update cms_pages set tree_order = cms_page_tree_order(page_id) where site=new.site;
    update cms_page_texts set
        published = new.published,
        title = new.title,
        description = new.description,
        content = new.content,
        _title = new._title,
        _description = new._description,
        _content = new._content
    where page_id = old.page_id and lang = new.lang;
    insert into cms_page_texts (page_id, lang, published,
                                title, description, content,
                                _title, _description, _content)
           select old.page_id, new.lang, new.published,
                  new.title, new.description, new.content,
                  new._title, new._description, new._content
           where new.lang not in (select lang from cms_page_texts where page_id=old.page_id)
               	 and coalesce(new.title, new.description, new.content,
                              new._title, new._description, new._content) is not null;
);

-- Make sure no pages have ord=0.  The trigger should shift other pages if necessary.
update cms_pages set ord=1 where ord=0;
