select role_id from a_user_roles where ($1 is null and uid is null) or ($1 is not null and uid=$1);
