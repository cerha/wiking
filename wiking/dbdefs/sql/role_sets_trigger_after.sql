begin
  if tg_op != 'DELETE' and not role_sets_cycle_check() then
    raise exception 'cycle in role sets';
  end if;
  return null;
end;
