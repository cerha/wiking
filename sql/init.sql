-- Wiking initial data --

INSERT INTO languages (lang) VALUES ('en'); 

INSERT INTO modules (name, active) VALUES ('Content', 't');
INSERT INTO modules (name, active) VALUES ('News', 't');
INSERT INTO modules (name, active) VALUES ('Panels', 't');
INSERT INTO modules (name, active) VALUES ('Users', 'f');
INSERT INTO modules (name, active) VALUES ('Titles', 't');
INSERT INTO modules (name, active) VALUES ('Stylesheets', 't');
INSERT INTO modules (name, active) VALUES ('Themes', 't');
INSERT INTO modules (name, active) VALUES ('Languages', 't');

INSERT INTO _mapping (identifier, mod_id, published, ord) 
VALUES ('index', 1, 't', 1);

INSERT INTO _mapping (identifier, mod_id, published, ord) 
VALUES ('css', 2, 't', NULL);

INSERT INTO content (mapping_id, lang, title, content) 
VALUES (1, 'en', 'Welcome', 
	'Your new Wiking site has been succesfully set up.\n\n'||
	'Enter the [/wmi Wiking Management Interface] to manage the content.');

INSERT INTO config (site_title) VALUES ('Wiking site');

INSERT INTO stylesheets (identifier) VALUES ('default.css');
INSERT INTO stylesheets (identifier) VALUES ('panels.css');

