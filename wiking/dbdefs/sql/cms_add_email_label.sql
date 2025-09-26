declare
  already_present int := count(*) from cms_email_labels where label = _label;
begin
  if already_present = 0 then
    insert into cms_email_labels (label) values (_label);
  end if;
end
