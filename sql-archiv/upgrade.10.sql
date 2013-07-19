set client_min_messages=WARNING;

drop table text_labels cascade;
drop table _texts cascade;
create language plpgsql;

alter table config add column default_language char(2) references languages(lang);

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
        lang char(2) not null references languages(lang) on delete cascade,
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
        lang char(2) not null references languages(lang) on delete cascade,
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
       role char(4), -- recipient role, if NULL then all users
       subject text unique, -- unique to prevent inadvertent multiple insertion
       content text, -- body of the e-mail
       date timestamp default now (), -- time of insertion
       pid int, -- PID of the process currently sending the mails
       finished boolean default 'FALSE' -- set TRUE after the mail was successfully sent
);
