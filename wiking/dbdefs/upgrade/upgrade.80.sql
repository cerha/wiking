SET SEARCH_PATH TO "public";

CREATE TABLE public.cms_sessions (
	session_id SERIAL NOT NULL, 
	session_key TEXT NOT NULL, 
	auth_type TEXT NOT NULL, 
	uid INTEGER NOT NULL, 
	last_access TIMESTAMP(0) WITH TIME ZONE, 
	PRIMARY KEY (session_id), 
	UNIQUE (uid, session_key), 
	UNIQUE (session_id), 
	FOREIGN KEY(uid) REFERENCES public.users (uid) ON DELETE CASCADE
);

GRANT all ON TABLE "public".cms_sessions TO "www-data";
GRANT usage ON "public"."cms_sessions_session_id_seq" TO GROUP "www-data";

ALTER TABLE "public"."cms_sessions" SET WITHOUT OIDS;

CREATE TABLE public.cms_session_history (
	session_id INTEGER NOT NULL, 
	auth_type TEXT NOT NULL, 
	uid INTEGER NOT NULL, 
	start_time TIMESTAMP(0) WITH TIME ZONE NOT NULL, 
	end_time TIMESTAMP(0) WITH TIME ZONE, 
	PRIMARY KEY (session_id), 
	UNIQUE (session_id), 
	FOREIGN KEY(uid) REFERENCES public.users (uid) ON DELETE CASCADE
);

GRANT all ON TABLE "public".cms_session_history TO "www-data";

ALTER TABLE "public"."cms_session_history" SET WITHOUT OIDS;

CREATE OR REPLACE FUNCTION "public"."cms_update_session_history"() RETURNS trigger LANGUAGE plpgsql AS $$
begin
  if tg_op = 'INSERT' then
     insert into cms_session_history (session_id, auth_type, uid, start_time)
     values (new.session_id, new.auth_type, new.uid, new.last_access);
     return new;
  end if;
  if tg_op = 'DELETE' then
     update cms_session_history set end_time=old.last_access where session_id=old.session_id;
     return old;
  end if;
end;
$$;

CREATE TRIGGER "cms_sessions_trigger" after insert OR delete ON "cms_sessions"
FOR EACH ROW EXECUTE PROCEDURE "public"."cms_update_session_history"();

CREATE OR REPLACE VIEW "public"."cms_v_session_history" AS
SELECT h.session_id, h.auth_type, h.uid, h.start_time, h.end_time, u.login, u.user_ AS "user", CAST(h.end_time IS NULL AS BOOLEAN) AS active, coalesce(h.end_time, now()) - h.start_time AS duration 
FROM public.cms_session_history AS h LEFT OUTER JOIN public.users AS u ON u.uid = h.uid;

GRANT all ON "public".cms_v_session_history TO "www-data";

CREATE OR REPLACE RULE "cms_v_session_history__insert_instead" AS ON INSERT TO "public"."cms_v_session_history"
DO INSTEAD NOTHING;

CREATE OR REPLACE RULE "cms_v_session_history__update_instead" AS ON UPDATE TO "public"."cms_v_session_history"
DO INSTEAD NOTHING;

CREATE OR REPLACE RULE "cms_v_session_history__delete_instead" AS ON DELETE TO "public"."cms_v_session_history"
DO INSTEAD NOTHING;


CREATE TABLE public.cms_login_failures (
	failure_id SERIAL NOT NULL, 
	timestamp TIMESTAMP(0) WITH TIME ZONE NOT NULL, 
	login TEXT NOT NULL, 
	auth_type TEXT NOT NULL, 
	ip_address TEXT NOT NULL, 
	user_agent TEXT, 
	PRIMARY KEY (failure_id), 
	UNIQUE (failure_id)
);

GRANT all ON TABLE "public".cms_login_failures TO "www-data";
GRANT usage ON "public"."cms_login_failures_failure_id_seq" TO GROUP "www-data";

ALTER TABLE "public"."cms_login_failures" SET WITHOUT OIDS;

insert into cms_session_history (session_id, auth_type, uid, start_time, end_time)
select rank() over (order by log_id), 'Cookie', uid, start_time,
       coalesce(end_time,
                (select last_access from cms_session where session_id=l.session_id),
                least(now(), start_time + interval '2 hours'))
from cms_session_log l where success order by log_id;

insert into cms_login_failures (timestamp, login, auth_type, ip_address, user_agent)
select start_time, login, 'Cookie', ip_address, user_agent
from cms_session_log where not success order by log_id;

select setval('cms_sessions_session_id_seq', (select max(session_id) from cms_session_history));

DROP VIEW "public"."cms_v_session_log";
DROP TABLE public.cms_session_log;
DROP TABLE public.cms_session;
