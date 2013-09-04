drop view attachments;
drop view pages;
drop view mapping;
drop view panels;
drop view session_log;
drop function _mapping_tree_order(page_id int);
drop view texts;
drop function add_text_label(_label name);
drop view emails;
drop function add_email_label(_label name);

alter table config rename to cms_config;
alter table cms_config drop constraint config_default_language_fkey, add constraint cms_config_default_language_fkey foreign key (default_language) references languages(lang);
alter table cms_config drop constraint config_theme_id_fkey, add constraint cms_config_theme_id_fkey foreign key (theme_id) references themes(theme_id);
alter table cms_config drop column config_id;
alter table cms_config drop column certificate_authentication;
alter table cms_config drop column certificate_expiration;
alter table cms_config add column site text unique;
update cms_config set site='*';
alter table cms_config alter column site set not null;

alter table languages rename to cms_languages;
alter index languages_pkey rename to cms_languages_pkey;
-- alter index languages_lang_id_key rename to cms_languages_lang_id_key;
alter index languages_lang_key rename to cms_languages_lang_key;
alter sequence languages_lang_id_seq rename to cms_languages_lang_id_seq;

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

create table cms_news (
	news_id serial primary key,
	page_id int not null references cms_pages on delete cascade,
	author int not null references users,
	"timestamp" timestamp not null default now(),
	lang char(2) not null references cms_languages(lang) on update cascade,
	title text not null,
	content text not null
);

create table cms_planner (
	planner_id serial primary key,
	page_id int not null references cms_pages on delete cascade,
	author int not null references users,
	"timestamp" timestamp not null default now(),
	start_date date not null,
	end_date date,
	lang char(2) not null references cms_languages(lang) on update cascade,
	title text not null,
	content text not null
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

create table cms_system_text_labels (
        label name not null,
        site text not null references cms_config(site) on update cascade on delete cascade,
	primary key (label, site)
);

create table cms_system_texts (
        label name not null,
        site text not null,
        lang char(2) not null references cms_languages(lang) on update cascade on delete cascade,
        description text default '',
        content text default '',
        primary key (label, site, lang),
	foreign key (label, site) references cms_system_text_labels (label, site) on update cascade on delete cascade
);

create table cms_email_labels (
        label name primary key
);

create table cms_emails (
        label name not null references cms_email_labels,
        lang char(2) not null references cms_languages(lang) on update cascade on delete cascade,
        description text,
        subject text,
        cc text,
        content text default '',
        primary key (label, lang)
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


insert into cms_pages (page_id, site, identifier, parent, modname, read_role_id, write_role_id, menu_visibility, foldable, ord)
       select mapping_id, '*', identifier, parent, modname, read_role_id, write_role_id, menu_visibility, foldable, ord
       from _mapping;
insert into cms_page_texts (page_id, lang, published, title, description, content, _title, _description, _content)
       select mapping_id, lang, published, title, description, content, _title, _description, _content
       from _pages;
--alter table cms_pages add constraint cms_pages_parent_fkey foreign key (parent) references cms_pages;
select setval('cms_pages_page_id_seq', nextval('_mapping_mapping_id_seq'));
drop table _mapping cascade;
drop table _pages cascade;
create or replace function cms_page_tree_order(page_id int) returns text as $$
  select
    case when $1 is null then '' else
      (select cms_page_tree_order(parent) || '.' || to_char(coalesce(ord, 999999), 'FM000000')
       from cms_pages where page_id=$1)
    end
  as result
$$ language sql;
update cms_pages set tree_order = cms_page_tree_order(page_id);

insert into cms_page_attachments (attachment_id, page_id, filename, mime_type, bytesize, image, thumbnail, thumbnail_size, thumbnail_width, thumbnail_height, in_gallery, listed, author, "location", width, height, "timestamp")
       select attachment_id, mapping_id, filename, mime_type, bytesize, image, thumbnail, thumbnail_size, thumbnail_width, thumbnail_height, in_gallery, listed, author, "location", width, height, "timestamp"
       from _attachments;
insert into cms_page_attachment_texts (attachment_id, lang, title, description)
       select attachment_id, lang, title, description
       from _attachment_descr;
select setval('cms_page_attachments_attachment_id_seq', nextval('_attachments_attachment_id_seq'));
drop table _attachments cascade;
drop table _attachment_descr cascade;

insert into cms_news (news_id, page_id, author, "timestamp", lang, title, content)
       select news_id, mapping_id, author, "timestamp", lang, title, content
       from news;
select setval('cms_news_news_id_seq', nextval('news_news_id_seq'));
drop table news cascade;

insert into cms_planner (planner_id, page_id, author, "timestamp", start_date, end_date, lang, title, content)
       select planner_id, mapping_id, author, "timestamp", start_date, end_date, lang, title, content
       from planner;
select setval('cms_planner_planner_id_seq', nextval('planner_planner_id_seq'));
drop table planner cascade;

insert into cms_panels (panel_id, site, lang, identifier, title, ord, page_id, size, content, _content, published)
       select panel_id, '*', lang, identifier, title, ord, mapping_id, size, content, _content, published
       from _panels;
select setval('cms_panels_panel_id_seq', nextval('_panels_panel_id_seq'));
drop table _panels cascade;

alter table stylesheets rename to cms_stylesheets;
alter index stylesheets_pkey rename to cms_stylesheets_pkey;
alter table cms_stylesheets add column site text references cms_config(site) on update cascade on delete cascade;
update cms_stylesheets set site='*';
alter table cms_stylesheets alter column site set not null;
alter table cms_stylesheets drop constraint stylesheets_identifier_key;
alter table cms_stylesheets add constraint cms_stylesheets_identifier_key unique (identifier, site);
alter sequence stylesheets_stylesheet_id_seq rename to cms_stylesheets_stylesheet_id_seq;

alter table themes rename to cms_themes;
alter index themes_pkey rename to cms_themes_pkey;
alter index themes_name_key rename to cms_themes_name_key;
alter sequence themes_theme_id_seq rename to cms_themes_theme_id_seq;

alter table countries rename to cms_countries;
alter index countries_pkey rename to cms_countries_pkey;
alter index countries_country_key rename to cms_countries_country_key;
alter sequence countries_country_id_seq rename to cms_countries_country_id_seq;

drop rule session_delete on session;
alter table session rename to cms_session;
alter index session_pkey rename to cms_session_pkey;
alter table cms_session drop constraint session_uid_fkey, add constraint cms_session_uid_fkey foreign key (uid) references users(uid) on delete cascade;
alter sequence session_session_id_seq rename to cms_session_session_id_seq;

alter table _session_log rename to cms_session_log;
alter index _session_log_pkey rename to cms_session_log_pkey;
alter table cms_session_log drop constraint _session_log_session_id_fkey,
      add constraint cms_session_log_session_id_fkey foreign key (session_id) references cms_session(session_id) on delete set null;
alter table cms_session_log drop constraint _session_log_uid_fkey,
      add constraint cms_session_log_uid_fkey foreign key (uid) references users(uid) on delete cascade;
alter sequence _session_log_log_id_seq rename to cms_session_log_log_id_seq;

insert into cms_system_text_labels (label, site)
       select label, '*' from text_labels;
insert into cms_system_texts (label, site, lang, description, content)
       select label, '*', lang, description, content from _texts;
drop table _texts;
drop table text_labels;

insert into cms_email_labels (label) select label from email_labels;
insert into cms_emails (label, lang, description, subject, cc, content)
       select label, lang, description, subject, cc, content from _emails;
insert into cms_email_attachments (attachment_id, label, filename, mime_type)
       select attachment_id, label, filename, mime_type from email_attachments;
insert into cms_email_spool (id, sender_address, role_id, subject, content, date, pid, finished)
       select id, sender_address, role_id, subject, content, date, pid, finished from email_spool;
drop table _emails;
drop table email_attachments;
drop table email_spool;
drop table email_labels;

create or replace rule cms_session_delete as on delete to cms_session do (
       update cms_session_log set end_time=old.last_access WHERE session_id=old.session_id;
);

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
                                where site=new.site
                                      and coalesce(parent, 0)=coalesce(new.parent, 0)), 100));
     update cms_pages set tree_order = cms_page_tree_order(page_id);
     insert into cms_page_texts (page_id, lang, published,
                                 title, description, content,
                                 _title, _description, _content)
     select (select page_id from cms_pages where identifier=new.identifier and site=new.site),
            new.lang, new.published,
            new.title, new.description, new.content,
            new._title, new._description, new._content
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
    update cms_pages set tree_order = cms_page_tree_order(page_id) where site=new.site;
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
                                title, description, content,
                                _title, _description, _content)
           select old.page_id, new.lang, new.published,
                  new.title, new.description, new.content,
                  new._title, new._description, new._content
           where new.lang not in (select lang from cms_page_texts where page_id=old.page_id)
                 and coalesce(new.title, new.description, new.content,
                              new._title, new._description, new._content) is not null;
);

create or replace rule cms_v_pages_delete as
  on delete to cms_v_pages do instead (
     delete from cms_pages where page_id = old.page_id;
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

create or replace function cms_add_text_label (_label name, _site text) returns void as $$
declare
  already_present int := count(*) from cms_system_text_labels
                         where label = _label and site = _site;
begin
  if already_present = 0 then
    update cms_config set site=_site where site='*';
    insert into cms_config (site, site_title) select _site, _site
           where _site not in (select site from cms_config);
    insert into cms_system_text_labels (label, site) values (_label, _site);
  end if;
end
$$ language plpgsql;

create or replace view cms_v_system_texts as
select label || ':' || site || ':' || lang as text_id,
       label, site, lang, description, content
from cms_system_text_labels cross join cms_languages
     left outer join cms_system_texts using (label, site, lang);

create or replace rule cms_v_system_texts_update as
  on update to cms_v_system_texts do instead (
    delete from cms_system_texts where label = new.label and lang = new.lang and site = new.site;
    insert into cms_system_texts (label, site, lang, description, content)
           values (new.label, new.site, new.lang, new.description, new.content);
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

create or replace view cms_v_emails as
select label || ':' || lang as text_id,
       label, lang, description, subject, cc, content
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
