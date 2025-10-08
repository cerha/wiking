SET SEARCH_PATH TO "public";


CREATE TABLE public.cached_tables (
	object_schema TEXT, 
	object_name TEXT, 
	version INTEGER DEFAULT 1, 
	stamp TIMESTAMP(0) WITHOUT TIME ZONE, 
	_processed BOOLEAN DEFAULT False NOT NULL
)

;

COMMENT ON TABLE "public"."cached_tables" IS 'Information about data versions of cached tables.
    Cached tables are tables or views with data cached in Wiking application
    accross HTTP requests.
    ';

COMMENT ON COLUMN "public"."cached_tables"."_processed" IS 'Flag for processing in FUpdateCachedTables';

GRANT all ON TABLE "public".cached_tables TO "www-data";

ALTER TABLE "public"."cached_tables" SET WITHOUT OIDS;

SET SEARCH_PATH TO "public";

CREATE OR REPLACE FUNCTION "public"."f_update_cached_tables"("schema_" TEXT, "name_" TEXT, "top_" BOOLEAN) RETURNS void LANGUAGE plpgsql AS $$
declare
  processed_ boolean;
  pg_class_oid oid;
  object_id oid;
  dep_schema text;
  dep_name text;
begin
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
$$;

COMMENT ON FUNCTION "public"."f_update_cached_tables"("schema_" TEXT, "name_" TEXT, "top_" BOOLEAN) IS 'Trigger function to increase data versions of cached tables.
    It increments version of both the given SCHEMA_.NAME_ table and
    of all the dependent tables.
    ';

SET SEARCH_PATH TO "public";

SET SEARCH_PATH TO "public";

CREATE OR REPLACE FUNCTION "public"."f_update_cached_tables_after"() RETURNS trigger LANGUAGE plpgsql AS $$
declare
  schema_ text := tg_argv[0];
  name_ text := tg_argv[1];
begin
  perform f_update_cached_tables (schema_, name_, true);
  return null;
end;
$$;

CREATE TRIGGER "public__cms_languages__cached_tables_update_trigger__after" after insert OR update OR delete OR truncate ON "cms_languages"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'cms_languages', True);


CREATE TRIGGER "public__cms_config__cached_tables_update_trigger__after" after insert OR update OR delete OR truncate ON "cms_config"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'cms_config', True);


CREATE TRIGGER "public__role_sets__cached_tables_update_trigger__after" after insert OR update OR delete OR truncate ON "role_sets"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'role_sets', True);


CREATE TRIGGER "public__users__cached_tables_update_trigger__after" after insert OR update OR delete OR truncate ON "users"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'users', True);


CREATE TRIGGER "public__cms_pages__cached_tables_update_trigger__after" after insert OR update OR delete OR truncate ON "cms_pages"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'cms_pages', True);

CREATE TRIGGER "public__cms_page_texts__cached_tables_update_trigger__after" after insert OR update OR delete OR truncate ON "cms_page_texts"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'cms_page_texts', True);


CREATE TRIGGER "public__cms_news__cached_tables_update_trigger__after" after insert OR update OR delete OR truncate ON "cms_news"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'cms_news', True);


CREATE TRIGGER "public__cms_planner__cached_tables_update_trigger__after" after insert OR update OR delete OR truncate ON "cms_planner"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'cms_planner', True);


CREATE TRIGGER "public__cms_panels__cached_tables_update_trigger__after" after insert OR update OR delete OR truncate ON "cms_panels"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'cms_panels', True);


CREATE TRIGGER "public__cms_stylesheets__cached_tables_update_trigger__after" after insert OR update OR delete OR truncate ON "cms_stylesheets"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'cms_stylesheets', True);


CREATE TRIGGER "public__cms_themes__cached_tables_update_trigger__after" after insert OR update OR delete OR truncate ON "cms_themes"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'cms_themes', True);

CREATE TRIGGER "public__cms_system_text_labels__cached_tables_update_trigger__after" after insert OR update OR delete OR truncate ON "cms_system_text_labels"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'cms_system_text_labels', True);

CREATE TRIGGER "public__cms_system_texts__cached_tables_update_trigger__after" after insert OR update OR delete OR truncate ON "cms_system_texts"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'cms_system_texts', True);

CREATE TRIGGER "public__role_members__cached_tables_update_trigger__after" after insert OR update OR delete OR truncate ON "role_members"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'role_members', True);

CREATE TRIGGER "public__roles__cached_tables_update_trigger__after" after insert OR update OR delete OR truncate ON "roles"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'roles', True);

CREATE TRIGGER "public__a_user_roles__cached_tables_update_trigger__after" after insert OR update OR delete OR truncate ON "a_user_roles"
FOR EACH STATEMENT EXECUTE PROCEDURE "public"."f_update_cached_tables_after"('public', 'a_user_roles', True);


update cms_stylesheets set identifier=identifier;
update cms_themes set name=name;
update cms_config set site_title=site_title;
