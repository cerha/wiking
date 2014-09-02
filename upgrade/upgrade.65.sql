DROP VIEW "public"."cms_v_publication_exports";

ALTER TABLE public.cms_publication_exports ADD COLUMN log TEXT;

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

