-- Wiking initial data --

INSERT INTO languages (lang) VALUES ('en');

INSERT INTO menu (lang, title, published, identifier, modname, private, ord) VALUES
 ('en', 'Welcome', 't', 'index', 'Pages', 'f', 1);

UPDATE pages SET _content='Your new Wiking site has been succesfully set up.\n\n' ||
		          'Enter the [/_wmi Wiking Management Interface] to manage the content.'
WHERE mapping_id=1 AND lang='en';
UPDATE pages SET content=_content;

--INSERT INTO themes ("name") VALUES ('Default');
INSERT INTO config (site_title) VALUES ('Wiking site');

INSERT INTO stylesheets (identifier) VALUES ('default.css');

INSERT INTO users (login, password, firstname, surname, nickname, user_,
                   email, enabled, admin)
VALUES ('admin', 'wiking', 'Wiking', 'Admin', 'Admin', 'Admin', '-', 't', 't');

INSERT INTO themes ("name", foreground, background, border, heading_fg, heading_bg, heading_line,
    frame_fg, frame_bg, frame_border, link, link_visited, link_hover, meta_fg, meta_bg, help,
    error_fg, error_bg, error_border, message_fg, message_bg, message_border,
    table_cell, table_cell2, button_fg, button, button_border, button_hover,
    button_inactive_fg, button_inactive, button_inactive_border,
    top_fg, top_bg, top_border, highlight_bg, inactive_folder)
VALUES ('Yellowstone', '#000', '#fff9ec', '#eda', '#420', '#fff0b0', '#eca', '#000', '#fff0d4',
        '#ffde90', '#a30', '#a30', '#f40', NULL, NULL, '#553', NULL, NULL, NULL, NULL, NULL, NULL,
        '#fff', '#fff8f0', NULL, '#fe8', '#db9', '#fd4', NULL, '#ccc', '#999', '#444', '#fff',
	'#db9', '#fb7', '#ed9');

INSERT INTO themes ("name", foreground, background, border, heading_fg, heading_bg, heading_line, 
    frame_fg, frame_bg, frame_border, link, link_visited, link_hover, meta_fg, meta_bg, help, 
    error_fg, error_bg, error_border, message_fg, message_bg, message_border, 
    table_cell, table_cell2, button_fg, button, button_border, button_hover,
    button_inactive_fg, button_inactive, button_inactive_border,
    top_fg, top_bg, top_border, highlight_bg, inactive_folder)
VALUES ('Olive', '#000', '#fff', '#bcb', '#0b4a44', '#d2e0d8', NULL, '#000', '#e8eee8', '#d0d7d0',
        '#042', NULL, '#d72', NULL, NULL, NULL, NULL, '#fc9', '#fa8', NULL, '#dfd', '#aea',
        '#f8fbfa', '#f1f3f2', NULL, NULL, '#8a9', '#dff8df', NULL, '#ccc', '#999', NULL, '#efebe7',
        '#8a9', '#fc8', '#d2e0d8');
