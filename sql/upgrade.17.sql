create table roles (
       role_id name primary key,
       name text,
       system boolean not null default 'f'
);

create table role_sets (
       role_set_id serial primary key,
       role_id name not null references roles on update cascade on delete cascade,
       member_role_id name not null references roles on update cascade on delete cascade,
       unique (role_id, member_role_id)
);
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

create or replace function expanded_role (role_id name) returns setof name as $$
declare
  row record;
begin
  return next role_id;
  for row in select member_role_id from role_sets where role_sets.role_id=role_id loop
    return query select expanded_role (row.member_role_id);
  end loop;
  return;
end;
$$ language plpgsql stable;

create or replace function unrelated_roles (role_id name) returns setof roles as $$
select * from roles where roles.role_id not in (select expanded_role($1)) and
                          $1 not in (select expanded_role(roles.role_id));
$$ language sql stable;
 
create table role_members (
       role_member_id serial primary key,
       role_id name not null references roles on update cascade on delete cascade,
       uid int not null references users on update cascade on delete cascade,
       unique (role_id, uid)
);

alter table users add column state text not null default 'new';
update users set state=role;
alter table users drop column role;

insert into roles (role_id, system) values ('user_admin', 't');
insert into roles (role_id, system) values ('content_admin', 't');
insert into roles (role_id, system) values ('settings_admin', 't');
insert into roles (role_id, system) values ('mail_admin', 't');
insert into roles (role_id, system) values ('style_admin', 't');
insert into roles (role_id, system) values ('admin', 't');

insert into role_sets (role_id, member_role_id) values ('admin', 'user_admin');
insert into role_sets (role_id, member_role_id) values ('admin', 'content_admin');
insert into role_sets (role_id, member_role_id) values ('admin', 'settings_admin');
insert into role_sets (role_id, member_role_id) values ('admin', 'mail_admin');
insert into role_sets (role_id, member_role_id) values ('admin', 'style_admin');

create function upgrade17() returns void as $$
declare
  row record;
  role_id name;
begin
  for row in select uid, state from users where state not in ('none', 'disa', 'user', 'cont') loop
    if row.state = 'admn' then
      role_id := 'admin';
    else
	if row.state = 'auth' then
	  role_id := 'content_admin';
	else
	  role_id := row.state;
	end if;
    end if;
    begin
      execute 'insert into roles (role_id, system) values ($1, True)' using role_id;
    exception when unique_violation then
    end;
    execute 'insert into role_members (role_id, uid) values ($1, $2)' using role_id, row.uid;
    execute 'update users set state=''enabled'' where uid=$1' using row.uid;
  end loop;
end;
$$ language plpgsql;
select upgrade17();
drop function upgrade17();

update users set state='new' where state='none' and regexpire is not null;
update users set state='unapproved' where state='none';
update users set state='enabled' where state in ('cont', 'user');
update users set state='disabled' where state='disa';

alter table email_spool add column role_id name references roles on update cascade on delete cascade;
update email_spool set role_id=role where role != '_all';
alter table email_spool drop column role;

alter table users drop column organization;
alter table users drop column organization_id;
drop table organizations;
