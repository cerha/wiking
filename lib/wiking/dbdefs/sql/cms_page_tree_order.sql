select
  case when $1 is null then '' else
    (select cms_page_tree_order(parent) || '.' || to_char(coalesce(ord, 999999), 'FM000000')
     from cms_pages where page_id=$1)
  end
as result
