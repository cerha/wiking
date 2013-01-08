create table cms_page_history (
       history_id serial primary key,
       page_id int not null,
       lang char(2) not null,
       uid int not null references users,
       timestamp timestamp(0) not null,
       content text,
       comment text,
       inserted_lines int not null,
       changed_lines int not null,
       deleted_lines int not null,
       foreign key (page_id, lang) references cms_page_texts (page_id, lang) on delete cascade
);

create or replace view cms_v_page_history as
  select h.*, u.user_ as user, page_id||'.'||h.lang as page_key,
         inserted_lines ||' / '|| changed_lines ||' / '|| deleted_lines as changes
  from cms_page_history h join users u using (uid);

create or replace rule cms_v_page_history_insert as
  on insert to cms_v_page_history do instead (
     insert into cms_page_history (page_id, lang, uid, timestamp, comment, content,
                                   inserted_lines, changed_lines, deleted_lines)
     values (new.page_id, new.lang, new.uid, new.timestamp, new.comment, new.content,
             new.inserted_lines, new.changed_lines, new.deleted_lines);
);

insert into cms_page_history (page_id, lang, uid, timestamp, comment, content,
                              changed_lines, inserted_lines, deleted_lines)
select page_id, lang, (select uid from role_members where role_id='admin' order by uid limit 1),
       current_timestamp(0) at time zone 'GMT',
       case when lang='cs' then 'Počáteční verze' else 'Initial version' end,
       _content, 0,
       coalesce(array_upper(string_to_array(content, E'\n'), 1), 0), 0 from cms_page_texts;
