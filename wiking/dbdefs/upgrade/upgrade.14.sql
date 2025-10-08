alter table users add column last_password_change timestamp;
update users set last_password_change=since;
alter table users alter column last_password_change set not null;
