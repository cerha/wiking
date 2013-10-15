DROP VIEW "public"."cms_v_publications";
DROP VIEW "public"."cms_v_pages";

CREATE OR REPLACE VIEW "public"."cms_v_pages" AS
SELECT CAST(p.page_id AS TEXT) || '.' || l.lang AS page_key, p.site, p.kind, l.lang, p.page_id, p.identifier, p.parent, p.modname, p.menu_visibility, p.foldable, p.ord, p.tree_order, p.owner, p.read_role_id, p.write_role_id, coalesce(t.published, False) AS published, t.creator, t.created, t.published_since, coalesce(t.title, p.identifier) AS title_or_identifier, t.title, t.description, t.content, t._title, t._description, t._content, cu.login AS creator_login, cu.user_ AS creator_name, ou.login AS owner_login, ou.user_ AS owner_name 
FROM public.cms_pages AS p JOIN public.cms_languages AS l ON 1 = 1 LEFT OUTER JOIN public.cms_page_texts AS t ON t.page_id = p.page_id AND t.lang = l.lang LEFT OUTER JOIN public.users AS cu ON cu.uid = t.creator LEFT OUTER JOIN public.users AS ou ON ou.uid = p.owner;

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
       _description, _content, null::varchar(64), null::text, null::varchar(64), null::text;
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
           where site = new.site and tree_order != cms_page_tree_order(page_id);
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
SELECT pages.page_id, pages.page_key, pages.site, pages.kind, pages.lang, pages.identifier, pages.parent, pages.modname, pages.menu_visibility, pages.foldable, pages.ord, pages.tree_order, pages.owner, pages.read_role_id, pages.write_role_id, pages.published, pages.creator, pages.created, pages.published_since, pages.title_or_identifier, pages.title, pages.description, pages.content, pages._title, pages._description, pages._content, pages.creator_login, pages.creator_name, pages.owner_login, pages.owner_name, publications.author, publications.isbn, publications.cover_image, publications.illustrator, publications.publisher, publications.published_year, publications.edition, publications.notes, attachments.filename AS cover_image_filename 
FROM "public"."cms_v_pages" AS pages JOIN public.cms_publications AS publications ON publications.page_id = pages.page_id LEFT OUTER JOIN public.cms_page_attachments AS attachments ON attachments.attachment_id = publications.cover_image;

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
       null::varchar(64), null::text, null::varchar(64), null::text,
       author, isbn, cover_image, illustrator,
       publisher, published_year, edition, notes, null::text;
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

