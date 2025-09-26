with recursive edges (a, b) as (
    select role_id, member_role_id from role_sets
  union
    select a, member_role_id from edges join role_sets on b = role_id
  )
select count(*) = 0 from edges where a = b;
