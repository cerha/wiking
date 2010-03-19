create table roles (
       role_id name primary key,
       description text,
       system boolean not null default 'f'
);

create table role_members (
       role_id name references roles,
       member name references roles,
       unique (role_id, member)
);
 
create table role_users (
       role_id name references roles,
       uid int references users,
       unique (role_id, uid)
);

alter table users rename column role to state;

insert into roles (role_id, system) values ('user_admin', 't');
insert into roles (role_id, system) values ('content_admin', 't');
insert into roles (role_id, system) values ('settings_admin', 't');
insert into roles (role_id, system) values ('mail_admin', 't');
insert into roles (role_id, system) values ('style_admin', 't');
insert into roles (role_id, system) values ('admin', 't');

create view user_roles as
select role_users.uid, roles.role_id, roles.name, roles.system
from role_users join roles on role_users.role_id = roles.role_id;

create function upgrade17() returns void as $$
declare
  row record;
  role_id name;
begin
  for row in select uid, state from users where state not in ('none', 'disa', 'user') loop
    if row.state = 'admn' then
      role_id := 'admin';
    else
      role_id := row.state;
    end if;
    begin
      execute 'insert into roles (role_id, system) values ($1, True)' using role_id;
    exception when unique_violation then
    end;
    execute 'insert into role_users (role_id, uid) values ($1, $2)' using role_id, row.uid;
    execute 'update users set state=''user'' where uid=$1' using row.uid;
  end loop;
end;
$$ language plpgsql;
select upgrade17();
drop function upgrade17();

alter table email_spool add column role_id name references roles on update cascade on delete cascade;
update email_spool set role_id=role;
alter table email_spool drop column role;
