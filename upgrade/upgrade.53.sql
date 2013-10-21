
CREATE OR REPLACE FUNCTION _parent_publication(page_id_ INTEGER) RETURNS integer LANGUAGE plpgsql stable AS $$
declare
  page cms_pages;
  parent cms_pages;
begin
  select * into page from cms_pages where page_id=page_id_;
  if page.kind != 'chapter' then
     return null;
  end if;
  select * into parent from cms_pages where page_id=page.parent;
  if parent.kind = 'publication' then
     return parent.page_id;
  end if;
  if parent.kind = 'chapter' then
     return _parent_publication(parent.page_id);
  end if;
  return null;
end;
$$;

-- Rename duplicate attachments (same file in multiple chapters) as we can not delete
-- them here because this would leave stray files on the disk.
update cms_page_attachments a set filename = 'xxx-' || page_id::text || '-' || filename
from (select a.attachment_id
      from cms_page_attachments a
      join cms_page_attachments b
      on a.filename=b.filename
      and _parent_publication(a.page_id) in (_parent_publication(b.page_id), b.page_id)
) as x
where a.attachment_id=x.attachment_id;

drop FUNCTION _parent_publication(page_id_ INTEGER);
