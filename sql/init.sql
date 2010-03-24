-- Wiking initial data --

INSERT INTO languages (lang) VALUES ('en');

INSERT INTO pages (lang, title, published, identifier, private, hidden, _content) VALUES
 ('en', 'Welcome', 't', 'index', 'f', 'f',
  'Your new Wiking site has been succesfully set up.' || E'\n\n' ||
  'Enter the [/_wmi Wiking Management Interface] to manage the content.');
UPDATE pages SET content=_content;

--INSERT INTO themes ("name") VALUES ('Default');
INSERT INTO config (site_title) VALUES ('Wiking site');

insert into stylesheets (identifier, media, ord) values ('default.css', 'all', 10);
insert into stylesheets (identifier, media, ord) values ('layout.css', 'screen', 20);
insert into stylesheets (identifier, media, ord) values ('print.css', 'print', 30);

insert into roles (role_id, system) values ('user_admin', 't');
insert into roles (role_id, system) values ('content_admin', 't');
insert into roles (role_id, system) values ('settings_admin', 't');
insert into roles (role_id, system) values ('mail_admin', 't');
insert into roles (role_id, system) values ('style_admin', 't');
insert into roles (role_id, system) values ('admin', 't');

insert into role_sets (role_id, member_role_id) values ('admin', 'user_admin');
insert into role_sets (role_id, member_role_id) values ('admin', 'content_admin');
insert into role_sets (role_id, member_role_id) values ('admin', 'settings_admin');
insert into role_sets (role_id, member_role_id) values ('admin', 'mail_admin');
insert into role_sets (role_id, member_role_id) values ('admin', 'style_admin');

INSERT INTO users (login, password, firstname, surname, nickname, user_, email, state, last_password_change)
VALUES ('admin', 'wiking', 'Wiking', 'Admin', 'Admin', 'Admin', '-', 'enabled', '2000-01-01 00:00:00');

insert into role_members (role_id, uid) values ('admin', 1);

INSERT INTO themes ("name", foreground, background, border, heading_fg, heading_bg, heading_line,
    frame_fg, frame_bg, frame_border, link, link_visited, link_hover, meta_fg, meta_bg, help,
    error_fg, error_bg, error_border, message_fg, message_bg, message_border,
    table_cell, table_cell2, top_fg, top_bg, top_border, highlight_bg, inactive_folder)
VALUES ('Yellowstone', '#000', '#fff9ec', '#eda', '#420', '#fff0b0', '#eca', '#000', '#fff0d4',
        '#ffde90', '#a30', '#a30', '#f40', NULL, NULL, '#553', NULL, NULL, NULL, NULL, NULL, NULL,
        '#fff', '#fff8f0', '#444', '#fff', '#db9', '#fb7', '#ed9');

INSERT INTO themes ("name", foreground, background, border, heading_fg, heading_bg, heading_line, 
    frame_fg, frame_bg, frame_border, link, link_visited, link_hover, meta_fg, meta_bg, help, 
    error_fg, error_bg, error_border, message_fg, message_bg, message_border, 
    table_cell, table_cell2, top_fg, top_bg, top_border, highlight_bg, inactive_folder)
VALUES ('Olive', '#000', '#fff', '#bcb', '#0b4a44', '#d2e0d8', NULL, '#000', '#e8eee8', '#d0d7d0',
        '#042', NULL, '#d72', NULL, NULL, NULL, NULL, '#fc9', '#fa8', NULL, '#dfd', '#aea',
        '#f8fbfa', '#f1f3f2', NULL, '#efebe7', '#8a9', '#fc8', '#d2e0d8');
