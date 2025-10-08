DROP VIEW "public"."cms_v_session_log";

drop rule if exists cms_session_delete on cms_session;

ALTER TABLE public.cms_session ALTER COLUMN last_access TYPE TIMESTAMP(0) WITH TIME ZONE;

CREATE OR REPLACE VIEW "public"."cms_v_session_log" AS
SELECT l.log_id, l.session_id, l.uid, u.login AS uid_login, u.user_ AS uid_user, l.login, l.success, s.session_id IS NOT NULL AND age(s.last_access) < '1 hour' AS active, l.start_time, coalesce(l.end_time, s.last_access) - l.start_time AS duration, l.ip_address, l.user_agent, l.referer 
FROM public.cms_session_log AS l JOIN public.users AS u ON l.uid = u.uid LEFT OUTER JOIN public.cms_session AS s ON l.session_id = s.session_id;

GRANT all ON "public".cms_v_session_log TO "www-data";

CREATE OR REPLACE RULE "cms_v_session_log__insert_instead" AS ON INSERT TO "public"."cms_v_session_log"
DO INSTEAD INSERT INTO public.cms_session_log (log_id, session_id, uid, login, success, start_time, ip_address, user_agent, referer) VALUES (nextval('public.cms_session_log_log_id_seq'), new.session_id, new.uid, new.login, new.success, new.start_time, new.ip_address, new.user_agent, new.referer);

CREATE OR REPLACE RULE "cms_v_session_log__update_instead" AS ON UPDATE TO "public"."cms_v_session_log"
DO INSTEAD NOTHING;

CREATE OR REPLACE RULE "cms_v_session_log__delete_instead" AS ON DELETE TO "public"."cms_v_session_log"
DO INSTEAD NOTHING;
