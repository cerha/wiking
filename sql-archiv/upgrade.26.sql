drop view attachments;
drop table _images;
alter table _attachments drop column "timestamp";
alter table _attachments add column in_gallery boolean not null default false;
alter table _attachments add column author text;
alter table _attachments add column "location" text;
alter table _attachments add column width int;
alter table _attachments add column height int;
alter table _attachments add column "timestamp" timestamp;

create or replace view attachments
as select a.attachment_id  ||'.'|| l.lang as attachment_variant_id, l.lang,
  a.attachment_id, a.mapping_id, d.title, d.description,
  a.filename, a.mime_type, a.bytesize,
  a.image, a.thumbnail, a.thumbnail_size, a.thumbnail_width, a.thumbnail_height,
  a.in_gallery, a.listed, a.author, a."location", a.width, a.height, a."timestamp"
from _attachments a JOIN _mapping m using (mapping_id) cross join languages l
     left outer join _attachment_descr d using (attachment_id, lang);

create or replace rule attachments_insert as
 on insert to attachments do instead (
    insert into _attachment_descr (attachment_id, lang, title, description)
           select new.attachment_id, new.lang, new.title, new.description
           where new.title IS not null OR new.description IS not null;
    insert into _attachments (attachment_id, mapping_id, filename, mime_type, bytesize,
                              image, thumbnail, thumbnail_size, thumbnail_width, thumbnail_height,
                              in_gallery, listed, author, "location", width, height, "timestamp")
           VALUES (new.attachment_id, new.mapping_id, new.filename, new.mime_type,
                   new.bytesize, new.image, new.thumbnail, new.thumbnail_size,
                   new.thumbnail_width, new.thumbnail_height, new.in_gallery, new.listed,
                   new.author, new."location", new.width, new.height, new."timestamp")
           returning
             attachment_id ||'.'|| (select max(lang) from _attachment_descr
                                    where attachment_id=attachment_id),  NULL::char(2),
             attachment_id, mapping_id, NULL::text, NULL::text,
             filename, mime_type, bytesize, image, thumbnail,
             thumbnail_size, thumbnail_width, thumbnail_height, in_gallery, listed,
             author, "location", width, height, "timestamp"
);

create or replace rule attachments_update as
 on UPDATE to attachments do instead (
    UPDATE _attachments SET
           mapping_id = new.mapping_id,
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
    UPDATE _attachment_descr SET title=new.title, description=new.description
           where attachment_id = old.attachment_id and lang = old.lang;
    insert into _attachment_descr (attachment_id, lang, title, description)
           select new.attachment_id, new.lang, new.title, new.description
           where old.attachment_id NOT IN
             (select attachment_id from _attachment_descr where lang=old.lang);
);

create or replace rule attachments_delete as
  on delete to attachments do instead (
     delete from _attachments where attachment_id = old.attachment_id;
);

