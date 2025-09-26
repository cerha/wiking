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
