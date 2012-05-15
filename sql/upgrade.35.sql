drop view cms_v_session_log;

create or replace view cms_v_session_log as select
       l.log_id,
       l.session_id,
       l.uid,
       u.login as uid_login, -- current login of given uid
       u.user_ as uid_user,
       l.login,
       l.success,
       s.session_id is not null and age(s.last_access) < '1 hour' as active,
       l.start_time,
       coalesce(l.end_time, s.last_access) - l.start_time as duration,
       l.ip_address,
       l.user_agent,
       l.referer
from cms_session_log l
     join users u using (uid)
     left outer join cms_session s using (session_id);

create or replace rule cms_v_session_log_insert as
  on insert to cms_v_session_log do instead (
     insert into cms_session_log (session_id, uid, login, success,
     	    	 	          start_time, ip_address, user_agent, referer)
            values (new.session_id, new.uid, new.login, new.success,
	    	    new.start_time, new.ip_address, new.user_agent, new.referer)
            returning log_id, session_id, uid, NULL::varchar(64), NULL::text, login, success, NULL::boolean,
	    	      start_time, NULL::interval, ip_address, user_agent, referer;
);
