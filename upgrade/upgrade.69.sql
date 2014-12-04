drop function role_sets_cycle_check_visit(text, text[]);
drop function role_sets_cycle_check();

CREATE OR REPLACE FUNCTION "public"."role_sets_cycle_check"() RETURNS BOOLEAN LANGUAGE sql AS $$
with recursive edges (a, b) as (
    select role_id, member_role_id from role_sets
  union
    select a, member_role_id from edges join role_sets on b = role_id
  )
select count(*) = 0 from edges where a = b;
$$;
