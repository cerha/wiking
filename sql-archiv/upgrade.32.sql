create table cms_database_version (
        version integer
);
insert into cms_database_version values (32);

alter table cms_email_spool drop constraint cms_email_spool_subject_key;

