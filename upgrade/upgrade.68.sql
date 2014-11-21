SET SEARCH_PATH TO "public";

CREATE OR REPLACE FUNCTION "public"."role_sets_cycle_check_visit"("role_id_" TEXT, "visited_array" TEXT[]) RETURNS BOOLEAN LANGUAGE plpgsql AS $$
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
$$;


SET SEARCH_PATH TO "public";

CREATE OR REPLACE FUNCTION "public"."role_sets_cycle_check"() RETURNS BOOLEAN LANGUAGE plpgsql AS $$
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
$$;

