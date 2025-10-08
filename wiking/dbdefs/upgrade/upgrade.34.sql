drop view cms_v_session_log;
alter table users alter column login type varchar(64);
alter table cms_session_log alter column login type varchar(64);

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

drop function insert_or_update_user (uid_ int, login_ varchar(32), password_ varchar(32), firstname_ text, surname_ text, nickname_ text, user__ text, email_ text, phone_ text, address_ text, uri_ text, state_ text, last_password_change_ timestamp, since_ timestamp, lang_ char(2), regexpire_ timestamp, regcode_ char(16), certauth_ boolean, note_ text, confirm_ boolean, gender_ char(1));
create or replace function cms_f_insert_or_update_user (uid_ int, login_ varchar(64), password_ varchar(32), firstname_ text, surname_ text, nickname_ text, user__ text, email_ text, phone_ text, address_ text, uri_ text, state_ text, last_password_change_ timestamp, since_ timestamp, lang_ char(2), regexpire_ timestamp, regcode_ char(16), certauth_ boolean, note_ text, confirm_ boolean, gender_ char(1)) returns void as $$
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


create table cms_discussions (
	comment_id serial primary key,
	page_id int not null references cms_pages on delete cascade,
	lang char(2) not null references cms_languages(lang) on update cascade,
	author int not null references users,
	"timestamp" timestamp not null default now(),
	in_reply_to int references cms_discussions on delete set null,
	tree_order text not null,
	text text not null
);
create index cms_discussions_tree_order_index on cms_discussions (tree_order);

create or replace function cms_discussions_trigger_before_insert() returns trigger as $$
declare
  parent_tree_order text := '';
begin
  if new.in_reply_to is not null then
    parent_tree_order := (select tree_order||'.' from cms_discussions where comment_id=new.in_reply_to);
  end if;
  new.tree_order := parent_tree_order || to_char(new.comment_id, 'FM000000000');
  return new;
end;
$$ language plpgsql;

create trigger cms_discussions_trigger_before_insert before insert on cms_discussions
for each row execute procedure cms_discussions_trigger_before_insert();

insert into cms_discussions (page_id, lang, author, timestamp, text) select page_id, lang, author, timestamp, content from cms_news where page_id in (select page_id from cms_pages where modname='Discussions');
delete from cms_news where page_id in (select page_id from cms_pages where modname='Discussions');
