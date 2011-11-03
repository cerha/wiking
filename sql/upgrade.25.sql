alter table _attachments add column image bytea;
alter table _attachments add column thumbnail bytea;
alter table _attachments add column thumbnail_size text;
alter table _attachments add column thumbnail_width int;
alter table _attachments add column thumbnail_height int;

drop view attachments;

create or replace view attachments
as select a.attachment_id  ||'.'|| l.lang as attachment_variant_id, l.lang,
  a.attachment_id, a.mapping_id, a.filename, a.mime_type, a.bytesize, 
  a.image, a.thumbnail, a.thumbnail_size, a.thumbnail_width, a.thumbnail_height,
  a.listed, a."timestamp", d.title, d.description, i.width is not null as is_image,
  i.width, i.height, i.author, i."location", i.exif_date, i.exif
from _attachments a JOIN _mapping m using (mapping_id) cross join languages l
     left outer join _attachment_descr d using (attachment_id, lang)
     left outer join _images i using (attachment_id);

create or replace rule attachments_insert as
 on insert to attachments do instead (
    insert into _attachment_descr (attachment_id, lang, title, description)
           select new.attachment_id, new.lang, new.title, new.description
           where new.title IS not null OR new.description IS not null;
    insert into _images (attachment_id, width, height, author, "location", exif_date, exif)
           select new.attachment_id, new.width, new.height, new.author, new."location",
                  new.exif_date, new.exif
           where new.is_image;
    insert into _attachments (attachment_id, mapping_id, filename, mime_type, bytesize, 
                              image, thumbnail, thumbnail_size, thumbnail_width, thumbnail_height,
                              listed)
           VALUES (new.attachment_id, new.mapping_id, new.filename, new.mime_type,
                   new.bytesize, new.image, new.thumbnail, new.thumbnail_size,
                   new.thumbnail_width, new.thumbnail_height, new.listed)
           returning
             attachment_id ||'.'|| (select max(lang) from _attachment_descr
                                    where attachment_id=attachment_id),  NULL::char(2),
             attachment_id, mapping_id, filename, mime_type, bytesize, image,
             thumbnail, thumbnail_size, thumbnail_width, thumbnail_height, listed,
             "timestamp", NULL::text, NULL::text, NULL::boolean, NULL::int, 
             NULL::int, NULL::text, NULL::text, NULL::timestamp, NULL::text
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
           listed = new.listed
           where attachment_id = old.attachment_id;
    UPDATE _images SET
           width = new.width,
           height = new.height,
           author = new.author,
           "location" = new."location",
           exif_date = new.exif_date,
           exif = new.exif
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
