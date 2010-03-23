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
 
create table role_members (
       role_member_id serial primary key,
       role_id name not null references roles on update cascade on delete cascade,
       uid int not null references users on update cascade on delete cascade,
       unique (role_id, uid)
);

alter table users add column state text not null default 'none';
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
    execute 'insert into role_users (role_id, uid) values ($1, $2)' using role_id, row.uid;
    execute 'update users set state=''user'' where uid=$1' using row.uid;
  end loop;
end;
$$ language plpgsql;
select upgrade17();
drop function upgrade17();

update users set state='user' where state='cont';

alter table email_spool add column role_id name references roles on update cascade on delete cascade;
update email_spool set role_id=role;
alter table email_spool drop column role;
