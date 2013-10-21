
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

update cms_page_attachments a set filename = page_id::text || '-' || filename where filename in (select filename from cms_page_attachments where page_id=_parent_publication(a.page_id));
update cms_page_attachments set page_id=_parent_publication(page_id) where _parent_publication(page_id) is not null;

drop FUNCTION _parent_publication(page_id_ INTEGER);
