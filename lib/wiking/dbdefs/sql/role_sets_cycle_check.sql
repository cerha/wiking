declare
  unvisited text;
begin
  create temp table if not exists _cycle_check (role_id name, visited bool);
  truncate _cycle_check;
  insert into _cycle_check select distinct role_id, false as visited from role_sets;
  loop
    select role_id into unvisited from _cycle_check where not visited;
    exit when unvisited is null;
    if not role_sets_cycle_check_visit(unvisited, '{}') then
      return false;
    end if;
  end loop;
  return true;
end;
