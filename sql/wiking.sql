-- Wiking database creation script. --
-- -*- indent-tabs-mode: nil -*-

CREATE TABLE languages (
	lang_id serial PRIMARY KEY,
	lang char(2) UNIQUE NOT NULL
);

-------------------------------------------------------------------------------

CREATE TABLE organizations (
       organization_id serial PRIMARY KEY,
       name varchar(128) NOT NULL UNIQUE,
       vatid varchar(16) NOT NULL UNIQUE,
       phone text,
       email text,
       address text,
       notes text
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
        certauth boolean NOT NULL DEFAULT 'FALSE',
        organization text, -- free form field just for registration
        organization_id int REFERENCES organizations
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
	hidden boolean NOT NULL,
	ord int NOT NULL,
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
       published boolean NOT NULL DEFAULT 'TRUE',
       title text NOT NULL,
       description text,
       content text,
       _title text,
       _description text,
       _content text,
       PRIMARY KEY (mapping_id, lang)
);

CREATE OR REPLACE VIEW pages AS 
SELECT m.mapping_id ||'.'|| l.lang as page_id, l.lang, 
       m.mapping_id, m.identifier, m.parent, m.modname, 
       m.private, m.owner, m.hidden, m.ord, m.tree_order,
       coalesce(p.published, 'FALSE') as published,
       coalesce(p.title, m.identifier) as title_or_identifier, 
       p.title, p.description, p.content, p._title, p._description, p._content
FROM _mapping m CROSS JOIN languages l
     LEFT OUTER JOIN _pages p USING (mapping_id, lang);

CREATE OR REPLACE RULE pages_insert AS
  ON INSERT TO pages DO INSTEAD (
     INSERT INTO _mapping (identifier, parent, modname, private, owner, hidden, ord)
     VALUES (new.identifier, new.parent, new.modname, new.private, new.owner, new.hidden, 
             coalesce(new.ord, (SELECT max(ord)+100 FROM _mapping 
                                WHERE coalesce(parent, 0)=coalesce(new.parent, 0)), 100));
     UPDATE _mapping SET tree_order = _mapping_tree_order(mapping_id);
     INSERT INTO _pages (mapping_id, lang, published, 
                         title, description, content, _title, _description, _content)
     SELECT (SELECT mapping_id FROM _mapping WHERE identifier=new.identifier),
            new.lang, new.published, 
            new.title, new.description, new.content, new._title, new._description, new._content
     RETURNING mapping_id ||'.'|| lang, 
       lang, mapping_id, NULL::varchar(32), NULL::int, NULL::text, NULL::boolean, NULL::int,
       NULL::boolean, NULL::int, NULL::text, published, title, title, description, content, _title,
       _description, _content
);

CREATE OR REPLACE RULE pages_update AS
  ON UPDATE TO pages DO INSTEAD (
    UPDATE _mapping SET
        identifier = new.identifier,
        parent = new.parent,
        modname = new.modname,
        private = new.private,
        owner = new.owner,
        hidden = new.hidden,
        ord = new.ord
    WHERE _mapping.mapping_id = old.mapping_id;
    UPDATE _mapping SET tree_order = _mapping_tree_order(mapping_id);
    UPDATE _pages SET
        published = new.published,
        title = new.title,
        description = new.description,
        content = new.content,
        _title = new._title,
        _description = new._description,
        _content = new._content
    WHERE mapping_id = old.mapping_id AND lang = new.lang;
    INSERT INTO _pages (mapping_id, lang, published, 
                        title, description, content, _title, _description, _content) 
           SELECT old.mapping_id, new.lang, new.published, 
                  new.title, new.description, new.content, 
                  new._title, new._description, new._content
           WHERE new.lang NOT IN (SELECT lang FROM _pages WHERE mapping_id=old.mapping_id)
                 AND (new.title IS NOT NULL OR new.description IS NOT NULL 
                      OR new.content IS NOT NULL 
                      OR new._title IS NOT NULL OR new._description IS NOT NULL 
                      OR new._content IS NOT NULL);
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
       attachment_id int NOT NULL REFERENCES _attachments ON DELETE CASCADE INITIALLY DEFERRED,
       lang char(2) NOT NULL REFERENCES languages(lang) ON DELETE CASCADE,
       title text,
       description text,
       UNIQUE (attachment_id, lang)
);

CREATE TABLE _images (
       attachment_id int NOT NULL REFERENCES _attachments ON DELETE CASCADE INITIALLY DEFERRED,
       width int NOT NULL,
       height int NOT NULL,
       author text,
       "location" text,
       exif_date timestamp,
       exif text
);

CREATE OR REPLACE VIEW attachments
AS SELECT a.attachment_id  ||'.'|| l.lang as attachment_variant_id, l.lang,
  a.attachment_id, a.mapping_id, a.filename, a.mime_type, a.bytesize, a.listed, a."timestamp",
  d.title, d.description, i.width IS NOT NULL as is_image,
  i.width, i.height, i.author, i."location", i.exif_date, i.exif
FROM _attachments a JOIN _mapping m USING (mapping_id) CROSS JOIN languages l
     LEFT OUTER JOIN _attachment_descr d USING (attachment_id, lang)
     LEFT OUTER JOIN _images i USING (attachment_id);

CREATE OR REPLACE RULE attachments_insert AS
 ON INSERT TO attachments DO INSTEAD (
    INSERT INTO _attachment_descr (attachment_id, lang, title, description)
           SELECT new.attachment_id, new.lang, new.title, new.description
           WHERE new.title IS NOT NULL OR new.description IS NOT NULL;
    INSERT INTO _images (attachment_id, width, height, author, "location", exif_date, exif)
           SELECT new.attachment_id, new.width, new.height, new.author, new."location",
                  new.exif_date, new.exif
           WHERE new.is_image;
    INSERT INTO _attachments (attachment_id, mapping_id, filename, mime_type, bytesize, listed)
           VALUES (new.attachment_id, new.mapping_id, new.filename,
                   new.mime_type, new.bytesize, new.listed)
           RETURNING
             attachment_id ||'.'|| (SELECT max(lang) FROM _attachment_descr
                                    WHERE attachment_id=attachment_id),  NULL::char(2),
             attachment_id, mapping_id, filename, mime_type, bytesize, listed, "timestamp",
             NULL::text, NULL::text, NULL::boolean, NULL::int, NULL::int, NULL::text, NULL::text,
             NULL::timestamp, NULL::text
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
    UPDATE _images SET
           width = new.width,
           height = new.height,
           author = new.author,
           "location" = new."location",
           exif_date = new.exif_date,
           exif = new.exif
           WHERE attachment_id = old.attachment_id;
    UPDATE _attachment_descr SET title=new.title, description=new.description
           WHERE attachment_id = old.attachment_id AND lang = old.lang;
    INSERT INTO _attachment_descr (attachment_id, lang, title, description)
           SELECT new.attachment_id, new.lang, new.title, new.description
           WHERE old.attachment_id NOT IN
             (SELECT attachment_id FROM _attachment_descr WHERE lang=old.lang);
);

CREATE OR REPLACE RULE attachments_delete AS
  ON DELETE TO attachments DO INSTEAD (
     DELETE FROM _attachments WHERE attachment_id = old.attachment_id;
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
