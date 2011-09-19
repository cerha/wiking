-- Remember to install the pgcrypto module first. To do that on debian-based systems,
-- install the `postgresql-contrib' package and then run (substitute "8.4" with your
-- PostgreSQL version and "brailshop.squeeze.pioneer" with your database server):
-- su -c 'psql -1f /usr/share/postgresql/8.4/contrib/pgcrypto.sql brailshop.squeeze.pioneer' postgres

create table cms_crypto_names (
       name text primary key,
       description text
);
grant all on cms_crypto_names to "www-data";

create table cms_crypto_keys (
       key_id serial primary key,
       name text not null references cms_crypto_names on update cascade on delete cascade,
       uid int not null references users on update cascade on delete cascade,
       key bytea not null,
       unique (name, uid)
);
grant all on cms_crypto_keys to "www-data";
grant all on cms_crypto_keys_key_id_seq to "www-data";

create or replace function cms_crypto_extract_key (encrypted bytea, psw text) returns text as $$
declare
  key text;
begin
  begin
    key := pgp_sym_decrypt(encrypted, psw);
  exception
    when OTHERS then
      return null;
  end;
  if substring(key for 7) != 'wiking:' then
    return null;
  end if;
  return substring(key from 8);
end;
$$ language plpgsql immutable;

create or replace function cms_crypto_store_key (key text, psw text) returns bytea as $$
-- This a PL/pgSQL, and not SQL, function in order to prevent direct dependency on pg_crypto.
begin
  return pgp_sym_encrypt('wiking:'||$1, $2);
end;
$$ language plpgsql immutable;

create or replace function cms_crypto_insert_key (name_ text, uid_ int, key_ text, psw text) returns bool as $$
begin
  lock cms_crypto_keys in exclusive mode;
  if (select count(*) from cms_crypto_keys where name=name_ and uid=uid_) > 0 then
    return False;
  end if;
  insert into cms_crypto_keys (name, uid, key) values (name_, uid_, cms_crypto_store_key(key_, psw));
  return True;
end;
$$ language plpgsql;

create or replace function cms_crypto_change_password (id_ int, old_psw text, new_psw text) returns bool as $$
declare
  key_ text;
begin
  lock cms_crypto_keys in exclusive mode;
  begin
    select cms_crypto_extract_key(key, $2) into key_ from cms_crypto_keys where key_id=$1;
  exception
    when OTHERS then
      key_ := null;
  end;
  if key_ is null then
    return False;
  end if;
  update cms_crypto_keys set key=cms_crypto_store_key(key_, $3) where key_id=$1;
  return True;
end;
$$ language plpgsql;

create or replace function cms_crypto_copy_key (name_ text, from_uid int, to_uid int, from_psw text, to_psw text) returns bool as $$
declare
  key_ text;
begin
  lock cms_crypto_keys in exclusive mode;
  begin
    select cms_crypto_extract_key(key, from_psw) into key_ from cms_crypto_keys where name=name_ and uid=from_uid;
  exception
    when OTHERS then
      key_ := null;
  end;
  if key_ is null then
    return False;
  end if;
  delete from cms_crypto_keys where name=name_ and uid=to_uid;
  insert into cms_crypto_keys (name, uid, key) values (name_, to_uid, cms_crypto_store_key(key_, to_psw));
  return True;

  end;
$$ language plpgsql;

create or replace function cms_crypto_delete_key (name_ text, uid_ int, force bool) returns bool as $$
begin
  lock cms_crypto_keys in exclusive mode;
  if not force and (select count(*) from cms_crypto_keys where name=name_) <= 1 then
    return False;
  end if;
  delete from cms_crypto_unlocked_passwords
         where key_id in (select key_id from cms_crypto_keys where name=name_ and uid=uid_);
  delete from cms_crypto_keys where name=name_ and uid=uid_;
  return True;
end;
$$ language plpgsql;

--

create table cms_crypto_unlocked_passwords (
       key_id int not null references cms_crypto_keys on update cascade on delete cascade,
       password bytea
);
grant all on cms_crypto_unlocked_passwords to "www-data";
create or replace function cms_crypto_unlocked_passwords_insert_trigger () returns trigger as $$
begin
  delete from cms_crypto_unlocked_passwords where key_id=new.key_id;
  return new;
end;
$$ language plpgsql;
create trigger cms_crypto_unlocked_passwords_insert_trigger_before before insert on cms_crypto_unlocked_passwords
for each row execute procedure cms_crypto_unlocked_passwords_insert_trigger();

create or replace function cms_crypto_unlock_passwords (uid_ int, psw text, cookie text) returns void as $$
  insert into cms_crypto_unlocked_passwords
         (select key_id, cms_crypto_store_key(cms_crypto_extract_key(key, $2), $3)
                 from cms_crypto_keys
                 where uid=$1 and cms_crypto_extract_key(key, $2) is not null);
$$ language sql;

create or replace function cms_crypto_lock_passwords (uid_ int) returns void as $$
  delete from cms_crypto_unlocked_passwords where key_id in (select key_id from cms_crypto_keys where uid=$1);
$$ language sql;

create or replace function cms_crypto_cook_passwords (uid_ int, cookie text) returns setof text as $$
begin
  lock cms_crypto_keys in exclusive mode;
  delete from cms_crypto_unlocked_passwords
         where key_id in (select key_id from cms_crypto_keys where uid=uid_) and
               cms_crypto_extract_key(password, cookie) is null;
  begin
    delete from t_pytis_passwords;
  exception
    when undefined_table then
      create temp table t_pytis_passwords (name text, password text);
  end;
  insert into t_pytis_passwords
         (select name, cms_crypto_extract_key(cms_crypto_unlocked_passwords.password, cookie)
                 from cms_crypto_keys join cms_crypto_unlocked_passwords using (key_id) where uid=uid_);
  return query select name from t_pytis_passwords;
end;
$$ language plpgsql;

insert into roles (role_id, system, auto) values ('crypto_admin', 't', 'f');
insert into role_sets (role_id, member_role_id) values ('admin', 'crypto_admin');
