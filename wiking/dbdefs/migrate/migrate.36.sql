drop function expanded_role(role_id name);
create or replace function expanded_role (role_id_ name) returns setof name as $$
declare
  row record;
begin
  return next role_id_;
  for row in select member_role_id from role_sets where role_sets.role_id=role_id_ loop
    return query select * from expanded_role (row.member_role_id);
  end loop;
  return;
end;
$$ language plpgsql stable;

create table a_user_roles (
       uid int references users on update cascade on delete cascade,
       role_id name not null references roles on update cascade on delete cascade
);
create index a_user_roles_uid_index on a_user_roles (uid);
grant all on a_user_roles to "www-data";

create or replace function update_user_roles () returns trigger as $$
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
  return null;
end;
$$ language plpgsql;

create trigger role_sets_update_user_roles_trigger after insert or update or delete on role_sets
for each statement execute procedure update_user_roles ();
create trigger role_members_update_user_roles_trigger after insert or update or delete on role_members
for each statement execute procedure update_user_roles ();

-- Force triggers
update role_sets set role_id='admin' where role_id='admin';
