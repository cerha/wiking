SET SEARCH_PATH TO "public";

drop view cms_v_page_attachments;
drop view cms_v_page_history;
drop view cms_v_newsletter_subscription;
drop view cms_v_planner;
drop view cms_v_publication_exports;
drop view cms_v_news;
drop function cms_recent_timestamp(ts TIMESTAMP(0), max_days INTEGER);

alter table cms_page_attachments alter column last_modified type timestamp with time zone;
alter table cms_page_attachments alter column created type timestamp with time zone;
alter table cms_email_spool alter column date type timestamp with time zone;
alter table cms_newsletter_editions alter column created type timestamp with time zone;
alter table cms_newsletter_editions alter column sent type timestamp with time zone;
alter table cms_newsletter_subscription alter column timestamp type timestamp with time zone;
alter table cms_news alter column timestamp type timestamp with time zone;
alter table cms_page_history alter column timestamp type timestamp with time zone;
alter table cms_planner alter column timestamp type timestamp with time zone;
alter table cms_publication_exports alter column timestamp type timestamp with time zone;
alter table users alter column since type timestamp with time zone;
alter table users alter column regexpire type timestamp with time zone;
alter table users alter column last_password_change type timestamp with time zone;
alter table cached_tables alter column stamp type timestamp with time zone;
alter table cms_discussions alter column timestamp type timestamp with time zone;

CREATE OR REPLACE VIEW "public"."cms_v_page_attachments" AS
SELECT CAST(a.attachment_id AS TEXT) || '.' || l.lang AS attachment_key, l.lang, a.attachment_id, a.page_id, t.title, t.description, a.filename, a.mime_type, a.bytesize, a.image, a.thumbnail, a.thumbnail_size, a.thumbnail_width, a.thumbnail_height, a.in_gallery, a.listed, a.author, a.location, a.width, a.height, a.created, a.last_modified 
FROM public.cms_page_attachments AS a JOIN public.cms_languages AS l ON 1 = 1 LEFT OUTER JOIN public.cms_page_attachment_texts AS t ON a.attachment_id = t.attachment_id AND l.lang = t.lang;

GRANT all ON "public".cms_v_page_attachments TO "www-data";

CREATE OR REPLACE RULE "cms_v_page_attachments__insert_instead" AS ON INSERT TO "public"."cms_v_page_attachments"
DO INSTEAD (
    insert into cms_page_attachment_texts (attachment_id, lang, title, description)
           select new.attachment_id, new.lang, new.title, new.description
           where new.title is not null OR new.description is not null;
    insert into cms_page_attachments (attachment_id, page_id, filename, mime_type, bytesize, image,
                                 thumbnail, thumbnail_size, thumbnail_width, thumbnail_height,
                                 in_gallery, listed, author, "location", width, height,
                                 created, last_modified)
           values (new.attachment_id, new.page_id, new.filename, new.mime_type,
                   new.bytesize, new.image, new.thumbnail, new.thumbnail_size,
                   new.thumbnail_width, new.thumbnail_height, new.in_gallery, new.listed,
                   new.author, new."location", new.width, new.height,
                   new.created, new.last_modified)
           returning
             attachment_id ||'.'|| (select max(lang) from cms_page_attachment_texts
                                    where attachment_id=attachment_id), null::char(2),
             attachment_id, page_id, null::text, null::text,
             filename, mime_type, bytesize, image, thumbnail,
             thumbnail_size, thumbnail_width, thumbnail_height, in_gallery, listed,
             author, "location", width, height, created, last_modified
        );

CREATE OR REPLACE RULE "cms_v_page_attachments__update_instead" AS ON UPDATE TO "public"."cms_v_page_attachments"
DO INSTEAD (
    update cms_page_attachments set
           page_id = new.page_id,
           filename = new.filename,
           mime_type = new.mime_type,
           bytesize = new.bytesize,
           image = new.image,
           thumbnail = new.thumbnail,
           thumbnail_size = new.thumbnail_size,
           thumbnail_width = new.thumbnail_width,
           thumbnail_height = new.thumbnail_height,
           listed = new.listed,
           in_gallery = new.in_gallery,
           author = new.author,
           "location" = new."location",
           width = new.width,
           height = new.height,
           created = new.created,
           last_modified = new.last_modified
           where attachment_id = old.attachment_id;
    update cms_page_attachment_texts set
           title=new.title,
           description=new.description
           where attachment_id = old.attachment_id and lang = old.lang;
    insert into cms_page_attachment_texts (attachment_id, lang, title, description)
           select new.attachment_id, new.lang, new.title, new.description
           where old.attachment_id not in
             (select attachment_id from cms_page_attachment_texts where lang=old.lang);
        );

CREATE OR REPLACE RULE "cms_v_page_attachments__delete_instead" AS ON DELETE TO "public"."cms_v_page_attachments"
DO INSTEAD (
     delete from cms_page_attachments where attachment_id = old.attachment_id;
        );

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


CREATE OR REPLACE VIEW "public"."cms_v_newsletter_subscription" AS
SELECT s.subscription_id, s.newsletter_id, s.uid, s.code, s.timestamp, coalesce(s.email, u.email) AS email, u.user_ AS user_name, u.login AS user_login 
FROM public.cms_newsletter_subscription AS s LEFT OUTER JOIN public.users AS u ON s.uid = u.uid;

GRANT all ON "public".cms_v_newsletter_subscription TO "www-data";

CREATE OR REPLACE RULE "cms_v_newsletter_subscription__insert_instead" AS ON INSERT TO "public"."cms_v_newsletter_subscription"
DO INSTEAD insert into public.cms_newsletter_subscription (newsletter_id, email, uid, code, timestamp) VALUES (new.newsletter_id, new.email, new.uid, new.code, new.timestamp);;

CREATE OR REPLACE RULE "cms_v_newsletter_subscription__update_instead" AS ON UPDATE TO "public"."cms_v_newsletter_subscription"
DO INSTEAD NOTHING;

CREATE OR REPLACE RULE "cms_v_newsletter_subscription__delete_instead" AS ON DELETE TO "public"."cms_v_newsletter_subscription"
DO INSTEAD DELETE FROM public.cms_newsletter_subscription WHERE public.cms_newsletter_subscription.subscription_id = old.subscription_id;

CREATE OR REPLACE VIEW "public"."cms_v_planner" AS
SELECT p.planner_id, p.page_id, p.lang, p.author, p.timestamp, p.start_date, p.end_date, p.title, p.content, u.user_ AS author_name, u.login AS author_login 
FROM public.cms_planner AS p JOIN public.users AS u ON p.author = u.uid;

GRANT all ON "public".cms_v_planner TO "www-data";

CREATE OR REPLACE RULE "cms_v_planner__insert_instead" AS ON INSERT TO "public"."cms_v_planner"
DO INSTEAD INSERT INTO public.cms_planner (planner_id, page_id, lang, author, timestamp, start_date, end_date, title, content) VALUES (nextval('public.cms_planner_planner_id_seq'), new.page_id, new.lang, new.author, new.timestamp, new.start_date, new.end_date, new.title, new.content);

CREATE OR REPLACE RULE "cms_v_planner__update_instead" AS ON UPDATE TO "public"."cms_v_planner"
DO INSTEAD UPDATE public.cms_planner SET planner_id=new.planner_id, page_id=new.page_id, lang=new.lang, author=new.author, timestamp=new.timestamp, start_date=new.start_date, end_date=new.end_date, title=new.title, content=new.content WHERE public.cms_planner.planner_id = old.planner_id;

CREATE OR REPLACE RULE "cms_v_planner__delete_instead" AS ON DELETE TO "public"."cms_v_planner"
DO INSTEAD DELETE FROM public.cms_planner WHERE public.cms_planner.planner_id = old.planner_id;

CREATE OR REPLACE VIEW "public"."cms_v_publication_exports" AS
SELECT e.export_id, e.page_id, e.lang, e.format, e.version, e.timestamp, e.public, e.bytesize, e.notes, e.log, CAST(e.page_id AS TEXT) || '.' || e.lang AS page_key 
FROM public.cms_publication_exports AS e;

GRANT all ON "public".cms_v_publication_exports TO "www-data";

CREATE OR REPLACE RULE "cms_v_publication_exports__insert_instead" AS ON INSERT TO "public"."cms_v_publication_exports"
DO INSTEAD INSERT INTO public.cms_publication_exports (export_id, page_id, lang, format, version, timestamp, public, bytesize, notes, log) VALUES (new.export_id, new.page_id, new.lang, new.format, new.version, new.timestamp, new.public, new.bytesize, new.notes, new.log);

CREATE OR REPLACE RULE "cms_v_publication_exports__update_instead" AS ON UPDATE TO "public"."cms_v_publication_exports"
DO INSTEAD UPDATE public.cms_publication_exports SET export_id=new.export_id, page_id=new.page_id, lang=new.lang, format=new.format, version=new.version, timestamp=new.timestamp, public=new.public, bytesize=new.bytesize, notes=new.notes, log=new.log WHERE public.cms_publication_exports.export_id = old.export_id;

CREATE OR REPLACE RULE "cms_v_publication_exports__delete_instead" AS ON DELETE TO "public"."cms_v_publication_exports"
DO INSTEAD DELETE FROM public.cms_publication_exports WHERE public.cms_publication_exports.export_id = old.export_id;

CREATE OR REPLACE VIEW "public"."cms_v_news" AS
SELECT n.news_id, n.page_id, n.lang, n.author, n.timestamp, n.title, n.content, n.days_displayed, u.user_ AS author_name, u.login AS author_login 
FROM public.cms_news AS n JOIN public.users AS u ON n.author = u.uid;

GRANT all ON "public".cms_v_news TO "www-data";

CREATE OR REPLACE RULE "cms_v_news__insert_instead" AS ON INSERT TO "public"."cms_v_news"
DO INSTEAD INSERT INTO public.cms_news (news_id, page_id, lang, author, timestamp, title, content, days_displayed) VALUES (nextval('public.cms_news_news_id_seq'), new.page_id, new.lang, new.author, new.timestamp, new.title, new.content, new.days_displayed);

CREATE OR REPLACE RULE "cms_v_news__update_instead" AS ON UPDATE TO "public"."cms_v_news"
DO INSTEAD UPDATE public.cms_news SET news_id=new.news_id, page_id=new.page_id, lang=new.lang, author=new.author, timestamp=new.timestamp, title=new.title, content=new.content, days_displayed=new.days_displayed WHERE public.cms_news.news_id = old.news_id;

CREATE OR REPLACE RULE "cms_v_news__delete_instead" AS ON DELETE TO "public"."cms_v_news"
DO INSTEAD DELETE FROM public.cms_news WHERE public.cms_news.news_id = old.news_id;

CREATE OR REPLACE FUNCTION "public"."cms_recent_timestamp"("ts" TIMESTAMP(0) WITH TIME ZONE, "max_days" INTEGER) RETURNS BOOLEAN LANGUAGE sql stable AS $$
select (current_date - $1::date) < $2
$$;

COMMENT ON FUNCTION "public"."cms_recent_timestamp"("ts" TIMESTAMP(0) WITH TIME ZONE, "max_days" INTEGER) IS 'Return true if `ts'' is not older than `max_days'' days.  Needed for a pytis
    filtering condition (FunctionCondition is currently too simple to express
    this directly).
    ';

