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

