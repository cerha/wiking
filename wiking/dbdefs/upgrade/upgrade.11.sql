drop table session;

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
