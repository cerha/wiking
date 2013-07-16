select * from roles where roles.role_id not in (select expanded_role($1)) and
                          $1 not in (select expanded_role(roles.role_id));
