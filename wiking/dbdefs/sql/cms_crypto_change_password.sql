declare
  key_ text;
begin
  lock cms_crypto_keys in exclusive mode;
  begin
    select cms_crypto_extract_key(key, $2) into key_ from cms_crypto_keys where key_id=$1;
  exception
    when OTHERS then
      key_ := null;
  end;
  if key_ is null then
    return False;
  end if;
  update cms_crypto_keys set key=cms_crypto_store_key(key_, $3) where key_id=$1;
  return True;
end;
