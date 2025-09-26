declare
  row record;
begin
  return next role_id_;
  for row in select member_role_id from role_sets where role_sets.role_id=role_id_ loop
    return query select * from expanded_role (row.member_role_id);
  end loop;
  return;
end;
