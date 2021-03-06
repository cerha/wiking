declare
  uid_ int;
  role_id_ name;
begin
  truncate a_user_roles;
  for uid_ in select uid from users union select null loop
    for role_id_ in select role_id from role_members where uid=uid_ union select unnest(array['anyone', 'authenticated']) loop
      insert into a_user_roles (select uid_, * from expanded_role(role_id_));
    end loop;
  end loop;
  perform f_update_cached_tables('public', 'a_user_roles', 'true');
  return null;
end;
