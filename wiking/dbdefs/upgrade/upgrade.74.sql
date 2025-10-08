alter table cms_stylesheets rename column identifier to filename;
alter table cms_stylesheets drop column media;
delete from cms_stylesheets where filename in ('layout.css', 'print.css');
