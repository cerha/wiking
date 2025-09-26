declare
  already_present int := count(*) from cms_system_text_labels
                         where label = _label and site = _site;
begin
  if already_present = 0 then
    update cms_config set site=_site where site='*';
    insert into cms_config (site, site_title) select _site, _site
           where _site not in (select site from cms_config);
    insert into cms_system_text_labels (label, site) values (_label, _site);
  end if;
end
