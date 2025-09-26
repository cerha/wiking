begin
  lock cms_crypto_keys in exclusive mode;
  if not force and (select count(*) from cms_crypto_keys where name=name_) <= 1 then
    return False;
  end if;
  delete from cms_crypto_unlocked_passwords
         where key_id in (select key_id from cms_crypto_keys where name=name_ and uid=uid_);
  delete from cms_crypto_keys where name=name_ and uid=uid_;
  return True;
end;
