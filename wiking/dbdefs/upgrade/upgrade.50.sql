alter trigger cms_pages_trigger_before on cms_pages rename to cms_pages_update_order__before;

CREATE OR REPLACE FUNCTION "public"."cms_page_tree_order"("page_id" INTEGER) RETURNS TEXT LANGUAGE sql stable AS $$
select
  case when $1 is null then '' else
    (select cms_page_tree_order(parent) || '.' || to_char(coalesce(ord, 999999), 'FM000000')
     from cms_pages where page_id=$1)
  end
as result
$$;


CREATE OR REPLACE RULE "cms_v_pages__insert_instead" AS ON INSERT TO "public"."cms_v_pages"
DO INSTEAD (
     insert into cms_pages (site, kind, identifier, parent, modname,
                            owner, read_role_id, write_role_id,
                            menu_visibility, foldable, ord)
     values (new.site, new.kind, new.identifier, new.parent, new.modname,
             new.owner, new.read_role_id, new.write_role_id,
             new.menu_visibility, new.foldable, new.ord);
     update cms_pages set tree_order = cms_page_tree_order(page_id)
            where site = new.site and
                  (identifier = new.identifier or tree_order != cms_page_tree_order(page_id));
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
       null::int, null::text, null::int, null::name, null::name,
       published, creator, created, published_since, title, title, description, content, _title,
       _description, _content;
        );

CREATE OR REPLACE RULE "cms_v_pages__update_instead" AS ON UPDATE TO "public"."cms_v_pages"
DO INSTEAD (
    -- Set the ord=0 first to work around the problem with recursion order in
    -- cms_pages_update_order trigger (see the comment there for more info).
    update cms_pages set ord=0 where cms_pages.page_id = old.page_id and new.ord < old.ord;
    update cms_pages set
        site = new.site,
        kind = new.kind,
        identifier = new.identifier,
        parent = new.parent,
        modname = new.modname,
        owner = new.owner,
        read_role_id = new.read_role_id,
        write_role_id = new.write_role_id,
        menu_visibility = new.menu_visibility,
        foldable = new.foldable,
        ord = new.ord
    where cms_pages.page_id = old.page_id;
    update cms_pages set tree_order = cms_page_tree_order(page_id)
           where site = new.site and tree_order != cms_page_tree_order(page_id) and
                 (identifier = new.identifier or tree_order != cms_page_tree_order(page_id));
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
