-- Wiking database creation script. --

CREATE TABLE languages (
	lang_id serial PRIMARY KEY,
	lang char(2) UNIQUE NOT NULL
);

-------------------------------------------------------------------------------

CREATE TABLE users (
	uid serial PRIMARY KEY,
	login varchar(32) UNIQUE NOT NULL,
	password varchar(32),
	firstname text NOT NULL,
	surname text NOT NULL,
	nickname text,
	user_ text NOT NULL,
	email text NOT NULL,
	phone text,
	address text,
	uri text,
	role char(4) NOT NULL DEFAULT 'none',
	since timestamp NOT NULL DEFAULT current_timestamp(0),
	lang char(2) REFERENCES languages(lang),
        regexpire timestamp,
        regcode char(16),
        certauth boolean DEFAULT 'FALSE'
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

CREATE TABLE _mapping (
	mapping_id serial PRIMARY KEY,
	identifier varchar(32) UNIQUE NOT NULL,
	parent integer REFERENCES _mapping,
	modname text,
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

CREATE TABLE _pages (
       mapping_id integer NOT NULL REFERENCES _mapping ON DELETE CASCADE,
       lang char(2) NOT NULL REFERENCES languages(lang),
       title text NOT NULL,
       description text,
       published boolean NOT NULL DEFAULT 'TRUE',
       _content text,
       content text,
       PRIMARY KEY (mapping_id, lang)
);

CREATE OR REPLACE VIEW pages AS 
SELECT m.mapping_id ||'.'|| l.lang as page_id, l.lang, m.*,
       p.title, p.description, coalesce(p.published, 'FALSE') as published,
       coalesce(p.title, m.identifier) as title_or_identifier, 
       p._content, p.content
FROM _mapping m CROSS JOIN languages l
     LEFT OUTER JOIN _pages p USING (mapping_id, lang);

CREATE OR REPLACE RULE pages_insert AS
  ON INSERT TO pages DO INSTEAD (
     INSERT INTO _mapping (identifier, parent, modname, private, owner, ord)
     VALUES (new.identifier, new.parent, new.modname, new.private, new.owner, new.ord);
     UPDATE _mapping SET tree_order = _mapping_tree_order(mapping_id);
     INSERT INTO _pages (mapping_id, lang, title, description, published, _content, content)
     SELECT (SELECT mapping_id FROM _mapping WHERE identifier=new.identifier),
             new.lang, new.title, new.description, new.published, new._content, new.content
     WHERE new.title IS NOT NULL;
);

CREATE OR REPLACE RULE pages_update AS
  ON UPDATE TO pages DO INSTEAD (
    UPDATE _mapping SET
        identifier = new.identifier,
     	parent = new.parent,
        modname = new.modname,
        private = new.private,
        owner = new.owner,
        ord = new.ord
    WHERE _mapping.mapping_id = old.mapping_id;
    UPDATE _mapping SET	tree_order = _mapping_tree_order(mapping_id);
    UPDATE _pages SET
    	title = new.title,
	description = new.description,
	published = new.published,
        _content = new._content,
	content = new.content
    WHERE mapping_id = old.mapping_id AND lang = new.lang;
    INSERT INTO _pages (mapping_id, lang, title, description, published, _content, content) 
	   SELECT old.mapping_id, new.lang, new.title, new.description, new.published,
		  new._content, new.content
           WHERE new.lang NOT IN (SELECT lang FROM _pages WHERE mapping_id=old.mapping_id)
	   	 AND (new.title IS NOT NULL OR new.description IS NOT NULL 
                      OR new._content IS NOT NULL OR new.content IS NOT NULL);
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
SELECT _panels.*, _mapping.modname, _mapping.identifier, _mapping.private, _pages.title as mtitle
FROM _panels 
     LEFT OUTER JOIN _mapping USING (mapping_id) 
     LEFT OUTER JOIN _pages USING (mapping_id, lang);

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

CREATE TABLE text_labels (
         label varchar(64) PRIMARY KEY
);

CREATE TABLE _texts (
        label varchar(64) NOT NULL REFERENCES text_labels,
        lang char(2) NOT NULL REFERENCES languages(lang),
        content text DEFAULT '',
        PRIMARY KEY (label, lang)
);

CREATE OR REPLACE VIEW texts AS
SELECT label || '@' || lang as text_id, label, lang, coalesce(content, '') as content
FROM text_labels CROSS JOIN languages LEFT OUTER JOIN _texts USING (label, lang);

CREATE OR REPLACE RULE texts_update AS
  ON UPDATE TO texts DO INSTEAD (
    DELETE FROM _texts WHERE label = new.label AND lang = new.lang;
    INSERT INTO _texts VALUES (new.label, new.lang, new.content);
);

-------------------------------------------------------------------------------

CREATE TABLE config (
	config_id int PRIMARY KEY DEFAULT 0 CHECK (config_id = 0),
	site_title text NOT NULL,
	site_subtitle text,
	allow_login_panel boolean NOT NULL DEFAULT 'TRUE',
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

-------------------------------------------------------------------------------

CREATE TABLE cacertificates (
       cacertificates_id serial PRIMARY KEY,
       certificate text NOT NULL,
       serial_number int NOT NULL,
       text text NOT NULL,  -- human readable form of the certificate
       issuer text NOT NULL,  -- CN, i.e. the authority
       valid_from timestamp NOT NULL,
       valid_until timestamp NOT NULL,
       trusted boolean DEFAULT 'FALSE'
);

CREATE TABLE certificates (
       certificates_id serial PRIMARY KEY,
       certificate text NOT NULL,
       serial_number int NOT NULL,
       text text NOT NULL,  -- human readable form of the certificate
       common_name text NOT NULL,
       email text,
       issuer text NOT NULL,
       valid_from timestamp NOT NULL,
       valid_until timestamp NOT NULL,
       trusted boolean DEFAULT 'FALSE',
       uid int REFERENCES users NOT NULL,
       purpose int NOT NULL -- 0=none, 1=authentication, 2=signing, 3=1+2
);
CREATE INDEX certificates_serial_number ON certificates (serial_number);
CREATE INDEX certificates_uid ON certificates (uid);
CREATE OR REPLACE RULE certificates_insert AS
  ON INSERT TO certificates DO
  DELETE FROM certificates WHERE uid = new.uid AND purpose = 1 AND purpose = new.purpose AND serial_number != new.serial_number;

CREATE SEQUENCE certificate_serial_number;
