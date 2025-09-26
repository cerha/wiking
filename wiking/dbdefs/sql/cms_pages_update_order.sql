begin
  if new.ord is null then
    new.ord := coalesce((select max(ord)+1 from cms_pages
                         where site = new.site and kind = new.kind
                         and coalesce(parent, 0)=coalesce(new.parent, 0)), 1);
  else
    -- This trigger has a problem with the order of application of changes
    -- during the recursion.  When the modified page 'ord' is smaller than the
    -- original and there are no empty ord slots in between the old and new
    -- value, the following statement recourses up the the initially modified
    -- row and the final value is the value set by the statement rather than
    -- new.ord of the original call (the intended new value).  The work around
    -- is to set the ord to zero first in the page update rule.
    if (select count(*) from cms_pages where
                -- prevent firing f_update_cached_tables_after when there is no change
               site = new.site and kind = new.kind and coalesce(parent, 0) = coalesce(new.parent, 0)
               and ord = new.ord and page_id != new.page_id) > 0 then
      update cms_pages set ord=ord+1
      where site = new.site and kind = new.kind and coalesce(parent, 0) = coalesce(new.parent, 0)
             and ord = new.ord and page_id != new.page_id;
    end if;
  end if;
  return new;
end;
