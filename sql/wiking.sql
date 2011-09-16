-- Wiking database creation script. --
-- -*- indent-tabs-mode: nil -*-

set client_min_messages=WARNING;

create table languages (
	lang_id serial primary key,
	lang char(2) unique not null
);

create table countries (
	country_id serial primary key,
	country char(2) unique not null
);

-------------------------------------------------------------------------------

create table roles (
       role_id name primary key,
       name text,
       system boolean not null default 'f',
       auto boolean not null default false
);

create table role_sets (
       role_set_id serial primary key,
       role_id name not null references roles on update cascade on delete cascade,
       member_role_id name not null references roles on update cascade on delete cascade,
       unique (role_id, member_role_id)
);

create or replace function expanded_role (role_id name) returns setof name as $$
declare
  row record;
begin
  return next role_id;
  for row in select member_role_id from role_sets where role_sets.role_id=role_id loop
    return query select * from expanded_role (row.member_role_id);
  end loop;
  return;
end;
$$ language plpgsql stable;

create or replace function unrelated_roles (role_id name) returns setof roles as $$
select * from roles where roles.role_id not in (select expanded_role($1)) and
                          $1 not in (select expanded_role(roles.role_id));
$$ language sql stable;

create table users (
	uid serial primary key,
	login varchar(32) unique not null,
	password varchar(32),
	firstname text not null,
	surname text not null,
	nickname text,
	user_ text not null,
	email text not null,
	phone text,
	address text,
	uri text,
	state text not null default 'new',
        last_password_change timestamp not null,
	since timestamp not null default current_timestamp(0),
	lang char(2) references languages(lang) on update cascade on delete set null,
        regexpire timestamp,
        regcode char(16),
        certauth boolean not null default false,
        note text,
        confirm boolean not null default false
);
alter table users alter column since 
set default current_timestamp(0) at time zone 'GMT';

create table role_members (
       role_member_id serial primary key,
       role_id name not null references roles on update cascade on delete cascade,
       uid int not null references users on update cascade on delete cascade,
       unique (role_id, uid)
);

create table session (
       session_id serial primary key,
       uid int not null references users on delete cascade,
       session_key text not null,
       last_access timestamp,
       unique (uid, session_key)
);

create table _session_log (
       log_id serial primary key,
       session_id int references session on delete set null,
       uid int references users on delete cascade, -- may be null for invalid logins
       login varchar(32) not null, -- usefull when uid is null or login changes
       success bool not null,
       start_time timestamp not null,
       end_time timestamp,
       ip_address text not null,
       user_agent text,
       referer text
);

create or replace rule session_delete as on delete to session do (
       update _session_log set end_time=old.last_access WHERE session_id=old.session_id;
);

create view session_log as select 
       l.log_id,
       l.session_id,
       l.uid,
       l.login,
       l.success,
       s.session_id is not null and age(s.last_access) < '1 hour' as active,
       l.start_time,
       coalesce(l.end_time, s.last_access) - l.start_time as duration,
       l.ip_address,
       l.user_agent,
       l.referer
from _session_log l left outer join session s using (session_id);

create or replace rule session_log_insert as
  on insert to session_log do instead (
     insert into _session_log (session_id, uid, login, success, 
     	    	 	       start_time, ip_address, user_agent, referer)
            values (new.session_id, new.uid, new.login, new.success, 
	    	    new.start_time, new.ip_address, new.user_agent, new.referer)
            returning log_id, session_id, uid, login, success, NULL::boolean,
	    	      start_time, NULL::interval, ip_address, user_agent, referer;
);

-------------------------------------------------------------------------------

create table _mapping (
	mapping_id serial primary key,
	identifier varchar(32) unique not null,
	parent integer references _mapping,
	modname text,
	hidden boolean not null,
	ord int not null,
	tree_order text,
	read_role_id name not null default 'anyone' references roles on update cascade,
	write_role_id name not null default 'content_admin' references roles on update cascade on delete set default
);
create unique index _mapping_unique_tree_order on _mapping (ord, coalesce(parent, 0));

create or replace function _mapping_tree_order(mapping_id int) returns text as $$
  select
    case when $1 is null then '' else
      (select _mapping_tree_order(parent) || '.' || to_char(coalesce(ord, 999999), 'FM000000')
       from _mapping where mapping_id=$1)
    end
  as result
$$ language sql;

create or replace view mapping as select * from _mapping;

-------------------------------------------------------------------------------

create table _pages (
       mapping_id integer not null references _mapping on delete cascade,
       lang char(2) not null references languages(lang) on update cascade,
       published boolean not null default true,
       title text not null,
       description text,
       content text,
       _title text,
       _description text,
       _content text,
       primary key (mapping_id, lang)
);

create or replace view pages as 
select m.mapping_id ||'.'|| l.lang as page_id, l.lang, 
       m.mapping_id, m.identifier, m.parent, m.modname, 
       m.hidden, m.ord, m.tree_order, m.read_role_id, m.write_role_id,
       coalesce(p.published, false) as published,
       coalesce(p.title, m.identifier) as title_or_identifier, 
       p.title, p.description, p.content, p._title, p._description, p._content
from _mapping m cross join languages l
     left outer join _pages p using (mapping_id, lang);

create or replace rule pages_insert as
  on insert to pages do instead (
     insert into _mapping (identifier, parent, modname, read_role_id, write_role_id, hidden, ord)
     values (new.identifier, new.parent, new.modname, new.read_role_id, new.write_role_id, new.hidden, 
             coalesce(new.ord, (select max(ord)+100 from _mapping 
                                where coalesce(parent, 0)=coalesce(new.parent, 0)), 100));
     update _mapping set tree_order = _mapping_tree_order(mapping_id);
     insert into _pages (mapping_id, lang, published, 
                         title, description, content, _title, _description, _content)
     select (select mapping_id from _mapping where identifier=new.identifier),
            new.lang, new.published, 
            new.title, new.description, new.content, new._title, new._description, new._content
     returning mapping_id ||'.'|| lang, 
       lang, mapping_id, null::varchar(32), null::int, null::text, null::boolean, null::int, 
       null::text, null::name, null::name,
       published, title, title, description, content, _title,
       _description, _content
);

create or replace rule pages_update as
  on update to pages do instead (
    update _mapping set
        identifier = new.identifier,
        parent = new.parent,
        modname = new.modname,
        read_role_id = new.read_role_id,
        write_role_id = new.write_role_id,
        hidden = new.hidden,
        ord = new.ord
    where _mapping.mapping_id = old.mapping_id;
    update _mapping set tree_order = _mapping_tree_order(mapping_id);
    update _pages set
        published = new.published,
        title = new.title,
        description = new.description,
        content = new.content,
        _title = new._title,
        _description = new._description,
        _content = new._content
    where mapping_id = old.mapping_id and lang = new.lang;
    insert into _pages (mapping_id, lang, published, 
                        title, description, content, _title, _description, _content) 
           select old.mapping_id, new.lang, new.published, 
                  new.title, new.description, new.content, 
                  new._title, new._description, new._content
           where new.lang not in (select lang from _pages where mapping_id=old.mapping_id)
                 and (new.title is not null or new.description is not null 
                      or new.content is not null 
                      or new._title is not null or new._description is not null 
                      or new._content is not null);
);

create or replace rule pages_delete as
  on delete to pages do instead (
     delete from _mapping where mapping_id = old.mapping_id;
);

-------------------------------------------------------------------------------

create table _attachments (
       attachment_id serial primary key,
       mapping_id int not null references _mapping on delete cascade,
       filename varchar(64) not null,
       mime_type text not null,
       bytesize text not null,
       listed boolean not null default true,
       "timestamp" timestamp not null default now(),
       unique (mapping_id, filename)
);

create table _attachment_descr (
       attachment_id int not null references _attachments on delete cascade initially deferred,
       lang char(2) not null references languages(lang) on update cascade on delete cascade,
       title text,
       description text,
       unique (attachment_id, lang)
);

create table _images (
       attachment_id int not null references _attachments on delete cascade initially deferred,
       width int not null,
       height int not null,
       author text,
       "location" text,
       exif_date timestamp,
       exif text
);

create or replace view attachments
as select a.attachment_id  ||'.'|| l.lang as attachment_variant_id, l.lang,
  a.attachment_id, a.mapping_id, a.filename, a.mime_type, a.bytesize, a.listed, a."timestamp",
  d.title, d.description, i.width is not null as is_image,
  i.width, i.height, i.author, i."location", i.exif_date, i.exif
from _attachments a JOIN _mapping m using (mapping_id) cross join languages l
     left outer join _attachment_descr d using (attachment_id, lang)
     left outer join _images i using (attachment_id);

create or replace rule attachments_insert as
 on insert to attachments do instead (
    insert into _attachment_descr (attachment_id, lang, title, description)
           select new.attachment_id, new.lang, new.title, new.description
           where new.title IS not null OR new.description IS not null;
    insert into _images (attachment_id, width, height, author, "location", exif_date, exif)
           select new.attachment_id, new.width, new.height, new.author, new."location",
                  new.exif_date, new.exif
           where new.is_image;
    insert into _attachments (attachment_id, mapping_id, filename, mime_type, bytesize, listed)
           VALUES (new.attachment_id, new.mapping_id, new.filename,
                   new.mime_type, new.bytesize, new.listed)
           returning
             attachment_id ||'.'|| (select max(lang) from _attachment_descr
                                    where attachment_id=attachment_id),  NULL::char(2),
             attachment_id, mapping_id, filename, mime_type, bytesize, listed, "timestamp",
             NULL::text, NULL::text, NULL::boolean, NULL::int, NULL::int, NULL::text, NULL::text,
             NULL::timestamp, NULL::text
);

create or replace rule attachments_update as
 on UPDATE to attachments do instead (
    UPDATE _attachments SET
           mapping_id = new.mapping_id,
           filename = new.filename,
           mime_type = new.mime_type,
           bytesize = new.bytesize,
           listed = new.listed
           where attachment_id = old.attachment_id;
    UPDATE _images SET
           width = new.width,
           height = new.height,
           author = new.author,
           "location" = new."location",
           exif_date = new.exif_date,
           exif = new.exif
           where attachment_id = old.attachment_id;
    UPDATE _attachment_descr SET title=new.title, description=new.description
           where attachment_id = old.attachment_id and lang = old.lang;
    insert into _attachment_descr (attachment_id, lang, title, description)
           select new.attachment_id, new.lang, new.title, new.description
           where old.attachment_id NOT IN
             (select attachment_id from _attachment_descr where lang=old.lang);
);

create or replace rule attachments_delete as
  on delete to attachments do instead (
     delete from _attachments where attachment_id = old.attachment_id;
);

-------------------------------------------------------------------------------

create table news (
	news_id serial primary key,
	lang char(2) not null references languages(lang) on update cascade,
	mapping_id int not null references _mapping on delete cascade,
	"timestamp" timestamp not null default now(),
	title text not null,
	author int not null references users,
	content text not null
);

-------------------------------------------------------------------------------

create table planner (
	planner_id serial primary key,
	lang char(2) not null references languages(lang) on update cascade,
	mapping_id int not null references _mapping on delete cascade,
	start_date date not null,
	end_date date,
	title text not null,
	author int not null references users,
	"timestamp" timestamp not null default now(),
	content text not null,
	UNIQUE (start_date, lang, title)
);

-------------------------------------------------------------------------------

create table _panels (
	panel_id serial primary key,
	lang char(2) not null references languages(lang) on update cascade,
	identifier varchar(32) UNIQUE,
	title text not null,
	ord int,
	mapping_id integer references _mapping on delete set null,
	size int,
	content text,
	_content text,
	published boolean not null default false,
	UNIQUE (identifier, lang)
);

create or replace view panels as
select _panels.*, _mapping.modname, _mapping.read_role_id
from _panels
     left outer join _mapping using (mapping_id)
     left outer join _pages using (mapping_id, lang);

create or replace rule panels_insert as
  on insert to panels do instead (
     insert into _panels
        (lang, identifier, title, ord, mapping_id, size, content, _content, published)
     VALUES
        (new.lang, new.identifier, new.title, new.ord, new.mapping_id, new.size,
	 new.content, new._content, new.published)
);

create or replace rule panels_update as
  on UPDATE to panels do instead (
    UPDATE _panels SET
	lang = new.lang,
	identifier = new.identifier,
	title = new.title,
	ord = new.ord,
	mapping_id = new.mapping_id,
	size = new.size,
	content = new.content,
	_content = new._content,
	published = new.published
    where _panels.panel_id = old.panel_id;
);

create or replace rule panels_delete as
  on delete to panels do instead (
     delete from _panels
     where _panels.panel_id = old.panel_id;
);

-------------------------------------------------------------------------------

create table stylesheets (
	stylesheet_id serial primary key,
	identifier varchar(32) UNIQUE not null,
	active boolean not null default true,
	media varchar(12) not null default 'all',
	description text,
	content text,
        ord integer
);

-------------------------------------------------------------------------------

create table themes (
	theme_id serial primary key,
	name text UNIQUE not null,	
        foreground varchar(7),
        background varchar(7),
        border varchar(7),
        heading_fg varchar(7),
        heading_bg varchar(7),
        heading_line varchar(7),
        frame_fg varchar(7),
        frame_bg varchar(7),
        frame_border varchar(7),
        link varchar(7),
        link_visited varchar(7),
        link_hover varchar(7),
        meta_fg varchar(7),
        meta_bg varchar(7),
        help varchar(7),
        error_fg varchar(7),
        error_bg varchar(7),
        error_border varchar(7),
        message_fg varchar(7),
        message_bg varchar(7),
        message_border varchar(7),
        table_cell varchar(7),
        table_cell2 varchar(7),
        top_fg varchar(7),
        top_bg varchar(7),
        top_border varchar(7),
        highlight_bg varchar(7),
        inactive_folder varchar(7)
);

-------------------------------------------------------------------------------

create table text_labels (
         label name primary key
);

create or replace function add_text_label (_label name) returns void as $$
declare
  already_present int := count(*) from text_labels where label = _label;
begin
  if already_present = 0 then
    insert into text_labels (label) values (_label);
  end if;
end
$$ language plpgsql;

create table _texts (
        label name not null references text_labels,
        lang char(2) not null references languages(lang) on update cascade on delete cascade,
        description text default '',
        content text default '',
        primary key (label, lang)
);

create or replace view texts as
select label || '@' || lang as text_id,
       label,
       lang,
       coalesce(description, '') as description,
       coalesce(content, '') as content
from text_labels cross join languages left outer join _texts using (label, lang);

create or replace rule texts_update as
  on update to texts do instead (
    delete from _texts where label = new.label and lang = new.lang;
    insert into _texts values (new.label, new.lang, new.description, new.content);
);

create table email_labels (
         label name primary key
);

create or replace function add_email_label (_label name) returns void as $$
declare
  already_present int := count(*) from email_labels where label = _label;
begin
  if already_present = 0 then
    insert into email_labels (label) values (_label);
  end if;
end
$$ language plpgsql;

create table _emails (
        label name not null references email_labels,
        lang char(2) not null references languages(lang) on update cascade on delete cascade,
        description text,
        subject text,
        cc text,
        content text default '',
        primary key (label, lang)
);

create or replace view emails as
select label || '@' || lang as text_id,
       label,
       lang,
       coalesce(description, '') as description,
       coalesce(subject, '') as subject,
       coalesce(cc, '') as cc,
       coalesce(content, '') as content
from email_labels cross join languages left outer join _emails using (label, lang);

create or replace rule emails_insert as
  on insert to emails do instead (
    select add_email_label(new.label);
    insert into _emails values (new.label, new.lang, new.description, new.subject, new.cc, new.content);
);
create or replace rule emails_update as
  on update to emails do instead (
    delete from _emails where label = new.label and lang = new.lang;
    insert into _emails values (new.label, new.lang, new.description, new.subject, new.cc, new.content);
);
create or replace rule emails_delete as
  on delete to emails do instead (
    delete from _emails where label = old.label;
    delete from email_labels where label = old.label;
);

create table email_attachments (
       attachment_id serial primary key,
       label name not null references email_labels on delete cascade,
       filename varchar(64) not null,
       mime_type text not null
);

create table email_spool (
       id serial primary key,
       sender_address text,
       role_id name references roles on update cascade on delete cascade, -- recipient role, if NULL then all users
       subject text unique, -- unique to prevent inadvertent multiple insertion
       content text, -- body of the e-mail
       date timestamp default now (), -- time of insertion
       pid int, -- PID of the process currently sending the mails
       finished boolean default false -- set TRUE after the mail was successfully sent
);

-------------------------------------------------------------------------------

create table config (
        config_id int primary key default 0 check (config_id = 0),
        site_title text,
        site_subtitle text,
        allow_login_panel boolean not null default true,
        allow_registration boolean not null default true,
        login_is_email boolean not null default false,
        registration_expiration int,
        force_https_login boolean not null default false,
        https_port int,
        smtp_server text,
        webmaster_address text,
        bug_report_address text,
        default_sender_address text,
        upload_limit int,
        session_expiration int,
	default_language char(2) references languages(lang) on update cascade,
        certificate_authentication boolean not null default false,
        certificate_expiration int,
        theme_id integer references themes
);

-------------------------------------------------------------------------------

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
