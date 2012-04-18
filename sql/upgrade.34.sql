alter table users alter column login type varchar(64);
update cms_database_version set version=34;
