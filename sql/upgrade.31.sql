create or replace function pytis_crypto_unlock_current_user_passwords (password_ text) returns setof text as $$
select ''::text where false;
$$ language sql immutable;
