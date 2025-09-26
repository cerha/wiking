declare
  schema_ text := tg_argv[0];
  name_ text := tg_argv[1];
begin
  perform f_update_cached_tables (schema_, name_, true);
  return null;
end;
