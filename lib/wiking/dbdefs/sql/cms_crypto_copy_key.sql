declare
  key_ text;
begin
  lock cms_crypto_keys in exclusive mode;
  begin
    select cms_crypto_extract_key(key, from_psw) into key_ from cms_crypto_keys where name=name_ and uid=from_uid;
  exception
    when OTHERS then
      key_ := null;
  end;
  if key_ is null then
    return False;
  end if;
  delete from cms_crypto_keys where name=name_ and uid=to_uid;
  insert into cms_crypto_keys (name, uid, key) values (name_, to_uid, cms_crypto_store_key(key_, to_psw));
  return True;
end;
