alter table users alter column password type text;
update users set password = case when (select count(*) from users
       	     	 	    	       where length(password) != 32) = 0
                            then 'md5u' else 'plain' end || ':' || coalesce(password, '');
alter table users alter column password set not null;
alter table public.users alter column last_password_change type timestamp(0) with time zone;
alter table public.users alter column since type timestamp(0) with time zone;
alter table public.users alter column since set default timezone('GMT', current_timestamp(0));
alter table public.users alter column regexpire type timestamp(0) with time zone;
alter table public.users alter column regcode type text;
alter table public.users add column passexpire timestamp(0) with time zone;
alter table public.users add column passcode text;

drop function "public"."cms_f_insert_or_update_user" ("uid_" INTEGER, "login_" VARCHAR(64), "password_" VARCHAR(64), "firstname_" TEXT, "surname_" TEXT, "nickname_" TEXT, "user__" TEXT, "email_" TEXT, "phone_" TEXT, "address_" TEXT, "uri_" TEXT, "state_" TEXT, "last_password_change_" TIMESTAMP(0) WITHOUT TIME ZONE, "since_" TIMESTAMP(0) WITHOUT TIME ZONE, "lang_" CHAR(2), "regexpire_" TIMESTAMP(0) WITHOUT TIME ZONE, "regcode_" CHAR(16), "certauth_" BOOLEAN, "note_" TEXT, "confirm_" BOOLEAN, "gender_" CHAR(1));

CREATE OR REPLACE FUNCTION "public"."cms_f_insert_or_update_user"("uid_" INTEGER, "login_" VARCHAR(64), "password_" TEXT, "firstname_" TEXT, "surname_" TEXT, "nickname_" TEXT, "user__" TEXT, "email_" TEXT, "phone_" TEXT, "address_" TEXT, "uri_" TEXT, "state_" TEXT, "last_password_change_" TIMESTAMP(0) WITH TIME ZONE, "since_" TIMESTAMP(0) WITH TIME ZONE, "lang_" CHAR(2), "regexpire_" TIMESTAMP(0) WITH TIME ZONE, "regcode_" TEXT, "passexpire_" TIMESTAMP(0) WITH TIME ZONE, "passcode_" TEXT, "certauth_" BOOLEAN, "note_" TEXT, "confirm_" BOOLEAN, "gender_" CHAR(1)) RETURNS void LANGUAGE plpgsql AS $$
declare
  row record;
begin
  if (select count(*) from users where login=login_)>0 then
    select into strict row * from users where login=login_;
    if row.login != login_ or row.password != password_ then
      raise exception 'duplicate key value violates unique constraint "users_login_key"';
    end if;
    update users set firstname=coalesce(firstname_,firstname), surname=coalesce(surname_,surname), nickname=coalesce(nickname_,nickname), email=coalesce(email_,email), phone=coalesce(phone_,phone), address=coalesce(address_,address), uri=coalesce(uri_,uri), regcode=null, certauth=coalesce(certauth_,certauth), note=coalesce(note_,note), gender=coalesce(gender_,gender) where login=login_;
  else
    insert into users (uid, login, password, firstname, surname, nickname, user_, email, phone, address, uri, state, last_password_change, since, lang, regexpire, regcode, certauth, note, confirm, gender) values (uid_, login_, password_, firstname_, surname_, nickname_, user__, email_, phone_, address_, uri_, state_, last_password_change_, since_, lang_, regexpire_, regcode_, coalesce(certauth_, False), note_, confirm_, gender_);
  end if;
end;
$$;
