-- Wiking initial data --

INSERT INTO languages (lang) VALUES ('en');

INSERT INTO modules (name, active, ord) VALUES ('Pages',       't', 10);
INSERT INTO modules (name, active, ord) VALUES ('Attachments', 't', 20);
INSERT INTO modules (name, active, ord) VALUES ('News',        't', 30);
INSERT INTO modules (name, active, ord) VALUES ('Planner',     't', 40);
INSERT INTO modules (name, active, ord) VALUES ('Panels',      't', 50);
INSERT INTO modules (name, active, ord) VALUES ('Users',       't', 60);
INSERT INTO modules (name, active, ord) VALUES ('Rights',      't', 70);
INSERT INTO modules (name, active, ord) VALUES ('Titles',      't', 80);
INSERT INTO modules (name, active, ord) VALUES ('Stylesheets', 't', 90);
INSERT INTO modules (name, active, ord) VALUES ('Themes',      't', 100);
INSERT INTO modules (name, active, ord) VALUES ('Languages',   't', 110);

INSERT INTO _mapping (identifier, mod_id, published, ord)
VALUES ('index', 1, 't', 1);
INSERT INTO _mapping (identifier, mod_id, published, ord)
VALUES ('css', 7, 't', NULL);

UPDATE pages SET title='Welcome', _content=
    'Your new Wiking site has been succesfully set up.\n\n' ||
    'Enter the [/_wmi Wiking Management Interface] to manage the content.'
WHERE mapping_id=1 AND lang='en';
UPDATE pages SET content=_content;

INSERT INTO config (site_title) VALUES ('Wiking site');

INSERT INTO stylesheets (identifier) VALUES ('default.css');
INSERT INTO stylesheets (identifier) VALUES ('panels.css');

INSERT INTO users (login, password, firstname, surname, email, enabled, admin)
VALUES ('admin', 'wiking', 'Wiking', 'Admin', '-', 't', 't');
