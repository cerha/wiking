drop view cms_v_page_history;

CREATE OR REPLACE VIEW "public"."cms_v_page_history" AS
SELECT h.history_id, h.page_id, h.lang, h.uid, h.timestamp, h.content, h.comment, h.inserted_lines, h.changed_lines, h.deleted_lines, u.user_ AS "user", u.login, CAST(h.page_id AS TEXT) || '.' || h.lang AS page_key, CAST(h.inserted_lines AS TEXT) || ' / ' || CAST(h.changed_lines AS TEXT) || ' / ' || CAST(h.deleted_lines AS TEXT) AS changes 
FROM public.cms_page_history AS h JOIN public.users AS u ON h.uid = u.uid;

GRANT all ON "public".cms_v_page_history TO "www-data";

CREATE OR REPLACE RULE "cms_v_page_history__insert_instead" AS ON INSERT TO "public"."cms_v_page_history"
DO INSTEAD INSERT INTO public.cms_page_history (history_id, page_id, lang, uid, timestamp, content, comment, inserted_lines, changed_lines, deleted_lines) VALUES (new.history_id, new.page_id, new.lang, new.uid, new.timestamp, new.content, new.comment, new.inserted_lines, new.changed_lines, new.deleted_lines);

CREATE OR REPLACE RULE "cms_v_page_history__update_instead" AS ON UPDATE TO "public"."cms_v_page_history"
DO INSTEAD NOTHING;

CREATE OR REPLACE RULE "cms_v_page_history__delete_instead" AS ON DELETE TO "public"."cms_v_page_history"
DO INSTEAD NOTHING;

