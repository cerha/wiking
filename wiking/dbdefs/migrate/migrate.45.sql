alter table cms_pages add column owner integer references users (uid);

DROP VIEW "public"."cms_v_publications";
DROP VIEW "public"."cms_v_pages";

CREATE OR REPLACE VIEW "public"."cms_v_pages" AS
SELECT CAST(p.page_id AS TEXT) || '.' || l.lang AS page_key, p.site, p.kind, l.lang, p.page_id, p.identifier, p.parent, p.modname, p.menu_visibility, p.foldable, p.ord, p.tree_order, p.owner, p.read_role_id, p.write_role_id, coalesce(t.published, False) AS published, t.creator, t.created, t.published_since, coalesce(t.title, p.identifier) AS title_or_identifier, t.title, t.description, t.content, t._title, t._description, t._content 
FROM public.cms_pages AS p, public.cms_languages AS l LEFT OUTER JOIN public.cms_page_texts AS t ON l.lang = t.lang 
WHERE p.page_id = t.page_id AND l.lang = t.lang;

GRANT all ON "public".cms_v_pages TO "www-data";

CREATE OR REPLACE RULE "cms_v_pages__insert_instead" AS ON INSERT TO "public"."cms_v_pages"
DO INSTEAD (
     insert into cms_pages (site, kind, identifier, parent, modname,
                            owner, read_role_id, write_role_id,
                            menu_visibility, foldable, ord)
     values (new.site, new.kind, new.identifier, new.parent, new.modname,
             new.owner, new.read_role_id, new.write_role_id,
             new.menu_visibility, new.foldable, new.ord);
     update cms_pages set tree_order = cms_page_tree_order(page_id)
            where site=new.site and kind=new.kind;
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
           where site=new.site and kind=new.kind;
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

CREATE OR REPLACE RULE "cms_v_pages__delete_instead" AS ON DELETE TO "public"."cms_v_pages"
DO INSTEAD DELETE FROM public.cms_pages WHERE public.cms_pages.page_id = old.page_id;

CREATE OR REPLACE VIEW "public"."cms_v_publications" AS
SELECT pages.page_id, pages.page_key, pages.site, pages.kind, pages.lang, pages.identifier, pages.parent, pages.modname, pages.menu_visibility, pages.foldable, pages.ord, pages.tree_order, pages.owner, pages.read_role_id, pages.write_role_id, pages.published, pages.creator, pages.created, pages.published_since, pages.title_or_identifier, pages.title, pages.description, pages.content, pages._title, pages._description, pages._content, publications.author, publications.isbn, publications.cover_image, publications.illustrator, publications.publisher, publications.published_year, publications.edition, publications.notes 
FROM "public"."cms_v_pages" AS pages JOIN public.cms_publications AS publications ON pages.page_id = publications.page_id;

GRANT all ON "public".cms_v_publications TO "www-data";

CREATE OR REPLACE RULE "cms_v_publications__insert_instead" AS ON INSERT TO "public"."cms_v_publications"
DO INSTEAD (
     insert into cms_v_pages (site, kind, identifier, parent, modname,
                              owner, read_role_id, write_role_id,
                              menu_visibility, foldable, ord, lang, published,
                              creator, created, published_since,
                              title, description, content, _title, _description, _content)
     values (new.site, new.kind, new.identifier, new.parent, new.modname,
             new.owner, new.read_role_id, new.write_role_id,
             new.menu_visibility, new.foldable, new.ord,
             new.lang, new.published, new.creator, new.created, new.published_since,
             new.title, new.description, new.content,
             new._title, new._description, new._content);
     insert into cms_publications (page_id, author, isbn, cover_image, illustrator,
                                   publisher, published_year, edition, notes)
     select page_id, new.author, new.isbn, new.cover_image, new.illustrator,
            new.publisher, new.published_year, new.edition, new.notes
     from cms_pages where identifier=new.identifier and site=new.site and kind=new.kind
     returning page_id, page_id ||'.'|| (select min(lang) from cms_page_texts
        where page_id=cms_publications.page_id), null::text,
       null::text, null::char(2), null::text, null::int, null::text, null::text, null::boolean,
       null::int, null::text, null::int, null::name, null::name,
       null::bool, null::int, null::timestamp, null::timestamp, null::text, null::text,
       null::text, null::text, null::text, null::text, null::text,
       author, isbn, cover_image, illustrator,
       publisher, published_year, edition, notes;
        );

CREATE OR REPLACE RULE "cms_v_publications__update_instead" AS ON UPDATE TO "public"."cms_v_publications"
DO INSTEAD (
    update cms_v_pages set
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

CREATE OR REPLACE RULE "cms_v_publications__delete_instead" AS ON DELETE TO "public"."cms_v_publications"
DO INSTEAD (
     delete from cms_pages where page_id = old.page_id;
        );

CREATE OR REPLACE FUNCTION "public"."cms_f_all_user_roles"("uid_" INTEGER) RETURNS SETOF NAME LANGUAGE sql stable AS $$
select role_id from a_user_roles where ($1 is null and uid is null) or ($1 is not null and uid=$1);
$$;

COMMENT ON FUNCTION "public"."cms_f_all_user_roles"("uid_" INTEGER) IS 'Return all user''s roles and their included roles.
    Both explicitly assigned and implicit roles (such as ''anyone'') are considered.';

CREATE OR REPLACE FUNCTION "public"."cms_f_role_member"("uid_" INTEGER, "role_id_" NAME) RETURNS BOOLEAN LANGUAGE plpgsql stable AS $$
begin
  if role_id_ is null then
    return False;
  else
    return role_id_ in (select cms_f_all_user_roles(uid_));
  end if;
end;
$$;
