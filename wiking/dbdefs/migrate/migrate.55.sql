DROP VIEW "public"."cms_v_publications";

ALTER TABLE public.cms_publications ADD COLUMN copyright_notice TEXT;

CREATE OR REPLACE VIEW "public"."cms_v_publications" AS
SELECT pages.page_id, pages.page_key, pages.site, pages.kind, pages.lang, pages.identifier, pages.parent, pages.modname, pages.menu_visibility, pages.foldable, pages.ord, pages.tree_order, pages.owner, pages.read_role_id, pages.write_role_id, pages.published, pages.creator, pages.created, pages.published_since, pages.title_or_identifier, pages.title, pages.description, pages.content, pages._title, pages._description, pages._content, pages.creator_login, pages.creator_name, pages.owner_login, pages.owner_name, publications.author, publications.isbn, publications.cover_image, publications.illustrator, publications.publisher, publications.published_year, publications.edition, publications.copyright_notice, publications.notes, attachments.filename AS cover_image_filename 
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
                                   publisher, published_year, edition, copyright_notice, notes)
     select page_id, new.author, new.isbn, new.cover_image, new.illustrator,
            new.publisher, new.published_year, new.edition, new.copyright_notice, new.notes
     from cms_pages where identifier=new.identifier and site=new.site and kind=new.kind
     returning page_id, page_id ||'.'|| (select min(lang) from cms_page_texts
        where page_id=cms_publications.page_id), null::text,
       null::text, null::char(2), null::text, null::int, null::text, null::text, null::boolean,
       null::int, null::text, null::int, null::name, null::name,
       null::bool, null::int, null::timestamp, null::timestamp, null::text, null::text,
       null::text, null::text, null::text, null::text, null::text,
       null::varchar(64), null::text, null::varchar(64), null::text,
       author, isbn, cover_image, illustrator,
       publisher, published_year, edition, copyright_notice, notes, null::text;
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
        copyright_notice = new.copyright_notice,
        notes = new.notes
    where page_id = old.page_id;
        );

CREATE OR REPLACE RULE "cms_v_publications__delete_instead" AS ON DELETE TO "public"."cms_v_publications"
DO INSTEAD (
     delete from cms_pages where page_id = old.page_id;
        );

