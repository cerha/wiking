-- Union is important for users, who have no explicit roles in a_user_roles. 
select role_id from a_user_roles where uid is null
union
select role_id from a_user_roles where uid=$1;
