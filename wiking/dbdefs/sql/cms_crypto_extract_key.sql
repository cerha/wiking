declare
  key text;
begin
  begin
    key := pgp_sym_decrypt(encrypted, psw);
  exception
    when OTHERS then
      return null;
  end;
  if substring(key for 7) != 'wiking:' then
    return null;
  end if;
  return substring(key from 8);
end;
