-- Wiking database creation script. --

CREATE TABLE users (
	uid serial PRIMARY KEY,
	login varchar(32) UNIQUE NOT NULL,
	password varchar(32) NOT NULL,
	firstname text NOT NULL,
	surname text NOT NULL,
	nickname text,
	user_ text NOT NULL,
	email text NOT NULL,
	phone text,
	address text,
	uri text,
	enabled boolean NOT NULL DEFAULT 'FALSE',
	contributor boolean NOT NULL DEFAULT 'FALSE',
	author boolean NOT NULL DEFAULT 'FALSE',
	admin boolean NOT NULL DEFAULT 'FALSE',
	since timestamp NOT NULL DEFAULT current_timestamp(0),
	session_key text,
	session_expire timestamp
);
ALTER TABLE users ALTER COLUMN since 
SET DEFAULT current_timestamp(0) AT TIME ZONE 'GMT';

CREATE TABLE session (
       session_id serial PRIMARY KEY,
       login varchar(32) NOT NULL,
       key text,
       expire timestamp,
       UNIQUE (login, key)
);

-------------------------------------------------------------------------------

CREATE TABLE languages (
	lang_id serial PRIMARY KEY,
	lang char(2) UNIQUE NOT NULL
);

-------------------------------------------------------------------------------

CREATE TABLE _mapping (
	mapping_id serial PRIMARY KEY,
	parent integer REFERENCES _mapping,
	identifier varchar(32) UNIQUE NOT NULL,
	modname text NOT NULL,
	private boolean NOT NULL DEFAULT 'FALSE',
	owner int REFERENCES users,
	ord int,
	tree_order text
);
CREATE UNIQUE INDEX _mapping_unique_tree_order ON _mapping (ord, coalesce(parent, 0));

CREATE OR REPLACE FUNCTION _mapping_tree_order(mapping_id int) RETURNS text AS $$
  SELECT
    CASE WHEN $1 IS NULL THEN '' ELSE
      (SELECT _mapping_tree_order(parent) || '.' || to_char(coalesce(ord, 999999), 'FM000000')
       FROM _mapping where mapping_id=$1)
    END
  AS RESULT
$$ LANGUAGE SQL;

CREATE OR REPLACE VIEW mapping AS SELECT * FROM _mapping;

-------------------------------------------------------------------------------

CREATE TABLE _menu (
       mapping_id integer NOT NULL REFERENCES _mapping ON DELETE CASCADE,
       lang char(2) NOT NULL REFERENCES languages(lang) ON DELETE CASCADE,
       title text NOT NULL,
       description text,
       published boolean NOT NULL DEFAULT 'TRUE',
       UNIQUE (mapping_id, lang)
);

CREATE OR REPLACE VIEW menu AS
SELECT _mapping.mapping_id ||'.'|| l.lang as menu_id,
       l.lang, m.title, m.description, coalesce(m.published, 'FALSE') as published,
       coalesce(m.title, _mapping.identifier) as title_or_identifier, _mapping.*
FROM _mapping CROSS JOIN languages l LEFT OUTER JOIN _menu m USING (mapping_id, lang);

CREATE OR REPLACE RULE menu_insert AS
  ON INSERT TO menu DO INSTEAD (
     INSERT INTO _mapping 
        (parent, identifier, modname, private, owner, ord)
     VALUES
        (new.parent, new.identifier, new.modname, new.private, new.owner, new.ord);
     UPDATE _mapping SET tree_order = _mapping_tree_order(mapping_id);
     INSERT INTO _menu (mapping_id, lang, title, description, published)
            VALUES ((SELECT mapping_id FROM _mapping WHERE identifier=new.identifier),
                    new.lang, new.title, new.description, new.published)
);

CREATE OR REPLACE RULE menu_update AS
  ON UPDATE TO menu DO INSTEAD (
    UPDATE _mapping SET
     	parent = new.parent,
        identifier = new.identifier,
        modname = new.modname,
        private = new.private,
        owner = new.owner,
        ord = new.ord
    WHERE _mapping.mapping_id = old.mapping_id;
    UPDATE _mapping SET	tree_order = _mapping_tree_order(mapping_id);
    UPDATE _menu SET title = new.title,
                     description = new.description,
		     published = new.published
           WHERE mapping_id = old.mapping_id AND lang = new.lang;
    INSERT INTO _menu (mapping_id, lang, title, description, published)
       	   SELECT old.mapping_id, new.lang, new.title, new.description, new.published
           WHERE new.lang NOT IN (SELECT lang FROM _menu WHERE mapping_id=old.mapping_id);
);

CREATE OR REPLACE RULE menu_delete AS
  ON DELETE TO menu DO INSTEAD (
     DELETE FROM _mapping
     WHERE _mapping.mapping_id = old.mapping_id;
);

-------------------------------------------------------------------------------

CREATE TABLE _pages (
	mapping_id integer NOT NULL REFERENCES _mapping ON DELETE CASCADE,
	lang char(2) NOT NULL REFERENCES languages(lang),
	_content text NOT NULL,
	content text,
	PRIMARY KEY (mapping_id, lang)
);

CREATE OR REPLACE VIEW pages AS 
SELECT map.mapping_id ||'.'|| l.lang as page_id, map.mapping_id, l.lang,
       map.identifier, map.parent, map.tree_order, map.owner,
       menu.title, menu.description, coalesce(menu.published, 'FALSE') as published,
       coalesce(menu.title, map.identifier) as title_or_identifier, 
       p._content, p.content
FROM _mapping map CROSS JOIN languages l
     LEFT OUTER JOIN _pages p USING (mapping_id, lang)
     LEFT OUTER JOIN _menu menu USING (mapping_id, lang)
WHERE map.modname = 'Pages';

CREATE OR REPLACE RULE pages_insert AS
  ON INSERT TO pages DO INSTEAD (
     INSERT INTO _mapping (identifier, modname, private, owner)
     VALUES (new.identifier, 'Pages', 'f', new.owner);
     INSERT INTO _pages (mapping_id, lang, _content, content)
     VALUES ((SELECT mapping_id FROM _mapping WHERE identifier=new.identifier),
             new.lang, new._content, new.content);
     INSERT INTO _menu (mapping_id, lang, title, description, published)
     VALUES ((SELECT mapping_id FROM _mapping WHERE identifier=new.identifier),
	     new.lang, new.title, new.description, new.published)
);

CREATE OR REPLACE RULE pages_update AS
  ON UPDATE TO pages DO INSTEAD (
    UPDATE _pages SET _content = new._content, content = new.content
           WHERE old._content IS NOT NULL 
	         AND mapping_id = old.mapping_id AND lang = old.lang;
    INSERT INTO _pages (mapping_id, lang, _content, content) 
	   SELECT new.mapping_id, new.lang, new._content, new.content
	   WHERE old._content IS NULL;
    UPDATE _menu SET title = new.title, description = new.description, published = new.published
           WHERE mapping_id = old.mapping_id AND lang = old.lang;
    INSERT INTO _menu (mapping_id, lang, title, description, published) 
    	   SELECT old.mapping_id, new.lang, new.title, new.description, new.published
           WHERE new.lang NOT IN (SELECT lang FROM _menu WHERE mapping_id=old.mapping_id);
);

CREATE OR REPLACE RULE pages_delete AS
  ON DELETE TO pages DO INSTEAD (
     DELETE FROM _mapping WHERE mapping_id = old.mapping_id;
);

-------------------------------------------------------------------------------

CREATE TABLE _attachments (
       attachment_id serial PRIMARY KEY,
       mapping_id int NOT NULL REFERENCES _mapping ON DELETE CASCADE,
       filename varchar(64) NOT NULL,
       mime_type text NOT NULL,
       bytesize text NOT NULL,
       listed boolean NOT NULL DEFAULT 'TRUE',
       "timestamp" timestamp NOT NULL DEFAULT now(),
       UNIQUE (mapping_id, filename)
);

CREATE TABLE _attachment_descr (
       attachment_id int NOT NULL REFERENCES _attachments ON DELETE CASCADE,
       lang char(2) NOT NULL REFERENCES languages(lang) ON DELETE CASCADE,
       title text,
       description text,
       UNIQUE (attachment_id, lang)
);

CREATE OR REPLACE VIEW attachments
AS SELECT a.attachment_id  ||'.'|| l.lang as page_attachment_id,
  a.attachment_id, l.lang, a.mapping_id ||'.'|| l.lang as page_id, 
  a.mapping_id, m.identifier, a.filename, a.mime_type, a.bytesize, a.listed,
  a."timestamp", d.title, d.description, current_database() as dbname 
FROM _attachments a JOIN _mapping m USING (mapping_id) CROSS JOIN languages l  
LEFT OUTER JOIN _attachment_descr d USING (attachment_id, lang);

CREATE OR REPLACE RULE attachments_insert AS
 ON INSERT TO attachments DO INSTEAD (
    INSERT INTO _attachments (attachment_id, mapping_id, filename, mime_type,
                              bytesize, listed)
            VALUES (new.attachment_id, new.mapping_id, new.filename, 
                    new.mime_type, new.bytesize, new.listed);
    INSERT INTO _attachment_descr (attachment_id, lang, title, description)
           SELECT new.attachment_id, new.lang, new.title, new.description
           WHERE new.title IS NOT NULL OR new.description IS NOT NULL;
);

CREATE OR REPLACE RULE attachments_update AS
 ON UPDATE TO attachments DO INSTEAD (
    UPDATE _attachments SET 
    	   mapping_id = new.mapping_id, 
	   filename = new.filename,
	   mime_type = new.mime_type,
	   bytesize = new.bytesize,
	   listed = new.listed	
           WHERE attachment_id = old.attachment_id;
    UPDATE _attachment_descr SET title=new.title, description=new.description
       	   WHERE attachment_id = old.attachment_id AND lang = old.lang;
    INSERT INTO _attachment_descr (attachment_id, lang, title, description) 
   	   SELECT new.attachment_id, new.lang, new.title, new.description
	   WHERE new.attachment_id NOT IN
             (SELECT attachment_id FROM _attachment_descr WHERE lang=new.lang);
);

CREATE OR REPLACE RULE attachments_delete AS
  ON DELETE TO attachments DO INSTEAD (
     DELETE FROM _attachments WHERE attachment_id = old.attachment_id;
);

-------------------------------------------------------------------------------

CREATE TABLE _panels (
	panel_id serial PRIMARY KEY,
	lang char(2) NOT NULL REFERENCES languages(lang),
	ptitle text,
	ord int,
	mapping_id integer REFERENCES _mapping,
	size int,
	content text,
	_content text,
	published boolean NOT NULL DEFAULT 'FALSE'
);

CREATE OR REPLACE VIEW panels AS 
SELECT _panels.*, _mapping.modname, _mapping.identifier, _mapping.private, _menu.title as mtitle
FROM _panels 
     LEFT OUTER JOIN _mapping USING (mapping_id) 
     LEFT OUTER JOIN _menu USING (mapping_id, lang);

CREATE OR REPLACE RULE panels_insert AS
  ON INSERT TO panels DO INSTEAD (
     INSERT INTO _panels 
        (lang, ptitle, ord, mapping_id, size, content, _content, published)
     VALUES
        (new.lang, new.ptitle, new.ord, new.mapping_id, new.size, 
	 new.content, new._content, new.published)
);

CREATE OR REPLACE RULE panels_update AS
  ON UPDATE TO panels DO INSTEAD (
    UPDATE _panels SET
	lang = new.lang,
	ptitle = new.ptitle,
	ord = new.ord,
	mapping_id = new.mapping_id,
	size = new.size,
	content = new.content,
	_content = new._content,
	published = new.published
    WHERE _panels.panel_id = old.panel_id;
);

CREATE OR REPLACE RULE panels_delete AS
  ON DELETE TO panels DO INSTEAD (
     DELETE FROM _panels
     WHERE _panels.panel_id = old.panel_id;
);

-------------------------------------------------------------------------------

CREATE TABLE news (
	news_id serial PRIMARY KEY,
	lang char(2) NOT NULL REFERENCES languages(lang),
	"timestamp" timestamp NOT NULL DEFAULT now(),
	title text NOT NULL,
	author int NOT NULL REFERENCES users,
	content text NOT NULL
);

-------------------------------------------------------------------------------

CREATE TABLE planner (
	planner_id serial PRIMARY KEY,
	lang char(2) NOT NULL REFERENCES languages(lang),
	start_date date NOT NULL,
	end_date date,
	title text NOT NULL,
	author int NOT NULL REFERENCES users,
	"timestamp" timestamp NOT NULL DEFAULT now(),
	content text NOT NULL,
	UNIQUE (start_date, lang, title)
);

-------------------------------------------------------------------------------

CREATE TABLE _images (
       	image_id serial PRIMARY KEY,
	filename varchar(64) NOT NULL,
	format varchar(4) NOT NULL,
	published boolean NOT NULL DEFAULT 'TRUE',
	width int NOT NULL,
	height int NOT NULL,
	"size" text NOT NULL,
	bytesize text NOT NULL,
	title text NOT NULL,
	author text,
	"location" text,
	description text,
	taken timestamp,
	exif text,
	"timestamp" timestamp NOT NULL DEFAULT now()
);

CREATE OR REPLACE VIEW images AS 
SELECT *, current_database() as dbname FROM _images;

CREATE OR REPLACE RULE images_insert AS
  ON INSERT TO images DO INSTEAD (
     INSERT INTO _images (image_id, filename, format, published, width,
     	height, "size", bytesize, title, author,
	"location", description, taken, exif, "timestamp")
     VALUES (new.image_id, new.filename, new.format, new.published, new.width,
     	new.height, new."size", new.bytesize, new.title, new.author,
	new."location", new.description, new.taken, new.exif, new."timestamp");
);

CREATE OR REPLACE RULE images_update AS
  ON UPDATE TO images DO INSTEAD (
    UPDATE _images SET
      filename = new.filename,
      format = new.format,
      published = new.published,
      width = new.width,
      height = new.height,
      "size" = new."size",
      bytesize = new.bytesize,
      title = new.title,
      author = new.author,
      "location" = new."location",
      description = new.description,
      taken = new.taken,
      exif = new.exif,
      "timestamp" = new."timestamp"
   WHERE image_id = old.image_id
);

CREATE OR REPLACE RULE images_delete AS
  ON DELETE TO images DO INSTEAD (
     DELETE FROM _images WHERE image_id = old.image_id;
);

-------------------------------------------------------------------------------

CREATE TABLE stylesheets (
	stylesheet_id serial PRIMARY KEY,
	identifier varchar(32) UNIQUE NOT NULL,
	active boolean NOT NULL DEFAULT 'TRUE',
	description text,
	content text
);

-------------------------------------------------------------------------------

CREATE TABLE themes (
	theme_id serial PRIMARY KEY,
	name text UNIQUE NOT NULL,	
        foreground varchar(7),
        background varchar(7),
        border varchar(7),
        heading_fg varchar(7),
        heading_bg varchar(7),
        heading_line varchar(7),
        frame_fg varchar(7),
        frame_bg varchar(7),
        frame_border varchar(7),
        link varchar(7),
        link_visited varchar(7),
        link_hover varchar(7),
        meta_fg varchar(7),
        meta_bg varchar(7),
        help varchar(7),
        error_fg varchar(7),
        error_bg varchar(7),
        error_border varchar(7),
        message_fg varchar(7),
        message_bg varchar(7),
        message_border varchar(7),
        table_cell varchar(7),
        table_cell2 varchar(7),
        button_fg varchar(7),
        button varchar(7),
        button_hover varchar(7),
        button_border varchar(7),
        button_inactive_fg varchar(7),
        button_inactive varchar(7),
        button_inactive_border varchar(7),
        top_fg varchar(7),
        top_bg varchar(7),
        top_border varchar(7),
        highlight_bg varchar(7),
        inactive_folder varchar(7)
);

-------------------------------------------------------------------------------

CREATE TABLE config (
	config_id int PRIMARY KEY DEFAULT 0 CHECK (config_id = 0),
	site_title text NOT NULL,
	site_subtitle text,
	allow_login_panel boolean NOT NULL DEFAULT 'FALSE',
	allow_registration boolean NOT NULL DEFAULT 'TRUE',
	force_https_login boolean NOT NULL DEFAULT 'FALSE',
	webmaster_addr text,
	upload_limit int,
	theme integer REFERENCES themes
);

--CREATE TABLE changes (
--	content_id integer NOT NULL REFERENCES content ON DELETE CASCADE,
--	author text NOT NULL,
--	time timestamp NOT NULL DEFAULT now(),
--	message text,
--);


--CREATE TABLE "session" (
--	login varchar(32) PRIMARY KEY,
--	"key" text NOT NULL,
--	expire timestamp NOT NULL
--);
