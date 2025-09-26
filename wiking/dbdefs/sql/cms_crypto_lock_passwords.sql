delete from cms_crypto_unlocked_passwords
       where key_id in (select key_id from cms_crypto_keys where uid=$1);
