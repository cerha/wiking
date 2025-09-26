begin
  lock cms_crypto_keys in exclusive mode;
  if (select count(*) from cms_crypto_keys where name=name_ and uid=uid_) > 0 then
    return False;
  end if;
  insert into cms_crypto_keys (name, uid, key) values (name_, uid_, cms_crypto_store_key(key_, psw));
  return True;
end;
