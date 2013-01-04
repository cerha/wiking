drop view cms_v_pages;
drop view cms_v_page_attachments;
drop view cms_v_panels;
alter table cms_pages alter column identifier type text;
alter table cms_page_attachments alter column filename type text;
alter table cms_panels alter column identifier type text;

create or replace view cms_v_pages as
select p.page_id ||'.'|| l.lang as page_key, p.site, l.lang,
       p.page_id, p.identifier, p.parent, p.modname,
       p.menu_visibility, p.foldable, p.ord, p.tree_order,
       p.read_role_id, p.write_role_id,
       coalesce(t.published, false) as published,
       coalesce(t.title, p.identifier) as title_or_identifier,
       t.title, t.description, t.content, t._title, t._description, t._content
from cms_pages p cross join cms_languages l
     left outer join cms_page_texts t using (page_id, lang);

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
       lang, page_id, null::text, null::int, null::text, null::text, null::boolean,
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

create or replace rule cms_v_pages_delete as
  on delete to cms_v_pages do instead (
     delete from cms_pages where page_id = old.page_id;
);

create or replace view cms_v_page_attachments
as select a.attachment_id  ||'.'|| l.lang as attachment_key, l.lang,
  a.attachment_id, a.page_id, t.title, t.description,
  a.filename, a.mime_type, a.bytesize,
  a.image, a.thumbnail, a.thumbnail_size, a.thumbnail_width, a.thumbnail_height,
  a.in_gallery, a.listed, a.author, a."location", a.width, a.height, a."timestamp"
from cms_page_attachments a cross join cms_languages l
     left outer join cms_page_attachment_texts t using (attachment_id, lang);

create or replace rule cms_v_page_attachments_insert as
 on insert to cms_v_page_attachments do instead (
    insert into cms_page_attachment_texts (attachment_id, lang, title, description)
           select new.attachment_id, new.lang, new.title, new.description
           where new.title is not null OR new.description is not null;
    insert into cms_page_attachments (attachment_id, page_id, filename, mime_type, bytesize, image,
                                 thumbnail, thumbnail_size, thumbnail_width, thumbnail_height,
                                 in_gallery, listed, author, "location", width, height, "timestamp")
           values (new.attachment_id, new.page_id, new.filename, new.mime_type,
                   new.bytesize, new.image, new.thumbnail, new.thumbnail_size,
                   new.thumbnail_width, new.thumbnail_height, new.in_gallery, new.listed,
                   new.author, new."location", new.width, new.height, new."timestamp")
           returning
             attachment_id ||'.'|| (select max(lang) from cms_page_attachment_texts
                                    where attachment_id=attachment_id), null::char(2),
             attachment_id, page_id, null::text, null::text,
             filename, mime_type, bytesize, image, thumbnail,
             thumbnail_size, thumbnail_width, thumbnail_height, in_gallery, listed,
             author, "location", width, height, "timestamp"
);

create or replace rule cms_v_page_attachments_update as
 on update to cms_v_page_attachments do instead (
    update cms_page_attachments set
           page_id = new.page_id,
           filename = new.filename,
           mime_type = new.mime_type,
           bytesize = new.bytesize,
           image = new.image,
           thumbnail = new.thumbnail,
           thumbnail_size = new.thumbnail_size,
           thumbnail_width = new.thumbnail_width,
           thumbnail_height = new.thumbnail_height,
           listed = new.listed,
           in_gallery = new.in_gallery,
           author = new.author,
           "location" = new."location",
           width = new.width,
           height = new.height,
	   "timestamp" = new."timestamp"
           where attachment_id = old.attachment_id;
    update cms_page_attachment_texts set
           title=new.title,
           description=new.description
           where attachment_id = old.attachment_id and lang = old.lang;
    insert into cms_page_attachment_texts (attachment_id, lang, title, description)
           select new.attachment_id, new.lang, new.title, new.description
           where old.attachment_id not in
             (select attachment_id from cms_page_attachment_texts where lang=old.lang);
);

create or replace rule cms_v_page_attachments_delete as
  on delete to cms_v_page_attachments do instead (
     delete from cms_page_attachments where attachment_id = old.attachment_id;
);

create or replace view cms_v_panels as
select cms_panels.*, cms_pages.modname, cms_pages.read_role_id
from cms_panels left outer join cms_pages using (page_id);

create or replace rule cms_v_panels_insert as
  on insert to cms_v_panels do instead (
     insert into cms_panels
        (site, lang, identifier, title, ord, page_id, size, content, _content, published)
     values
        (new.site, new.lang, new.identifier, new.title, new.ord, new.page_id, new.size,
	 new.content, new._content, new.published)
);

create or replace rule cms_v_panels_update as
  on update to cms_v_panels do instead (
    update cms_panels set
      site = new.site,
      lang = new.lang,
      identifier = new.identifier,
      title = new.title,
      ord = new.ord,
      page_id = new.page_id,
      size = new.size,
      content = new.content,
      _content = new._content,
      published = new.published
    where panel_id = old.panel_id;
);

create or replace rule cms_v_panels_delete as
  on delete to cms_v_panels do instead (
     delete from cms_panels where panel_id = old.panel_id;
);
