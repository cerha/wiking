
CREATE OR REPLACE FUNCTION _parent_publication(page_id_ INTEGER) RETURNS integer LANGUAGE plpgsql stable AS $$
declare
  page cms_pages;
  parent cms_pages;
begin
  select * into page from cms_pages where page_id=page_id_;
  if page.kind = 'publication' then
     return page.page_id;
  end if;
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
update cms_page_attachments a set filename = 'xxx-' || x.rank::text || '-' || filename
from (
select distinct a.attachment_id, 
       rank() OVER (PARTITION BY a.filename||'::'||_parent_publication(a.page_id) ORDER BY a.page_id)
from cms_page_attachments a
join cms_page_attachments b
on a.filename = b.filename
and a.attachment_id != b.attachment_id
and _parent_publication(a.page_id) is not null
and _parent_publication(a.page_id) = _parent_publication(b.page_id)
) as x
where a.attachment_id=x.attachment_id and x.rank!=1;

update cms_page_attachments set page_id = _parent_publication(page_id)
where _parent_publication(page_id) is not null and page_id != _parent_publication(page_id);

drop FUNCTION _parent_publication(page_id_ INTEGER);
