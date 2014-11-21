declare
  next_array text[] := visited_array || array[role_id_];
  next_id text;
begin
  if role_id_ = any(visited_array) then
    return false;
  end if;
  if (select visited from _cycle_check where role_id = role_id_) then
    return true;
  end if;
  for next_id in select member_role_id from role_sets where role_id = role_id_ loop
    if not role_sets_cycle_check_visit(next_id, next_array) then
      return false;
    end if;
  end loop;
  update _cycle_check set visited=true where role_id = role_id_;
  return true;
end;
