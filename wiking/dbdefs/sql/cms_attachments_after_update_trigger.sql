declare
    tree_order_matcher text := '';
begin
    if old.filename != new.filename then
       tree_order_matcher := (select tree_order || '.%' from cms_pages		  
                              where page_id=new.page_id and kind='publication');
       update cms_page_texts set
          content=replace(content, old.filename, new.filename),
          _content=replace(_content, old.filename, new.filename)
          where page_id = new.page_id or
                page_id in (select page_id from cms_pages
                            where tree_order like tree_order_matcher);
    end if;
    return null;
end;
