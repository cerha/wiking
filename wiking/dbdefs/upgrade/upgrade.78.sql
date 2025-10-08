CREATE OR REPLACE VIEW "public"."cms_v_system_text_labels" AS
SELECT public.cms_system_text_labels.label, public.cms_system_text_labels.site, public.cms_languages.lang 
FROM public.cms_system_text_labels, public.cms_languages;

GRANT all ON "public".cms_v_system_text_labels TO "www-data";

CREATE OR REPLACE RULE "cms_v_system_text_labels__insert_instead" AS ON INSERT TO "public"."cms_v_system_text_labels"
DO INSTEAD NOTHING;

CREATE OR REPLACE RULE "cms_v_system_text_labels__update_instead" AS ON UPDATE TO "public"."cms_v_system_text_labels"
DO INSTEAD NOTHING;

CREATE OR REPLACE RULE "cms_v_system_text_labels__delete_instead" AS ON DELETE TO "public"."cms_v_system_text_labels"
DO INSTEAD NOTHING;

CREATE OR REPLACE VIEW "public"."cms_v_system_texts" AS
SELECT public.cms_v_system_text_labels.label || ':' || public.cms_v_system_text_labels.site || ':' || public.cms_v_system_text_labels.lang AS text_id, public.cms_v_system_text_labels.label, public.cms_v_system_text_labels.site, public.cms_v_system_text_labels.lang, public.cms_system_texts.description, public.cms_system_texts.content 
FROM "public"."cms_v_system_text_labels" LEFT OUTER JOIN public.cms_system_texts ON public.cms_v_system_text_labels.lang = public.cms_system_texts.lang AND public.cms_v_system_text_labels.label = public.cms_system_texts.label AND public.cms_v_system_text_labels.site = public.cms_system_texts.site;

GRANT all ON "public".cms_v_system_texts TO "www-data";

CREATE OR REPLACE RULE "cms_v_system_texts__insert_instead" AS ON INSERT TO "public"."cms_v_system_texts"
DO INSTEAD NOTHING;

CREATE OR REPLACE RULE "cms_v_system_texts__update_instead" AS ON UPDATE TO "public"."cms_v_system_texts"
DO INSTEAD (
    delete from cms_system_texts where label = new.label and lang = new.lang and site = new.site;
    insert into cms_system_texts (label, site, lang, description, content)
           values (new.label, new.site, new.lang, new.description, new.content);
        );

CREATE OR REPLACE RULE "cms_v_system_texts__delete_instead" AS ON DELETE TO "public"."cms_v_system_texts"
DO INSTEAD delete from cms_system_text_labels where label = old.label and site = old.site;;

