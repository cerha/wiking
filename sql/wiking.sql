-- Wiking database creation script.
-- when using interactively, don't forget to:
-- REVOKE ALL on object from PUBLIC;
-- GRANT ALL on object to "www-data";

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

--------------------------------------------------------------------------------

CREATE TABLE modules (
	mod_id serial PRIMARY KEY,
	name varchar(32) UNIQUE,
	active boolean NOT NULL DEFAULT 'TRUE'
) WITH OIDS;

--------------------------------------------------------------------------------

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

--------------------------------------------------------------------------------

CREATE TABLE languages (
	lang_id serial PRIMARY KEY,
	lang char(2) UNIQUE NOT NULL
) WITH OIDS;

--------------------------------------------------------------------------------

CREATE TABLE titles (
	title_id serial PRIMARY KEY,
	mapping_id integer NOT NULL REFERENCES _mapping ON DELETE CASCADE,
	lang char(2) NOT NULL REFERENCES languages(lang) ON DELETE CASCADE,
	title text NOT NULL,
	UNIQUE (mapping_id, lang)
) WITH OIDS;

--------------------------------------------------------------------------------

CREATE TABLE _content (
	content_id serial PRIMARY KEY,
	mapping_id integer NOT NULL REFERENCES _mapping ON DELETE CASCADE,
	lang char(2) NOT NULL REFERENCES languages(lang),
	published boolean NOT NULL DEFAULT 'TRUE',
	content text,
	_content text,
	UNIQUE (mapping_id, lang)
) WITH OIDS;

CREATE OR REPLACE VIEW content AS 
SELECT c.oid, m.identifier, t.title, c.* 
FROM (_content c JOIN _mapping m USING (mapping_id))
     NATURAL LEFT OUTER JOIN titles t;

CREATE OR REPLACE RULE content_insert AS
  ON INSERT TO content DO INSTEAD (
     INSERT INTO _content (mapping_id, lang, content, _content)
     VALUES (new.mapping_id, new.lang, new.content, new._content);
     INSERT INTO titles (mapping_id, lang, title)
     VALUES (new.mapping_id, new.lang, new.title)
	);

CREATE OR REPLACE RULE content_update AS
  ON UPDATE TO content DO INSTEAD (
    UPDATE _content SET
	published = new.published,
	content   = new.content,
	_content  = new._content
    WHERE _content.content_id = old.content_id;
    UPDATE titles SET
	title = new.title
    WHERE titles.mapping_id = old.mapping_id 
          AND titles.lang = old.lang;
    INSERT INTO titles (mapping_id, lang, title) 
	   SELECT new.mapping_id, new.lang, new.title
	   WHERE old.title IS NULL AND new.title IS NOT NULL;
);

CREATE OR REPLACE RULE content_delete AS
  ON DELETE TO content DO INSTEAD (
     DELETE FROM titles
     WHERE titles.mapping_id = old.mapping_id AND titles.lang = old.lang;
     DELETE FROM _content
     WHERE _content.content_id = old.content_id;
);

--------------------------------------------------------------------------------

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

--------------------------------------------------------------------------------

CREATE TABLE news (
	news_id serial PRIMARY KEY,
	title text NOT NULL,
	lang char(2) NOT NULL REFERENCES languages(lang),
	content text NOT NULL,
	"timestamp" timestamp NOT NULL DEFAULT now()
) WITH OIDS;

--------------------------------------------------------------------------------

CREATE TABLE stylesheets (
	stylesheet_id serial PRIMARY KEY,
	identifier varchar(32) UNIQUE NOT NULL,
	active boolean NOT NULL DEFAULT 'TRUE',
	description text,
	content text
) WITH OIDS;

--------------------------------------------------------------------------------

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
        error_fg varchar(7),
        error_bg varchar(7),
        error_border varchar(7),
        message_fg varchar(7),
        message_bg varchar(7),
        message_border varchar(7)
) WITH OIDS;

--------------------------------------------------------------------------------

CREATE TABLE users (
	uid serial PRIMARY KEY,
	login varchar(32) UNIQUE NOT NULL,
	password varchar(32) NOT NULL,
	firstname text,
	surname text,
	nickname text,
	email text,
	phone text,
	address text,
	uri text,
	enabled boolean NOT NULL DEFAULT 'FALSE',
	since timestamp NOT NULL DEFAULT current_timestamp(0)
) WITH OIDS;

CREATE TABLE config (
	config_id int PRIMARY KEY DEFAULT 0 CHECK (config_id = 0),
	site_title text NOT NULL,
	site_subtitle text,
	webmaster_addr text,
	theme integer REFERENCES themes
) WITH OIDS;

--   "session_key" text,
--   "session_expire" timestamp
--   "enabled" bool DEFAULT 'FALSE' NOT NULL,


--CREATE TABLE changes (
--	content_id integer NOT NULL REFERENCES content ON DELETE CASCADE,
--	author text NOT NULL,
--	time timestamp NOT NULL DEFAULT now(),
--	message text,
--);
