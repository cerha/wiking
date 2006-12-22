-- Wiking initial data --

INSERT INTO languages (lang) VALUES ('en');

INSERT INTO modules (name, active, ord) VALUES ('Content',     't', 10);
INSERT INTO modules (name, active, ord) VALUES ('News',        't', 20);
INSERT INTO modules (name, active, ord) VALUES ('Planner',     't', 30);
INSERT INTO modules (name, active, ord) VALUES ('Panels',      't', 40);
INSERT INTO modules (name, active, ord) VALUES ('Users',       'f', 50);
INSERT INTO modules (name, active, ord) VALUES ('Titles',      't', 60);
INSERT INTO modules (name, active, ord) VALUES ('Stylesheets', 't', 70);
INSERT INTO modules (name, active, ord) VALUES ('Themes',      't', 80);
INSERT INTO modules (name, active, ord) VALUES ('Languages',   't', 90);

INSERT INTO _mapping (identifier, mod_id, published, ord)
VALUES ('index', 1, 't', 1);

INSERT INTO _mapping (identifier, mod_id, published, ord)
VALUES ('css', 7, 't', NULL);

INSERT INTO content (mapping_id, lang, title, content)
VALUES (1, 'en', 'Welcome',
    'Your new Wiking site has been succesfully set up.\n\n' ||
    'Enter the [/_wmi Wiking Management Interface] to manage the content.');

INSERT INTO config (site_title) VALUES ('Wiking site');

INSERT INTO stylesheets (identifier) VALUES ('default.css');
INSERT INTO stylesheets (identifier) VALUES ('panels.css');

