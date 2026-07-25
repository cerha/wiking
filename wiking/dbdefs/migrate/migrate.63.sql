CREATE TABLE public.cms_newsletters (
	newsletter_id SERIAL NOT NULL, 
	page_id INTEGER NOT NULL, 
	lang CHAR(2) NOT NULL, 
	title TEXT NOT NULL, 
	image BYTEA NOT NULL, 
	image_width INTEGER NOT NULL, 
	image_height INTEGER NOT NULL, 
	description TEXT NOT NULL, 
	sender TEXT NOT NULL, 
	address TEXT NOT NULL, 
	read_role_id NAME DEFAULT 'anyone' NOT NULL, 
	write_role_id NAME DEFAULT 'content_admin' NOT NULL, 
	bg_color TEXT NOT NULL, 
	text_color TEXT NOT NULL, 
	link_color TEXT NOT NULL, 
	heading_color TEXT NOT NULL, 
	top_bg_color TEXT NOT NULL, 
	top_text_color TEXT NOT NULL, 
	top_link_color TEXT NOT NULL, 
	footer_bg_color TEXT NOT NULL, 
	footer_text_color TEXT NOT NULL, 
	footer_link_color TEXT NOT NULL, 
	signature TEXT, 
	PRIMARY KEY (newsletter_id), 
	FOREIGN KEY(page_id) REFERENCES public.cms_pages (page_id) ON DELETE CASCADE, 
	FOREIGN KEY(lang) REFERENCES public.cms_languages (lang) ON UPDATE CASCADE, 
	FOREIGN KEY(read_role_id) REFERENCES public.roles (role_id) ON UPDATE CASCADE, 
	FOREIGN KEY(write_role_id) REFERENCES public.roles (role_id) ON DELETE SET DEFAULT ON UPDATE CASCADE
);

GRANT all ON TABLE "public".cms_newsletters TO "www-data";
GRANT usage ON "public"."cms_newsletters_newsletter_id_seq" TO GROUP "www-data";
ALTER TABLE "public"."cms_newsletters" SET WITHOUT OIDS;
CREATE TRIGGER "public__cms_newsletters__cached_tables_update_trigger" after insert OR update OR delete OR truncate ON "cms_newsletters"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'cms_newsletters', True);

CREATE TABLE public.cms_newsletter_subscription (
	subscription_id SERIAL NOT NULL, 
	newsletter_id INTEGER NOT NULL, 
	uid INTEGER, 
	email TEXT, 
	code TEXT, 
	timestamp TIMESTAMP(0) WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (subscription_id), 
	CHECK ((uid is not null or email is not null and code is not null) and (uid is null or email is null and code is null)), 
	UNIQUE (newsletter_id, uid), 
	UNIQUE (newsletter_id, email), 
	FOREIGN KEY(newsletter_id) REFERENCES public.cms_newsletters (newsletter_id) ON DELETE CASCADE, 
	FOREIGN KEY(uid) REFERENCES public.users (uid)
);

GRANT all ON TABLE "public".cms_newsletter_subscription TO "www-data";
GRANT usage ON "public"."cms_newsletter_subscription_subscription_id_seq" TO GROUP "www-data";
ALTER TABLE "public"."cms_newsletter_subscription" SET WITHOUT OIDS;
CREATE TRIGGER "public__cms_newsletter_subscription__cached_tables_update_trigger" after insert OR update OR delete OR truncate ON "cms_newsletter_subscription"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'cms_newsletter_subscription', True);

CREATE TABLE public.cms_newsletter_editions (
	edition_id SERIAL NOT NULL, 
	newsletter_id INTEGER NOT NULL, 
	creator INTEGER NOT NULL, 
	created TIMESTAMP(0) WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	sent TIMESTAMP(0) WITHOUT TIME ZONE, 
	access_code TEXT, 
	PRIMARY KEY (edition_id), 
	FOREIGN KEY(newsletter_id) REFERENCES public.cms_newsletters (newsletter_id) ON DELETE CASCADE, 
	FOREIGN KEY(creator) REFERENCES public.users (uid)
);

GRANT all ON TABLE "public".cms_newsletter_editions TO "www-data";
GRANT usage ON "public"."cms_newsletter_editions_edition_id_seq" TO GROUP "www-data";
ALTER TABLE "public"."cms_newsletter_editions" SET WITHOUT OIDS;
CREATE TRIGGER "public__cms_newsletter_editions__cached_tables_update_trigger" after insert OR update OR delete OR truncate ON "cms_newsletter_editions"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'cms_newsletter_editions', True);

CREATE TABLE public.cms_newsletter_posts (
	post_id SERIAL NOT NULL, 
	edition_id INTEGER NOT NULL, 
	ord INTEGER, 
	title TEXT NOT NULL, 
	content TEXT NOT NULL, 
	image BYTEA, 
	image_position TEXT, 
	image_width INTEGER, 
	image_height INTEGER, 
	PRIMARY KEY (post_id), 
	FOREIGN KEY(edition_id) REFERENCES public.cms_newsletter_editions (edition_id) ON DELETE CASCADE
);

GRANT all ON TABLE "public".cms_newsletter_posts TO "www-data";
GRANT usage ON "public"."cms_newsletter_posts_post_id_seq" TO GROUP "www-data";
ALTER TABLE "public"."cms_newsletter_posts" SET WITHOUT OIDS;
CREATE TRIGGER "public__cms_newsletter_posts__cached_tables_update_trigger" after insert OR update OR delete OR truncate ON "cms_newsletter_posts"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'cms_newsletter_posts', True);
