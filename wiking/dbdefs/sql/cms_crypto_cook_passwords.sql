begin
  lock cms_crypto_keys in exclusive mode;
  delete from cms_crypto_unlocked_passwords
         where key_id in (select key_id from cms_crypto_keys where uid=uid_) and
               cms_crypto_extract_key(password, cookie) is null;
  begin
    delete from t_pytis_passwords;
  exception
    when undefined_table then
      create temp table t_pytis_passwords (name text, password text);
  end;
  insert into t_pytis_passwords
         (select name, cms_crypto_extract_key(cms_crypto_unlocked_passwords.password, cookie)
                 from cms_crypto_keys join cms_crypto_unlocked_passwords using (key_id) where uid=uid_);
  return query select name from t_pytis_passwords;
end;
