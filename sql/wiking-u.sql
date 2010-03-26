-- Untrusted definitions, to be imported by a PostgreSQL superuser

create or replace function role_sets_cycle_check () returns bool
as '    connections = {}
    unvisited = {}
    for row in plpy.execute("select role_id, member_role_id from role_sets"):
        role_id, member_role_id = row[''role_id''], row[''member_role_id'']
        edges = connections.get(role_id)
        if edges is None:
            edges = connections[role_id] = []
            unvisited[role_id] = True
        edges.append(member_role_id)
    def dfs(node):
        unvisited[node] = False
        for next in connections[node]:
            status = unvisited.get(next)
            if status is None:
                continue
            if status is False or not dfs(next):
                return False
        del unvisited[node]
        return True
    while unvisited:
        if not dfs(unvisited.keys()[0]):
            return False
    return True
' language plpythonu;
create or replace function role_sets_trigger_after() returns trigger as $$
begin
  if tg_op != 'DELETE' and not role_sets_cycle_check() then
    raise exception 'cycle in role sets';
  end if;
  return null;
end;
$$ language plpgsql;
create trigger role_sets_trigger_after after insert or update or delete on role_sets
for each statement execute procedure role_sets_trigger_after();
