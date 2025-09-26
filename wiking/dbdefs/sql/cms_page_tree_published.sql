select
  case when $1 is null then true else
     (select case when published then cms_page_tree_published(parent, $2) else false end
      from cms_pages join cms_page_texts using (page_id) where page_id=$1 and lang=$2)
  end
as result
