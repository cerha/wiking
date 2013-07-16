declare
  parent_tree_order text := '';
begin
  if new.in_reply_to is not null then
    parent_tree_order := (select tree_order||'.' from cms_discussions where comment_id=new.in_reply_to);
  end if;
  new.tree_order := parent_tree_order || to_char(new.comment_id, 'FM000000000');
  return new;
end;
