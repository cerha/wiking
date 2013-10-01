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

CREATE OR REPLACE VIEW "public"."cms_v_role_members" AS
SELECT m.role_member_id, m.role_id, m.uid, r.name AS role_name, u.user_ AS user_name, u.login AS user_login 
FROM public.role_members AS m JOIN public.roles AS r ON r.role_id = m.role_id JOIN public.users AS u ON m.uid = u.uid;

GRANT all ON "public".cms_v_role_members TO "www-data";

CREATE OR REPLACE RULE "cms_v_role_members__insert_instead" AS ON INSERT TO "public"."cms_v_role_members"
DO INSTEAD INSERT INTO public.role_members (role_member_id, role_id, uid) VALUES (nextval('public.role_members_role_member_id_seq'), new.role_id, new.uid);

CREATE OR REPLACE RULE "cms_v_role_members__update_instead" AS ON UPDATE TO "public"."cms_v_role_members"
DO INSTEAD UPDATE public.role_members SET role_member_id=new.role_member_id, role_id=new.role_id, uid=new.uid WHERE public.role_members.role_member_id = old.role_member_id;

CREATE OR REPLACE RULE "cms_v_role_members__delete_instead" AS ON DELETE TO "public"."cms_v_role_members"
DO INSTEAD DELETE FROM public.role_members WHERE public.role_members.role_member_id = old.role_member_id;

