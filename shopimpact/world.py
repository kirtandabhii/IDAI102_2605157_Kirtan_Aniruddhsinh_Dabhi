"""Every country, its currency, and approximate exchange rates.

Choosing a country in Settings sets the currency; brands are the same
everywhere. Rates here are built-in, rounded estimates (units per 1 US
dollar, late 2025). When the server is online, rates.py refreshes them daily.
"""

# ISO country code | country name | ISO currency code
_COUNTRIES = """
AF|Afghanistan|AFN
AX|Åland Islands|EUR
AL|Albania|ALL
DZ|Algeria|DZD
AS|American Samoa|USD
AD|Andorra|EUR
AO|Angola|AOA
AI|Anguilla|XCD
AG|Antigua and Barbuda|XCD
AR|Argentina|ARS
AM|Armenia|AMD
AW|Aruba|AWG
AU|Australia|AUD
AT|Austria|EUR
AZ|Azerbaijan|AZN
BS|Bahamas|BSD
BH|Bahrain|BHD
BD|Bangladesh|BDT
BB|Barbados|BBD
BY|Belarus|BYN
BE|Belgium|EUR
BZ|Belize|BZD
BJ|Benin|XOF
BM|Bermuda|BMD
BT|Bhutan|BTN
BO|Bolivia|BOB
BA|Bosnia and Herzegovina|BAM
BW|Botswana|BWP
BR|Brazil|BRL
VG|British Virgin Islands|USD
BN|Brunei|BND
BG|Bulgaria|EUR
BF|Burkina Faso|XOF
BI|Burundi|BIF
CV|Cabo Verde|CVE
KH|Cambodia|KHR
CM|Cameroon|XAF
CA|Canada|CAD
KY|Cayman Islands|KYD
CF|Central African Republic|XAF
TD|Chad|XAF
CL|Chile|CLP
CN|China|CNY
CO|Colombia|COP
KM|Comoros|KMF
CG|Congo|XAF
CD|Congo (DRC)|CDF
CK|Cook Islands|NZD
CR|Costa Rica|CRC
CI|Côte d'Ivoire|XOF
HR|Croatia|EUR
CU|Cuba|CUP
CW|Curaçao|XCG
CY|Cyprus|EUR
CZ|Czechia|CZK
DK|Denmark|DKK
DJ|Djibouti|DJF
DM|Dominica|XCD
DO|Dominican Republic|DOP
EC|Ecuador|USD
EG|Egypt|EGP
SV|El Salvador|USD
GQ|Equatorial Guinea|XAF
ER|Eritrea|ERN
EE|Estonia|EUR
SZ|Eswatini|SZL
ET|Ethiopia|ETB
FK|Falkland Islands|FKP
FO|Faroe Islands|DKK
FJ|Fiji|FJD
FI|Finland|EUR
FR|France|EUR
GF|French Guiana|EUR
PF|French Polynesia|XPF
GA|Gabon|XAF
GM|Gambia|GMD
GE|Georgia|GEL
DE|Germany|EUR
GH|Ghana|GHS
GI|Gibraltar|GIP
GR|Greece|EUR
GL|Greenland|DKK
GD|Grenada|XCD
GP|Guadeloupe|EUR
GU|Guam|USD
GT|Guatemala|GTQ
GG|Guernsey|GBP
GN|Guinea|GNF
GW|Guinea-Bissau|XOF
GY|Guyana|GYD
HT|Haiti|HTG
HN|Honduras|HNL
HK|Hong Kong|HKD
HU|Hungary|HUF
IS|Iceland|ISK
IN|India|INR
ID|Indonesia|IDR
IR|Iran|IRR
IQ|Iraq|IQD
IE|Ireland|EUR
IM|Isle of Man|GBP
IL|Israel|ILS
IT|Italy|EUR
JM|Jamaica|JMD
JP|Japan|JPY
JE|Jersey|GBP
JO|Jordan|JOD
KZ|Kazakhstan|KZT
KE|Kenya|KES
KI|Kiribati|AUD
XK|Kosovo|EUR
KW|Kuwait|KWD
KG|Kyrgyzstan|KGS
LA|Laos|LAK
LV|Latvia|EUR
LB|Lebanon|LBP
LS|Lesotho|LSL
LR|Liberia|LRD
LY|Libya|LYD
LI|Liechtenstein|CHF
LT|Lithuania|EUR
LU|Luxembourg|EUR
MO|Macao|MOP
MG|Madagascar|MGA
MW|Malawi|MWK
MY|Malaysia|MYR
MV|Maldives|MVR
ML|Mali|XOF
MT|Malta|EUR
MH|Marshall Islands|USD
MQ|Martinique|EUR
MR|Mauritania|MRU
MU|Mauritius|MUR
YT|Mayotte|EUR
MX|Mexico|MXN
FM|Micronesia|USD
MD|Moldova|MDL
MC|Monaco|EUR
MN|Mongolia|MNT
ME|Montenegro|EUR
MS|Montserrat|XCD
MA|Morocco|MAD
MZ|Mozambique|MZN
MM|Myanmar|MMK
NA|Namibia|NAD
NR|Nauru|AUD
NP|Nepal|NPR
NL|Netherlands|EUR
NC|New Caledonia|XPF
NZ|New Zealand|NZD
NI|Nicaragua|NIO
NE|Niger|XOF
NG|Nigeria|NGN
KP|North Korea|KPW
MK|North Macedonia|MKD
MP|Northern Mariana Islands|USD
NO|Norway|NOK
OM|Oman|OMR
PK|Pakistan|PKR
PW|Palau|USD
PS|Palestine|ILS
PA|Panama|PAB
PG|Papua New Guinea|PGK
PY|Paraguay|PYG
PE|Peru|PEN
PH|Philippines|PHP
PL|Poland|PLN
PT|Portugal|EUR
PR|Puerto Rico|USD
QA|Qatar|QAR
RE|Réunion|EUR
RO|Romania|RON
RU|Russia|RUB
RW|Rwanda|RWF
BL|Saint Barthélemy|EUR
SH|Saint Helena|SHP
KN|Saint Kitts and Nevis|XCD
LC|Saint Lucia|XCD
MF|Saint Martin|EUR
PM|Saint Pierre and Miquelon|EUR
VC|Saint Vincent and the Grenadines|XCD
WS|Samoa|WST
SM|San Marino|EUR
ST|São Tomé and Príncipe|STN
SA|Saudi Arabia|SAR
SN|Senegal|XOF
RS|Serbia|RSD
SC|Seychelles|SCR
SL|Sierra Leone|SLE
SG|Singapore|SGD
SX|Sint Maarten|XCG
SK|Slovakia|EUR
SI|Slovenia|EUR
SB|Solomon Islands|SBD
SO|Somalia|SOS
ZA|South Africa|ZAR
KR|South Korea|KRW
SS|South Sudan|SSP
ES|Spain|EUR
LK|Sri Lanka|LKR
SD|Sudan|SDG
SR|Suriname|SRD
SE|Sweden|SEK
CH|Switzerland|CHF
SY|Syria|SYP
TW|Taiwan|TWD
TJ|Tajikistan|TJS
TZ|Tanzania|TZS
TH|Thailand|THB
TL|Timor-Leste|USD
TG|Togo|XOF
TO|Tonga|TOP
TT|Trinidad and Tobago|TTD
TN|Tunisia|TND
TR|Türkiye|TRY
TM|Turkmenistan|TMT
TC|Turks and Caicos Islands|USD
TV|Tuvalu|AUD
UG|Uganda|UGX
UA|Ukraine|UAH
AE|United Arab Emirates|AED
GB|United Kingdom|GBP
US|United States|USD
VI|U.S. Virgin Islands|USD
UY|Uruguay|UYU
UZ|Uzbekistan|UZS
VU|Vanuatu|VUV
VA|Vatican City|EUR
VE|Venezuela|VES
VN|Vietnam|VND
WF|Wallis and Futuna|XPF
EH|Western Sahara|MAD
YE|Yemen|YER
ZM|Zambia|ZMW
ZW|Zimbabwe|ZWG
"""

# Approximate units of each currency per 1 US dollar (late 2025).
PER_USD = {
    "AED": 3.6725, "AFN": 69, "ALL": 84, "AMD": 384, "AOA": 915, "ARS": 1450, "AUD": 1.53,
    "AWG": 1.79, "AZN": 1.70, "BAM": 1.68, "BBD": 2.0, "BDT": 122, "BHD": 0.376, "BIF": 2960,
    "BMD": 1.0, "BND": 1.30, "BOB": 6.91, "BRL": 5.35, "BSD": 1.0, "BTN": 88.5, "BWP": 13.6,
    "BYN": 3.0, "BZD": 2.0, "CAD": 1.40, "CDF": 2400, "CHF": 0.80, "CLP": 940, "CNY": 7.12,
    "COP": 3850, "CRC": 502, "CUP": 24.0, "CVE": 94.5, "CZK": 20.9, "DJF": 178, "DKK": 6.43,
    "DOP": 63.5, "DZD": 130, "EGP": 47.5, "ERN": 15.0, "ETB": 150, "EUR": 0.862, "FJD": 2.27,
    "FKP": 0.76, "GBP": 0.76, "GEL": 2.71, "GHS": 11.0, "GIP": 0.76, "GMD": 73, "GNF": 8680,
    "GTQ": 7.66, "GYD": 209, "HKD": 7.78, "HNL": 26.3, "HTG": 131, "HUF": 333, "IDR": 16600,
    "ILS": 3.27, "INR": 88.6, "IQD": 1310, "IRR": 42100, "ISK": 125, "JMD": 160, "JOD": 0.709,
    "JPY": 154, "KES": 129, "KGS": 87.4, "KHR": 4010, "KMF": 424, "KPW": 900, "KRW": 1450,
    "KWD": 0.307, "KYD": 0.833, "KZT": 520, "LAK": 21700, "LBP": 89500, "LKR": 304, "LRD": 183,
    "LSL": 17.3, "LYD": 5.45, "MAD": 9.25, "MDL": 17.0, "MGA": 4480, "MKD": 53.0, "MMK": 2100,
    "MNT": 3590, "MOP": 8.02, "MRU": 39.9, "MUR": 45.8, "MVR": 15.4, "MWK": 1735, "MXN": 18.4,
    "MYR": 4.18, "MZN": 63.9, "NAD": 17.3, "NGN": 1450, "NIO": 36.8, "NOK": 10.1, "NPR": 141.6,
    "NZD": 1.76, "OMR": 0.385, "PAB": 1.0, "PEN": 3.38, "PGK": 4.25, "PHP": 59.0, "PKR": 281,
    "PLN": 3.66, "PYG": 7100, "QAR": 3.64, "RON": 4.38, "RSD": 101, "RUB": 81, "RWF": 1450,
    "SAR": 3.75, "SBD": 8.2, "SCR": 14.3, "SDG": 600, "SEK": 9.45, "SGD": 1.30, "SHP": 0.76,
    "SLE": 23.0, "SOS": 571, "SRD": 39.0, "SSP": 4600, "STN": 21.1, "SYP": 13000, "SZL": 17.3,
    "THB": 32.6, "TJS": 9.3, "TMT": 3.5, "TND": 2.94, "TOP": 2.38, "TRY": 42.2, "TTD": 6.78,
    "TWD": 30.8, "TZS": 2450, "UAH": 41.8, "UGX": 3480, "USD": 1.0, "UYU": 39.8, "UZS": 12000,
    "VES": 220, "VND": 26350, "VUV": 120, "WST": 2.75, "XAF": 565, "XCD": 2.70, "XCG": 1.79,
    "XOF": 565, "XPF": 102.8, "YER": 239, "ZAR": 17.3, "ZMW": 23.0, "ZWG": 26.8,
}

# Symbols we prefer over the browser's defaults (others are worked out in the browser).
SYMBOLS = {
    "GBP": "£", "USD": "$", "EUR": "€", "INR": "₹", "JPY": "¥", "CNY": "¥", "KRW": "₩", "CHF": "CHF",
    "SGD": "S$", "AUD": "A$", "CAD": "C$", "NZD": "NZ$", "HKD": "HK$", "AED": "AED", "SAR": "SAR",
    "BRL": "R$", "ZAR": "R", "RUB": "₽", "TRY": "₺", "THB": "฿", "PHP": "₱", "VND": "₫",
    "NGN": "₦", "ILS": "₪", "UAH": "₴", "PLN": "zł", "MXN": "MX$", "IDR": "Rp", "MYR": "RM",
    "PKR": "Rs", "LKR": "Rs", "NPR": "Rs", "BDT": "৳", "KES": "KSh", "EGP": "E£", "TWD": "NT$",
}


def _parse():
    countries = []
    for line in _COUNTRIES.strip().splitlines():
        code, name, currency = line.split("|")
        countries.append({"code": code, "name": name, "currency": currency})
    return countries


COUNTRIES = _parse()
COUNTRY_BY_CODE = {c["code"]: c for c in COUNTRIES}

# Countries shown at the top of the picker (the four the app was researched for, plus a few big ones).
POPULAR = ["IN", "SG", "CH", "US", "GB", "AE", "AU", "CA", "DE", "FR", "JP"]
