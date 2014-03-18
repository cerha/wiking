alter table cms_page_attachments add column bytesize_ int;
update cms_page_attachments set 
       bytesize_ = split_part(bytesize, ' ', 1)::float * 
                   case when split_part(bytesize, ' ', 2) = 'B' then 1
                   when split_part(bytesize, ' ', 2) = 'kB' then 1024
		   when split_part(bytesize, ' ', 2) = 'MB' then 1024*1024
		   when split_part(bytesize, ' ', 2) = 'GB' then 1024*1024*1024 end::int;
alter table cms_page_attachments drop column bytesize cascade;
alter table cms_page_attachments rename column bytesize_ to bytesize;
alter table cms_page_attachments alter column bytesize set not null;

CREATE OR REPLACE VIEW "public"."cms_v_page_attachments" AS
SELECT CAST(a.attachment_id AS TEXT) || '.' || l.lang AS attachment_key, l.lang, a.attachment_id, a.page_id, t.title, t.description, a.filename, a.mime_type, a.bytesize, a.image, a.thumbnail, a.thumbnail_size, a.thumbnail_width, a.thumbnail_height, a.in_gallery, a.listed, a.author, a.location, a.width, a.height, a.created, a.last_modified 
FROM public.cms_page_attachments AS a JOIN public.cms_languages AS l ON 1 = 1 LEFT OUTER JOIN public.cms_page_attachment_texts AS t ON a.attachment_id = t.attachment_id AND l.lang = t.lang;

GRANT all ON "public".cms_v_page_attachments TO "www-data";

CREATE OR REPLACE RULE "cms_v_page_attachments__insert_instead" AS ON INSERT TO "public"."cms_v_page_attachments"
DO INSTEAD (
    insert into cms_page_attachment_texts (attachment_id, lang, title, description)
           select new.attachment_id, new.lang, new.title, new.description
           where new.title is not null OR new.description is not null;
    insert into cms_page_attachments (attachment_id, page_id, filename, mime_type, bytesize, image,
                                 thumbnail, thumbnail_size, thumbnail_width, thumbnail_height,
                                 in_gallery, listed, author, "location", width, height,
                                 created, last_modified)
           values (new.attachment_id, new.page_id, new.filename, new.mime_type,
                   new.bytesize, new.image, new.thumbnail, new.thumbnail_size,
                   new.thumbnail_width, new.thumbnail_height, new.in_gallery, new.listed,
                   new.author, new."location", new.width, new.height,
                   new.created, new.last_modified)
           returning
             attachment_id ||'.'|| (select max(lang) from cms_page_attachment_texts
                                    where attachment_id=attachment_id), null::char(2),
             attachment_id, page_id, null::text, null::text,
             filename, mime_type, bytesize, image, thumbnail,
             thumbnail_size, thumbnail_width, thumbnail_height, in_gallery, listed,
             author, "location", width, height, created, last_modified
        );

CREATE OR REPLACE RULE "cms_v_page_attachments__update_instead" AS ON UPDATE TO "public"."cms_v_page_attachments"
DO INSTEAD (
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
           created = new.created,
           last_modified = new.last_modified
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

CREATE OR REPLACE RULE "cms_v_page_attachments__delete_instead" AS ON DELETE TO "public"."cms_v_page_attachments"
DO INSTEAD (
     delete from cms_page_attachments where attachment_id = old.attachment_id;
        );

