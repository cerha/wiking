CREATE OR REPLACE RULE "cms_v_system_texts__delete_instead" AS ON DELETE TO "public"."cms_v_system_texts"
DO INSTEAD delete from cms_system_text_labels where label = old.label and site = old.site;;
