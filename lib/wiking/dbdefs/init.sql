-- Wiking initial data --

insert into cms_database_version values (70);

insert into cms_languages (lang) values ('en');
insert into cms_config (site) values ('*');

insert into cms_stylesheets (identifier, site, media, ord) values ('default.css', '*', 'all', 10);
insert into cms_stylesheets (identifier, site, media, ord) values ('layout.css', '*', 'screen', 20);
insert into cms_stylesheets (identifier, site, media, ord) values ('print.css', '*', 'print', 30);

insert into roles (role_id, system, auto) values ('anyone', 't', 't');
insert into roles (role_id, system, auto) values ('authenticated', 't', 't');
insert into roles (role_id, system, auto) values ('owner', 't', 't');
insert into roles (role_id, system, auto) values ('user', 't', 't');
insert into roles (role_id, system, auto) values ('registered', 't', 't');
insert into roles (role_id, system, auto) values ('cms-user-admin', 't', 'f');
insert into roles (role_id, system, auto) values ('cms-crypto-admin', 't', 'f');
insert into roles (role_id, system, auto) values ('cms-content-admin', 't', 'f');
insert into roles (role_id, system, auto) values ('cms-settings-admin', 't', 'f');
insert into roles (role_id, system, auto) values ('cms-mail-admin', 't', 'f');
insert into roles (role_id, system, auto) values ('cms-style-admin', 't', 'f');
insert into roles (role_id, system, auto) values ('cms-admin', 't', 'f');

insert into role_sets (role_id, member_role_id) values ('cms-admin', 'cms-user-admin');
insert into role_sets (role_id, member_role_id) values ('cms-admin', 'cms-crypto-admin');
insert into role_sets (role_id, member_role_id) values ('cms-admin', 'cms-content-admin');
insert into role_sets (role_id, member_role_id) values ('cms-admin', 'cms-settings-admin');
insert into role_sets (role_id, member_role_id) values ('cms-admin', 'cms-mail-admin');
insert into role_sets (role_id, member_role_id) values ('cms-admin', 'cms-style-admin');

insert into users (login, password, firstname, surname, nickname, user_, email, state, last_password_change)
values ('admin', 'wiking', 'Wiking', 'Admin', 'Admin', 'Admin', '-', 'enabled', '2012-01-01 00:00');

insert into role_members (role_id, uid) values ('cms-admin', (select uid from users where login='admin'));

insert into cms_themes ("name", foreground, background, border, heading_fg, heading_bg, heading_line,
    frame_fg, frame_bg, frame_border, link, link_visited, link_hover, meta_fg, meta_bg, help,
    error_fg, error_bg, error_border, message_fg, message_bg, message_border,
    table_cell, table_cell2, top_fg, top_bg, top_border, highlight_bg, inactive_folder)
values ('Yellowstone', '#000', '#fff9ec', '#eda', '#420', '#fff0b0', '#eca', '#000', '#fff0d4',
        '#ffde90', '#a30', '#a30', '#f40', null, null, '#553', null, null, null, null, null, null,
        '#fff', '#fff8f0', '#444', '#fff', '#db9', '#fb7', '#ed9');

insert into cms_themes ("name", foreground, background, border, heading_fg, heading_bg, heading_line, 
    frame_fg, frame_bg, frame_border, link, link_visited, link_hover, meta_fg, meta_bg, help, 
    error_fg, error_bg, error_border, message_fg, message_bg, message_border, 
    table_cell, table_cell2, top_fg, top_bg, top_border, highlight_bg, inactive_folder)
values ('Olive', '#000', '#fff', '#bcb', '#0b4a44', '#d2e0d8', null, '#000', '#e8eee8', '#d0d7d0',
        '#042', null, '#d72', null, null, null, null, '#fc9', '#fa8', null, '#dfd', '#aea',
        '#f8fbfa', '#f1f3f2', null, '#efebe7', '#8a9', '#fc8', '#d2e0d8');

COPY cms_countries (country) FROM stdin;
AD
AE
AF
AG
AI
AL
AM
AO
AQ
AR
AS
AT
AU
AW
AX
AZ
BA
BB
BD
BE
BF
BG
BH
BI
BJ
BL
BM
BN
BO
BQ
BR
BS
BT
BV
BW
BY
BZ
CA
CC
CD
CF
CG
CH
CI
CK
CL
CM
CN
CO
CR
CU
CV
CW
CX
CY
CZ
DE
DJ
DK
DM
DO
DZ
EC
EE
EG
EH
ER
ES
ET
FI
FJ
FK
FM
FO
FR
GA
GB
GD
GE
GF
GG
GH
GI
GL
GM
GN
GP
GQ
GR
GS
GT
GU
GW
GY
HK
HM
HN
HR
HT
HU
ID
IE
IL
IM
IN
IO
IQ
IR
IS
IT
JE
JM
JO
JP
KE
KG
KH
KI
KM
KN
KP
KR
KW
KY
KZ
LA
LB
LC
LI
LK
LR
LS
LT
LU
LV
LY
MA
MC
MD
ME
MF
MG
MH
MK
ML
MM
MN
MO
MP
MQ
MR
MS
MT
MU
MV
MW
MX
MY
MZ
NA
NC
NE
NF
NG
NI
NL
NO
NP
NR
NU
NZ
OM
PA
PE
PF
PG
PH
PK
PL
PM
PN
PR
PS
PT
PW
PY
QA
RE
RO
RS
RU
RW
SA
SB
SC
SD
SE
SG
SH
SI
SJ
SK
SL
SM
SN
SO
SR
SS
ST
SV
SX
SY
SZ
TC
TD
TF
TG
TH
TJ
TK
TL
TM
TN
TO
TR
TT
TV
TW
TZ
UA
UG
UM
US
UY
UZ
VA
VC
VE
VG
VI
VN
VU
WF
WS
YE
YT
ZA
ZM
ZW
\.
