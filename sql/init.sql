-- Wiking initial data --

INSERT INTO languages (lang) VALUES ('en');

INSERT INTO mapping (identifier, modname, published, private, ord) VALUES
 ('index', 'Pages', 't', 'f', 1);
INSERT INTO mapping (identifier, modname, published, private, ord) VALUES
 ('css', 'Stylesheets', 't','f', NULL);

UPDATE pages SET title='Welcome', _content=
    'Your new Wiking site has been succesfully set up.\n\n' ||
    'Enter the [/_wmi Wiking Management Interface] to manage the content.'
WHERE mapping_id=1 AND lang='en';
UPDATE pages SET content=_content;

INSERT INTO config (site_title) VALUES ('Wiking site');

INSERT INTO stylesheets (identifier) VALUES ('default.css');
INSERT INTO stylesheets (identifier) VALUES ('panels.css');

INSERT INTO users (login, password, firstname, surname, nickname, user_,
                   email, enabled, admin)
VALUES ('admin', 'wiking', 'Wiking', 'Admin', 'Admin', 'Admin', '-', 't', 't');
