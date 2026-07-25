ALTER TABLE public.cms_pages ALTER COLUMN write_role_id SET DEFAULT 'cms-content-admin';
ALTER TABLE public.cms_newsletters ALTER COLUMN write_role_id SET DEFAULT 'cms-content-admin';

drop trigger role_sets_update_user_roles_trigger on role_sets;
drop trigger role_members_update_user_roles_trigger on role_members;

update roles set role_id = 'cms-' || replace(role_id, '_', '-')
where role_id in ('admin', 'content_admin', 'style_admin', 'settings_admin',
                  'user_admin', 'mail_admin', 'crypto_admin');

create trigger role_sets_update_user_roles_trigger after insert or update or delete on role_sets
for each statement execute procedure update_user_roles ();
create trigger role_members_update_user_roles_trigger after insert or update or delete on role_members
for each statement execute procedure update_user_roles ();

