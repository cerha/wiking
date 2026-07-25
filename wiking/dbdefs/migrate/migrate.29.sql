create or replace function insert_or_update_user (uid_ int, login_ varchar(32), password_ varchar(32), firstname_ text, surname_ text, nickname_ text, user__ text, email_ text, phone_ text, address_ text, uri_ text, state_ text, last_password_change_ timestamp, since_ timestamp, lang_ char(2), regexpire_ timestamp, regcode_ char(16), certauth_ boolean, note_ text, confirm_ boolean, gender_ char(1)) returns void as $$
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
$$ language plpgsql;
