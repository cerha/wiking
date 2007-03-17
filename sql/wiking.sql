-- Wiking database creation script. --

CREATE TABLE _rowlocks ( 
   id      int, 
   row     oid,
   usename name,
   expires timestamp
);

CREATE TABLE _rowlocks_real (
   id      serial    PRIMARY KEY,                     -- lock identification
   row     oid       NOT NULL,                        -- locked row oid
   usename name      NOT NULL default session_user,   -- locking user
   expires timestamp NOT NULL DEFAULT now() + '00:01' -- lock expiration time
);

CREATE OR REPLACE RULE "_RET_rowlocks" AS ON SELECT to _rowlocks DO INSTEAD
  SELECT * FROM _rowlocks_real WHERE expires > now();

CREATE OR REPLACE RULE _rowlocks_insert AS ON INSERT TO _rowlocks DO INSTEAD
  INSERT INTO _rowlocks_real (row) VALUES (new.row);

CREATE OR REPLACE RULE _rowlocks_update AS ON UPDATE TO _rowlocks DO INSTEAD
  UPDATE _rowlocks_real SET expires = now() + '00:01'
  WHERE id = old.id AND expires > now();

CREATE OR REPLACE RULE _rowlocks_delete AS ON DELETE TO _rowlocks DO INSTEAD
  DELETE FROM _rowlocks_real WHERE id = old.id OR expires <= now();

-------------------------------------------------------------------------------

CREATE TABLE modules (
	mod_id serial PRIMARY KEY,
	name varchar(32) UNIQUE,
	ord  int,
	active boolean NOT NULL DEFAULT 'TRUE'
) WITH OIDS;

-------------------------------------------------------------------------------

CREATE TABLE _mapping (
	mapping_id serial PRIMARY KEY,
	parent integer REFERENCES _mapping ON DELETE CASCADE,
	identifier varchar(32) UNIQUE NOT NULL,
	mod_id integer NOT NULL REFERENCES modules,
	published boolean NOT NULL DEFAULT 'FALSE',
	ord int
) WITH OIDS;

CREATE OR REPLACE VIEW mapping AS 
SELECT _mapping.oid, _mapping.*, modules.name as modname
FROM _mapping JOIN modules USING (mod_id);

CREATE OR REPLACE RULE mapping_insert AS
  ON INSERT TO mapping DO INSTEAD (
     INSERT INTO _mapping 
        (parent, identifier, mod_id, published, ord)
     VALUES
        (new.parent, new.identifier, new.mod_id, 
	 new.published, new.ord);
);

CREATE OR REPLACE RULE mapping_update AS
  ON UPDATE TO mapping DO INSTEAD (
    UPDATE _mapping SET
	parent = new.parent,
	identifier = new.identifier,
	mod_id = new.mod_id, 
	published = new.published,
	ord = new.ord
    WHERE _mapping.mapping_id = old.mapping_id;
);

CREATE OR REPLACE RULE mapping_delete AS
  ON DELETE TO mapping DO INSTEAD (
     DELETE FROM _mapping
     WHERE _mapping.mapping_id = old.mapping_id;
);

-------------------------------------------------------------------------------

CREATE TABLE languages (
	lang_id serial PRIMARY KEY,
	lang char(2) UNIQUE NOT NULL
) WITH OIDS;

-------------------------------------------------------------------------------

CREATE TABLE titles (
	title_id serial PRIMARY KEY,
	mapping_id integer NOT NULL REFERENCES _mapping ON DELETE CASCADE,
	lang char(2) NOT NULL REFERENCES languages(lang) ON DELETE CASCADE,
	title text NOT NULL,
	UNIQUE (mapping_id, lang)
) WITH OIDS;

-------------------------------------------------------------------------------

CREATE TABLE _pages (
	mapping_id integer NOT NULL REFERENCES _mapping ON DELETE CASCADE,
	lang char(2) NOT NULL REFERENCES languages(lang),
	_content text NOT NULL,
	content text,
	PRIMARY KEY (mapping_id, lang)
) WITH OIDS;

CREATE OR REPLACE VIEW pages AS 
SELECT p.oid, m.mapping_id ||'.'|| l.lang as page_id, m.mapping_id, l.lang,
       m.identifier, t.title, p._content, p.content
FROM _mapping m CROSS JOIN languages l JOIN modules USING (mod_id)
     LEFT OUTER JOIN _pages p USING (mapping_id, lang)
     LEFT OUTER JOIN titles t USING (mapping_id, lang)
WHERE modules.name = 'Pages';

CREATE OR REPLACE RULE pages_insert AS
  ON INSERT TO pages DO INSTEAD (
     INSERT INTO _mapping (identifier, mod_id)
     VALUES (new.identifier, (SELECT mod_id FROM modules WHERE name='Pages'));
     INSERT INTO _pages (mapping_id, lang, _content, content)
     VALUES ((SELECT mapping_id FROM _mapping WHERE identifier=new.identifier),
             new.lang, new._content, new.content);
     INSERT INTO titles (mapping_id, lang, title)
     VALUES ((SELECT mapping_id FROM _mapping WHERE identifier=new.identifier),
	     new.lang, new.title)
);

CREATE OR REPLACE RULE pages_update AS
  ON UPDATE TO pages DO INSTEAD (
    UPDATE _pages SET _content = new._content, content = new.content
           WHERE old._content IS NOT NULL 
	         AND mapping_id = old.mapping_id AND lang = old.lang;
    INSERT INTO _pages (mapping_id, lang, _content, content) 
	   SELECT new.mapping_id, new.lang, new._content, new.content
	   WHERE old._content IS NULL;
    UPDATE titles SET title = new.title
           WHERE mapping_id = old.mapping_id AND lang = old.lang;
    INSERT INTO titles (mapping_id, lang, title) 
	   SELECT new.mapping_id, new.lang, new.title
	   WHERE old.title IS NULL AND new.title IS NOT NULL;
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
) WITH OIDS;

CREATE TABLE _attachment_descr (
       attachment_id int NOT NULL REFERENCES _attachments ON DELETE CASCADE,
       lang char(2) NOT NULL REFERENCES languages(lang),
       title text NOT NULL,
       description text
) WITH OIDS;

CREATE OR REPLACE VIEW attachments
AS SELECT a.oid, a.attachment_id  ||'.'|| l.lang as page_attachment_id,
  a.attachment_id, l.lang, a.mapping_id ||'.'|| l.lang as page_id, 
  a.mapping_id, m.identifier, a.filename, a.mime_type, a.bytesize, a.listed, a."timestamp",
  d.title, d.description, current_database() as dbname 
FROM _attachments a JOIN _mapping m USING (mapping_id) CROSS JOIN languages l  
LEFT OUTER JOIN _attachment_descr d USING (attachment_id, lang);

CREATE OR REPLACE RULE attachments_insert AS
 ON INSERT TO attachments DO INSTEAD (
    INSERT INTO _attachments (mapping_id, filename, mime_type, bytesize, listed)
    VALUES (new.mapping_id, new.filename, 
            new.mime_type, new.bytesize, new.listed);
    INSERT INTO _attachment_descr (attachment_id, lang, title, description)
    VALUES ((SELECT currval('_attachments_attachment_id_seq')),
    	     new.lang, new.title, new.description)
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
	   WHERE old.title IS NULL;
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
) WITH OIDS;

CREATE OR REPLACE VIEW panels AS 
SELECT _panels.oid, _panels.*, _mapping.mod_id, _mapping.identifier,
       modules.name as modname, t.title as mtitle
FROM _panels 
     LEFT OUTER JOIN _mapping USING (mapping_id) 
     LEFT OUTER JOIN modules  USING (mod_id)
     LEFT OUTER JOIN titles t USING (mapping_id, lang);

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
	content text NOT NULL
) WITH OIDS;

-------------------------------------------------------------------------------

CREATE TABLE planner (
	planner_id serial PRIMARY KEY,
	lang char(2) NOT NULL REFERENCES languages(lang),
	start_date date NOT NULL,
	end_date date,
	title text NOT NULL,
	content text,
	UNIQUE (start_date, lang, title)
) WITH OIDS;

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
) WITH OIDS;

CREATE OR REPLACE VIEW images AS 
SELECT oid, *, current_database() as dbname FROM _images;

CREATE OR REPLACE RULE images_insert AS
  ON INSERT TO images DO INSTEAD (
     INSERT INTO _images (filename, format, published, width,
	height, "size", bytesize, title, author,
	"location", description, taken, exif, "timestamp")
     VALUES (new.filename, new.format, new.published, new.width,
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
) WITH OIDS;

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
        table_cell varchar(7),
        table_cell2 varchar(7),
        top_fg varchar(7),
        top_bg varchar(7),
        top_border varchar(7),
        highlight_bg varchar(7),
        inactive_folder varchar(7),
        button_fg varchar(7),
        button varchar(7),
        button_border varchar(7),
        button_inactive_fg varchar(7),
        button_inactive varchar(7),
        button_inactive_border varchar(7),
        help varchar(7),
        error_fg varchar(7),
        error_bg varchar(7),
        error_border varchar(7),
        message_fg varchar(7),
        message_bg varchar(7),
        message_border varchar(7)
) WITH OIDS;

-------------------------------------------------------------------------------

CREATE TABLE users (
	uid serial PRIMARY KEY,
	login varchar(32) UNIQUE NOT NULL,
	password varchar(32) NOT NULL,
	firstname text NOT NULL,
	surname text NOT NULL,
	nickname text,
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
) WITH OIDS;

ALTER TABLE users ALTER COLUMN since 
      SET DEFAULT current_timestamp(0) AT TIME ZONE 'GMT';

CREATE TABLE config (
	config_id int PRIMARY KEY DEFAULT 0 CHECK (config_id = 0),
	site_title text NOT NULL,
	site_subtitle text,
	login_panel boolean NOT NULL DEFAULT 'FALSE',
	allow_registration boolean NOT NULL DEFAULT 'TRUE',
	webmaster_addr text,
	theme integer REFERENCES themes
) WITH OIDS;

--CREATE TABLE changes (
--	content_id integer NOT NULL REFERENCES content ON DELETE CASCADE,
--	author text NOT NULL,
--	time timestamp NOT NULL DEFAULT now(),
--	message text,
--);
