-- Wiking database creation script. --
-- -*- indent-tabs-mode: nil -*-

set client_min_messages=WARNING;

create table cms_languages (
        lang_id serial primary key,
        lang char(2) unique not null
);

create table cms_config (
        site text primary key,
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
        default_language char(2) references cms_languages(lang) on update cascade,
        theme_id integer -- references cms_themes
);

create table cms_countries (
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
	lang char(2) references cms_languages(lang) on update cascade on delete set null,
        regexpire timestamp,
        regcode char(16),
        certauth boolean not null default false,
        note text,
        confirm boolean not null default false,
        gender char(1) -- [m]ale, [f]emale, NULL=unknown
);
alter table users alter column since 
set default current_timestamp(0) at time zone 'GMT';
grant all on users_uid_seq to "www-data";

create or replace function insert_or_update_user (uid_ int, login_ varchar(32), password_ varchar(32), firstname_ text, surname_ text, nickname_ text, user__ text, email_ text, phone_ text, address_ text, uri_ text, state_ text, last_password_change_ timestamp, since_ timestamp, lang_ char(2), regexpire_ timestamp, regcode_ char(16), certauth_ boolean, note_ text, confirm_ boolean, gender_ char(1)) returns void as $$
declare
  row record;
begin
  if (select count(*) from users where login=login_)>0 then
    select into strict row * from users where login=login_;
    if row.login != login_ or row.password != password_ then
      raise exception 'duplicate key value violates unique constraint "users_login_key"';
    end if;
    update users set firstname=coalesce(firstname_,firstname), surname=coalesce(surname_,surname), nickname=coalesce(nickname_,nickname), email=coalesce(email_,email), phone=coalesce(phone_,phone), address=coalesce(address_,address), uri=coalesce(uri_,uri), regcode=null, certauth=coalesce(certauth_,certauth), note=coalesce(note_,note), gender=coalesce(gender_,gender) where login=login_;
  else
    insert into users (uid, login, password, firstname, surname, nickname, user_, email, phone, address, uri, state, last_password_change, since, lang, regexpire, regcode, certauth, note, confirm, gender) values (uid_, login_, password_, firstname_, surname_, nickname_, user__, email_, phone_, address_, uri_, state_, last_password_change_, since_, lang_, regexpire_, regcode_, coalesce(certauth_, False), note_, confirm_, gender_);
  end if;
end;
$$ language plpgsql;

create table role_members (
       role_member_id serial primary key,
       role_id name not null references roles on update cascade on delete cascade,
       uid int not null references users on update cascade on delete cascade,
       unique (role_id, uid)
);

create table cms_session (
       session_id serial primary key,
       uid int not null references users on delete cascade,
       session_key text not null,
       last_access timestamp,
       unique (uid, session_key)
);

create table cms_session_log (
       log_id serial primary key,
       session_id int references cms_session on delete set null,
       uid int references users on delete cascade, -- may be null for invalid logins
       login varchar(32) not null, -- usefull when uid is null or login changes
       success bool not null,
       start_time timestamp not null,
       end_time timestamp,
       ip_address text not null,
       user_agent text,
       referer text
);

create or replace rule cms_session_delete as on delete to cms_session do (
       update cms_session_log set end_time=old.last_access WHERE session_id=old.session_id;
);

create or replace view cms_v_session_log as select
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
from cms_session_log l left outer join cms_session s using (session_id);

create or replace rule cms_v_session_log_insert as
  on insert to cms_v_session_log do instead (
     insert into cms_session_log (session_id, uid, login, success,
     	    	 	          start_time, ip_address, user_agent, referer)
            values (new.session_id, new.uid, new.login, new.success,
	    	    new.start_time, new.ip_address, new.user_agent, new.referer)
            returning log_id, session_id, uid, login, success, NULL::boolean,
	    	      start_time, NULL::interval, ip_address, user_agent, referer;
);

-------------------------------------------------------------------------------

create table cms_pages (
       	page_id serial primary key,
	site text not null references cms_config(site) on update cascade on delete cascade,
	identifier varchar(32) not null,
	parent integer references cms_pages,
	modname text,
	menu_visibility text not null,
	foldable boolean,
	ord int not null,
	tree_order text,
	read_role_id name not null default 'anyone' references roles on update cascade,
	write_role_id name not null default 'content_admin' references roles on update cascade on delete set default,
	unique (identifier, site)
);
create unique index cms_pages_unique_tree_order on cms_pages (ord, coalesce(parent, 0), site);

create table cms_page_texts (
       page_id integer not null references cms_pages on delete cascade,
       lang char(2) not null references cms_languages(lang) on update cascade,
       published boolean not null default true,
       title text not null,
       description text,
       content text,
       _title text,
       _description text,
       _content text,
       primary key (page_id, lang)
);

create or replace function cms_page_tree_order(page_id int) returns text as $$
  select
    case when $1 is null then '' else
      (select cms_page_tree_order(parent) || '.' || to_char(coalesce(ord, 999999), 'FM000000')
       from cms_pages where page_id=$1)
    end
  as result
$$ language sql;

create or replace view cms_v_pages as
select p.page_id ||'.'|| l.lang as page_key, p.site, l.lang,
       p.page_id, p.identifier, p.parent, p.modname,
       p.menu_visibility, p.foldable, p.ord, p.tree_order,
       p.read_role_id, p.write_role_id,
       coalesce(t.published, false) as published,
       coalesce(t.title, p.identifier) as title_or_identifier,
       t.title, t.description, t.content, t._title, t._description, t._content
from cms_pages p cross join cms_languages l
     left outer join cms_page_texts t using (page_id, lang);

create or replace rule cms_v_pages_insert as
  on insert to cms_v_pages do instead (
     insert into cms_pages (site, identifier, parent, modname, read_role_id, write_role_id,
                            menu_visibility, foldable, ord)
     values (new.site, new.identifier, new.parent, new.modname,
             new.read_role_id, new.write_role_id, new.menu_visibility, new.foldable,
             coalesce(new.ord, (select max(ord)+100 from cms_pages
                                where coalesce(parent, 0)=coalesce(new.parent, 0)), 100));
     update cms_pages set tree_order = cms_page_tree_order(page_id);
     insert into cms_page_texts (page_id, lang, published,
                         title, description, content, _title, _description, _content)
     select (select page_id from cms_pages where identifier=new.identifier),
            new.lang, new.published,
            new.title, new.description, new.content, new._title, new._description, new._content
     returning page_id ||'.'|| lang, null::text,
       lang, page_id, null::varchar(32), null::int, null::text, null::text, null::boolean,
       null::int, null::text, null::name, null::name,
       published, title, title, description, content, _title,
       _description, _content
);

create or replace rule cms_v_pages_update as
  on update to cms_v_pages do instead (
    update cms_pages set
        site = new.site,
        identifier = new.identifier,
        parent = new.parent,
        modname = new.modname,
        read_role_id = new.read_role_id,
        write_role_id = new.write_role_id,
        menu_visibility = new.menu_visibility,
        foldable = new.foldable,
        ord = new.ord
    where cms_pages.page_id = old.page_id;
    update cms_pages set tree_order = cms_page_tree_order(page_id);
    update cms_page_texts set
        published = new.published,
        title = new.title,
        description = new.description,
        content = new.content,
        _title = new._title,
        _description = new._description,
        _content = new._content
    where page_id = old.page_id and lang = new.lang;
    insert into cms_page_texts (page_id, lang, published,
                        title, description, content, _title, _description, _content)
           select old.page_id, new.lang, new.published,
                  new.title, new.description, new.content,
                  new._title, new._description, new._content
           where new.lang not in (select lang from cms_page_texts where page_id=old.page_id)
                 and (new.title is not null or new.description is not null
                      or new.content is not null
                      or new._title is not null or new._description is not null
                      or new._content is not null);
);

create or replace rule cms_v_pages_delete as
  on delete to cms_v_pages do instead (
     delete from cms_pages where page_id = old.page_id;
);

-------------------------------------------------------------------------------

create table cms_page_attachments (
       attachment_id serial primary key,
       page_id int not null references cms_pages on delete cascade,
       filename varchar(64) not null,
       mime_type text not null,
       bytesize text not null,
       image bytea,
       thumbnail bytea,
       thumbnail_size text, -- desired size - small/medium/large
       thumbnail_width int, -- the actual pixel width of the thumbnail
       thumbnail_height int, -- the actual pixel height of the thumbnail
       in_gallery boolean not null default false,
       listed boolean not null default true,
       author text,
       "location" text,
       width int,
       height int,
       "timestamp" timestamp,
       unique (filename, page_id)
);

create table cms_page_attachment_texts (
       attachment_id int not null references cms_page_attachments on delete cascade initially deferred,
       lang char(2) not null references cms_languages(lang) on update cascade on delete cascade,
       title text,
       description text,
       unique (attachment_id, lang)
);

create or replace view cms_v_page_attachments
as select a.attachment_id  ||'.'|| t.lang as attachment_key, t.lang,
  a.attachment_id, a.page_id, t.title, t.description,
  a.filename, a.mime_type, a.bytesize,
  a.image, a.thumbnail, a.thumbnail_size, a.thumbnail_width, a.thumbnail_height,
  a.in_gallery, a.listed, a.author, a."location", a.width, a.height, a."timestamp"
from cms_page_attachments a cross join cms_languages
     left outer join cms_page_attachment_texts t using (attachment_id, lang);

create or replace rule cms_v_page_attachments_insert as
 on insert to cms_v_page_attachments do instead (
    insert into cms_page_attachment_texts (attachment_id, lang, title, description)
           select new.attachment_id, new.lang, new.title, new.description
           where new.title is not null OR new.description is not null;
    insert into cms_page_attachments (attachment_id, page_id, filename, mime_type, bytesize, image,
                                 thumbnail, thumbnail_size, thumbnail_width, thumbnail_height,
                                 in_gallery, listed, author, "location", width, height, "timestamp")
           values (new.attachment_id, new.page_id, new.filename, new.mime_type,
                   new.bytesize, new.image, new.thumbnail, new.thumbnail_size,
                   new.thumbnail_width, new.thumbnail_height, new.in_gallery, new.listed,
                   new.author, new."location", new.width, new.height, new."timestamp")
           returning
             attachment_id ||'.'|| (select max(lang) from cms_page_attachment_texts
                                    where attachment_id=attachment_id), null::char(2),
             attachment_id, page_id, null::text, null::text,
             filename, mime_type, bytesize, image, thumbnail,
             thumbnail_size, thumbnail_width, thumbnail_height, in_gallery, listed,
             author, "location", width, height, "timestamp"
);

create or replace rule cms_v_page_attachments_update as
 on update to cms_v_page_attachments do instead (
    update cms_page_attachments set
           page_id = new.page_id,
           filename = new.filename,
           mime_type = new.mime_type,
           bytesize = new.bytesize,
           image = new.image,
           thumbnail = new.thumbnail,
           thumbnail_size = new.thumbnail_size,
           thumbnail_width = new.thumbnail_width,
           thumbnail_height = new.thumbnail_height,
           listed = new.listed,
           in_gallery = new.in_gallery,
           author = new.author,
           "location" = new."location",
           width = new.width,
           height = new.height,
	   "timestamp" = new."timestamp"
           where attachment_id = old.attachment_id;
    update cms_page_attachment_texts set
           title=new.title,
           description=new.description
           where attachment_id = old.attachment_id and lang = old.lang;
    insert into cms_page_attachment_texts (attachment_id, lang, title, description)
           select new.attachment_id, new.lang, new.title, new.description
           where old.attachment_id not in
             (select attachment_id from cms_page_attachment_texts where lang=old.lang);
);

create or replace rule cms_v_page_attachments_delete as
  on delete to cms_v_page_attachments do instead (
     delete from cms_page_attachments where attachment_id = old.attachment_id;
);

-------------------------------------------------------------------------------

create table cms_news (
	news_id serial primary key,
	site text not null references cms_config(site) on update cascade on delete cascade,
	page_id int not null references cms_pages on delete cascade,
	author int not null references users,
	"timestamp" timestamp not null default now(),
	lang char(2) not null references cms_languages(lang) on update cascade,
	title text not null,
	content text not null
);

create table cms_planner (
	planner_id serial primary key,
	site text not null references cms_config(site) on update cascade on delete cascade,
	page_id int not null references cms_pages on delete cascade,
	author int not null references users,
	"timestamp" timestamp not null default now(),
	start_date date not null,
	end_date date,
	lang char(2) not null references cms_languages(lang) on update cascade,
	title text not null,
	content text not null,
	unique (title, site, start_date, lang)
);

create table cms_panels (
	panel_id serial primary key,
	site text not null references cms_config(site) on update cascade on delete cascade,
	lang char(2) not null references cms_languages(lang) on update cascade,
	identifier varchar(32),
	title text not null,
	ord int,
	page_id integer references cms_pages on delete set null,
	size int,
	content text,
	_content text,
	published boolean not null default false,
	unique (identifier, site, lang)
);

create or replace view cms_v_panels as
select cms_panels.*, cms_pages.modname, cms_pages.read_role_id
from cms_panels left outer join cms_pages using (page_id);

create or replace rule cms_v_panels_insert as
  on insert to cms_v_panels do instead (
     insert into cms_panels
        (site, lang, identifier, title, ord, page_id, size, content, _content, published)
     values
        (new.site, new.lang, new.identifier, new.title, new.ord, new.page_id, new.size,
	 new.content, new._content, new.published)
);

create or replace rule cms_v_panels_update as
  on update to cms_v_panels do instead (
    update cms_panels set
      site = new.site,
      lang = new.lang,
      identifier = new.identifier,
      title = new.title,
      ord = new.ord,
      page_id = new.page_id,
      size = new.size,
      content = new.content,
      _content = new._content,
      published = new.published
    where panel_id = old.panel_id;
);

create or replace rule cms_v_panels_delete as
  on delete to cms_v_panels do instead (
     delete from cms_panels where panel_id = old.panel_id;
);

-------------------------------------------------------------------------------

create table cms_stylesheets (
	stylesheet_id serial primary key,
	site text references cms_config(site) on update cascade on delete cascade,
	identifier varchar(32) not null,
	active boolean not null default true,
	media varchar(12) not null default 'all',
	scope text,
	description text,
	content text,
        ord integer,
	unique (identifier, site)
);

create table cms_themes (
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

alter table cms_config add constraint cms_config_theme_id_fkey foreign key (theme_id) references cms_themes;

-------------------------------------------------------------------------------

create table cms_system_text_labels (
        label name not null,
        site text not null references cms_config(site) on update cascade on delete cascade,
	primary key (label, site)
);

create or replace function cms_add_text_label (_label name, _site text) returns void as $$
declare
  already_present int := count(*) from cms_system_text_labels
                         where label = _label and site = _site;
begin
  if already_present = 0 then
    insert into cms_system_text_labels (label, site) values (_label, _site);
  end if;
end
$$ language plpgsql;

create table cms_system_texts (
        label name not null,
        site text not null,
        lang char(2) not null references cms_languages(lang) on update cascade on delete cascade,
        description text default '',
        content text default '',
        primary key (label, site, lang),
	foreign key (label, site) references cms_system_text_labels (label, site) on update cascade on delete cascade
);

create or replace view cms_v_system_texts as
select label || '@' || lang as text_id,
       label,
       site,
       lang,
       coalesce(description, '') as description,
       coalesce(content, '') as content
from cms_system_text_labels cross join cms_languages
     left outer join cms_system_texts using (label, site, lang);

create or replace rule cms_v_system_texts_update as
  on update to cms_system_texts do instead (
    delete from cms_system_texts where label = new.label and lang = new.lang and site = new.site;
    insert into cms_system_texts (label, site, lang, description, content)
           values (new.label, new.site, new.lang, new.description, new.content);
);

-------------------------------------------------------------------------------

create table cms_email_labels (
        label name primary key
);

create or replace function cms_add_email_label (_label name) returns void as $$
declare
  already_present int := count(*) from cms_email_labels where label = _label;
begin
  if already_present = 0 then
    insert into cms_email_labels (label) values (_label);
  end if;
end
$$ language plpgsql;

create table cms_emails (
        label name not null references cms_email_labels,
        lang char(2) not null references cms_languages(lang) on update cascade on delete cascade,
        description text,
        subject text,
        cc text,
        content text default '',
        primary key (label, lang)
);

create or replace view cms_v_emails as
select label || '@' || lang as text_id,
       label,
       lang,
       coalesce(description, '') as description,
       coalesce(subject, '') as subject,
       coalesce(cc, '') as cc,
       coalesce(content, '') as content
from cms_email_labels cross join cms_languages left outer join cms_emails using (label, lang);

create or replace rule cms_v_emails_insert as
  on insert to cms_v_emails do instead (
    select cms_add_email_label(new.label);
    insert into cms_emails values (new.label, new.lang, new.description, new.subject, new.cc, new.content);
);
create or replace rule cms_v_emails_update as
  on update to cms_v_emails do instead (
    delete from cms_emails where label = new.label and lang = new.lang;
    insert into cms_emails values (new.label, new.lang, new.description, new.subject, new.cc, new.content);
);
create or replace rule cms_v_emails_delete as
  on delete to cms_v_emails do instead (
    delete from cms_emails where label = old.label;
    delete from cms_email_labels where label = old.label;
);

create table cms_email_attachments (
       attachment_id serial primary key,
       label name not null references cms_email_labels on delete cascade,
       filename varchar(64) not null,
       mime_type text not null
);

create table cms_email_spool (
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
