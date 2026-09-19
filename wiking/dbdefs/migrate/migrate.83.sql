SET SEARCH_PATH TO "public";

-- Derive 'parents_published' from the parent pages when a page is created.
-- The application doesn't pass the value (it is a read only field), so newly
-- created pages used to remain invisible to the users who can not see
-- unpublished pages until the page was updated.

CREATE OR REPLACE RULE "cms_v_pages__insert_instead" AS ON INSERT TO "public"."cms_v_pages"
DO INSTEAD (INSERT INTO public.cms_pages (site, kind, identifier, parent, modname, menu_visibility, foldable, ord, owner, read_role_id, write_role_id) VALUES (new.site, new.kind, new.identifier, new.parent, new.modname, new.menu_visibility, new.foldable, new.ord, new.owner, new.read_role_id, new.write_role_id); UPDATE public.cms_pages SET tree_order=cms_page_tree_order(public.cms_pages.page_id) WHERE public.cms_pages.site = new.site AND (public.cms_pages.identifier = new.identifier OR public.cms_pages.tree_order != cms_page_tree_order(public.cms_pages.page_id)); INSERT INTO public.cms_page_texts (page_id, lang, published, parents_published, creator, created, published_since, title, description, content, _title, _description, _content) SELECT public.cms_pages.page_id, new.lang, new.published, cms_page_tree_published(new.parent, new.lang) AS cms_page_tree_published_1, new.creator, new.created, new.published_since, new.title, new.description, new.content, new._title, new._description, new._content 
FROM public.cms_pages 
WHERE public.cms_pages.identifier = new.identifier AND public.cms_pages.site = new.site AND public.cms_pages.kind = new.kind RETURNING CAST(public.cms_page_texts.page_id AS TEXT) || '.' || public.cms_page_texts.lang AS page_key, CAST(NULL AS TEXT) AS site, CAST(NULL AS TEXT) AS kind, public.cms_page_texts.lang, public.cms_page_texts.page_id, CAST(NULL AS TEXT) AS identifier, CAST(NULL AS INTEGER) AS parent, CAST(NULL AS TEXT) AS modname, CAST(NULL AS TEXT) AS menu_visibility, CAST(NULL AS BOOLEAN) AS foldable, CAST(NULL AS INTEGER) AS ord, CAST(NULL AS TEXT) AS tree_order, CAST(NULL AS INTEGER) AS owner, CAST(NULL AS NAME) AS read_role_id, CAST(NULL AS NAME) AS write_role_id, public.cms_page_texts.published, public.cms_page_texts.parents_published, public.cms_page_texts.published_since, public.cms_page_texts.creator, public.cms_page_texts.created, CAST(NULL AS TEXT) AS title_or_identifier, public.cms_page_texts.title, public.cms_page_texts.description, public.cms_page_texts.content, public.cms_page_texts._title, public.cms_page_texts._description, public.cms_page_texts._content, CAST(NULL AS VARCHAR(64)) AS creator_login, CAST(NULL AS TEXT) AS creator_name, CAST(NULL AS VARCHAR(64)) AS owner_login, CAST(NULL AS TEXT) AS owner_name);

-- Fix the value of the pages created before this migration.
UPDATE cms_page_texts SET parents_published = published.parents_published
  FROM (SELECT cms_pages.page_id, cms_page_texts.lang,
               cms_page_tree_published(cms_pages.parent, cms_page_texts.lang) AS parents_published
          FROM cms_pages JOIN cms_page_texts ON cms_page_texts.page_id = cms_pages.page_id
       ) AS published
 WHERE cms_page_texts.page_id = published.page_id
   AND cms_page_texts.lang = published.lang
   AND cms_page_texts.parents_published != published.parents_published;
