begin
  delete from cms_crypto_unlocked_passwords where key_id=new.key_id;
  return new;
end;
