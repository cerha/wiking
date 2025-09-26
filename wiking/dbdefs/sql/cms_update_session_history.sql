begin
  if tg_op = 'INSERT' then
     insert into cms_session_history (session_id, auth_type, uid, start_time)
     values (new.session_id, new.auth_type, new.uid, new.last_access);
     return new;
  end if;
  if tg_op = 'DELETE' then
     update cms_session_history set end_time=old.last_access where session_id=old.session_id;
     return old;
  end if;
end;
