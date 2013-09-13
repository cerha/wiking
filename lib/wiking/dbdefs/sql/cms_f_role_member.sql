begin
  if role_id_ is null then
    return False;
  else
    return role_id_ in (select cms_f_all_user_roles(uid_));
  end if;
end;
