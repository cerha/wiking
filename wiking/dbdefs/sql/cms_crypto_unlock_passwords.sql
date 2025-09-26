insert into cms_crypto_unlocked_passwords
       (select key_id, cms_crypto_store_key(cms_crypto_extract_key(key, $2), $3)
               from cms_crypto_keys
               where uid=$1 and cms_crypto_extract_key(key, $2) is not null);
