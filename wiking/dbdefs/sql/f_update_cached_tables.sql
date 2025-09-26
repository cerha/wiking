declare
  processed_ boolean;
  pg_class_oid oid;
  object_id oid;
  dep_schema text;
  dep_name text;
begin
  -- Already updated in this transaction?
  begin
    create temp table _updated_cached_tables (_schema name, _name name) on commit delete rows;
  exception
    when duplicate_table then
      null;
  end;
  if (select count(*) > 0 from _updated_cached_tables where _schema = schema_ and _name = name_) then
    return;
  end if;
  if top_ then
    -- Reduce the chance of dead lock
    lock cached_tables in exclusive mode;
    -- Mark all entries as unprocessed
    update cached_tables set _processed = false;
  end if;
  -- Increase the version number
  select _processed into processed_ from cached_tables
         where object_schema = schema_ and object_name = name_;
  if processed_ is null then
    -- New entry
    insert into cached_tables (object_schema, object_name, stamp, _processed)
           values (schema_, name_, now (), true);
  elsif processed_ then
    -- Already processed
    return;
  else
    -- Version increase
    update cached_tables set version = version + 1, stamp = now (), _processed = true
           where object_schema = schema_ and object_name = name_;
  end if;
  -- Mark as already updated in this transaction
  insert into _updated_cached_tables (_schema, _name) values (schema_, name_);
  -- Increase versions of dependent objects
  select pg_class.oid into strict pg_class_oid
         from pg_class join pg_namespace on relnamespace = pg_namespace.oid
         where nspname = 'pg_catalog' and relname = 'pg_class';
  select pg_class.oid into strict object_id
         from pg_class join pg_namespace on relnamespace = pg_namespace.oid
         where nspname = schema_ and relname = name_;
  for dep_schema, dep_name in
      select nspname, relname from pg_depend join
                                   pg_class on objid = pg_class.oid join
                                   pg_namespace on relnamespace = pg_namespace.oid
                              where refobjid = object_id and classid = pg_class_oid and
                                    nspname != 'pg_catalog' and nspname != 'pg_toast'
      union
      select distinct nspname, relname from pg_depend join
                                            pg_rewrite on objid = pg_rewrite.oid join
                                            pg_class on pg_class.oid = ev_class join
                                            pg_namespace on relnamespace = pg_namespace.oid
                                       where refobjid = object_id and
                                             nspname != 'pg_catalog' and nspname != 'pg_toast' and
                                             ev_type = '1'
  loop
    perform f_update_cached_tables (dep_schema, dep_name, false);
  end loop;
end;
