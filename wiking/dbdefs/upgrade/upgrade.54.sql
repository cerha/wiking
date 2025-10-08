SET SEARCH_PATH TO "public";


CREATE TABLE public.cms_page_excerpts (
	id SERIAL NOT NULL, 
	page_id INTEGER, 
	lang TEXT NOT NULL, 
	title TEXT NOT NULL, 
	content TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(page_id) REFERENCES public.cms_pages (page_id) ON DELETE CASCADE ON UPDATE CASCADE
)

;

COMMENT ON TABLE "public"."cms_page_excerpts" IS 'Excerpts from CMS pages.
    Currently serving for printing parts of e-books in Braille.
    ';

GRANT ALL ON TABLE "public".cms_page_excerpts TO "www-data";

GRANT usage ON "public"."cms_page_excerpts_id_seq" TO GROUP "www-data";

ALTER TABLE "public"."cms_page_excerpts" SET WITHOUT OIDS;

