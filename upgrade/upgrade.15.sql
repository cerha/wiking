alter table users drop constraint users_lang_fkey;
alter table users add constraint users_lang_fkey foreign key (lang) references languages(lang) on update cascade on delete set null;
alter table _pages drop constraint _pages_lang_fkey;
alter table _pages add constraint _pages_lang_fkey foreign key (lang) references languages(lang) on update cascade;
alter table _attachment_descr drop constraint _attachment_descr_lang_fkey;
alter table _attachment_descr add constraint _attachment_descr_lang_fkey foreign key (lang) references languages(lang) on update cascade on delete cascade;
alter table news drop constraint news_lang_fkey;
alter table news add constraint news_lang_fkey foreign key (lang) references languages(lang) on update cascade;
alter table planner drop constraint planner_lang_fkey;
alter table planner add constraint planner_lang_fkey foreign key (lang) references languages(lang) on update cascade;
alter table _panels drop constraint _panels_lang_fkey;
alter table _panels add constraint _panels_lang_fkey foreign key (lang) references languages(lang) on update cascade;
alter table _texts drop constraint _texts_lang_fkey;
alter table _texts add constraint _texts_lang_fkey foreign key (lang) references languages(lang) on update cascade on delete cascade;
alter table _emails drop constraint _emails_lang_fkey;
alter table _emails add constraint _emails_lang_fkey foreign key (lang) references languages(lang) on update cascade on delete cascade;
alter table config drop constraint config_default_language_fkey;
alter table config add constraint config_default_language_fkey foreign key (default_language) references languages(lang) on update cascade;
alter table _mapping drop constraint _mapping_owner_fkey;
alter table _mapping add constraint _mapping_owner_fkey foreign key (owner) references users on delete set null;
alter table _panels drop constraint _panels_mapping_id_fkey;
alter table _panels add constraint _panels_mapping_id_fkey foreign key (mapping_id) references _mapping on delete set null;

