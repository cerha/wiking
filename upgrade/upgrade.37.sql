create or replace view cms_v_page_attachments
as select a.attachment_id  ||'.'|| l.lang as attachment_key, l.lang,
  a.attachment_id, a.page_id, t.title, t.description,
  a.filename, a.mime_type, a.bytesize,
  a.image, a.thumbnail, a.thumbnail_size, a.thumbnail_width, a.thumbnail_height,
  a.in_gallery, a.listed, a.author, a."location", a.width, a.height, a."timestamp"
from cms_page_attachments a cross join cms_languages l
     left outer join cms_page_attachment_texts t using (attachment_id, lang);
