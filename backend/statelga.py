
import re

# ==========================================================
# BASIC STATE DATABASE (used by backend + video tester)
# ==========================================================

STATES_LGA = {
    "ABUJA": {
        "codes": ["ABJ", "FCT", "ABUJA", "AA", "AB", "AC", "AD", "AE", "AF", "AG"],
        "lgas": ["ABAJI", "BWARI", "GWAGWALADA", "KUJE", "KWALI", "MUNICIPAL AREA COUNCIL"]
    },
    "ABIA": {
        "codes": ["ABI", "ABIA", "ABA"],
        "lgas": ["ABA NORTH", "ABA SOUTH", "AROCHUKWU", "BENDE", "IKWUANO",
                 "ISIALA NGWA NORTH", "ISIALA NGWA SOUTH", "ISUIKWUATO",
                 "OBINGWA", "OHAFIA", "OSISIOMA", "UGWUNAGBO", "UKWA EAST",
                 "UKWA WEST", "UMUAHIA NORTH", "UMUAHIA SOUTH", "UMU NNEOCHI"]
    },
    "ADAMAWA": {
        "codes": ["ADA", "ADAMAWA", "AD"],
        "lgas": ["DEMSA", "FUFURE", "GANYE", "GAYUK", "GOMBI", "GRIE", "HONG",
                 "JADA", "LAMURDE", "MADAGALI", "MAIHA", "MAYO BELWA", "MICHIKA",
                 "MUBI NORTH", "MUBI SOUTH", "NUMAN", "SHELLENG", "SONG",
                 "TOUNGO", "YOLA NORTH", "YOLA SOUTH"]
    },
    "AKWAIBOM": {
        "codes": ["AKW", "AKWAIBOM", "AK"],
        "lgas": ["ABAK", "EASTERN OBOLO", "EKET", "ESIT EKET", "ESSIEN UDIM",
                 "ETIM EKPO", "ETINAN", "IBENO", "IBESIKPO ASUTAN", "IBIONO-IBOM",
                 "IKA", "IKONO", "IKOT ABASI", "IKOT EKPENE", "INI", "ITU", "MBO",
                 "MKPAT-ENIN", "NSIT-ATAI", "NSIT-IBOM", "NSIT-UBIUM", "OBOT AKARA",
                 "OKOBO", "ONNA", "ORON", "ORUK ANAM", "UDUNG-UKO", "UKANAFUN",
                 "URUAN", "URUE-OFFONG/ORUKO", "UYO"]
    },
    "ANAMBRA": {
        "codes": ["ANM", "ANAMBRA", "AN"],
        "lgas": ["AGUATA", "ANAMBRA EAST", "ANAMBRA WEST", "ANAOCHA", "AWKA NORTH",
                 "AWKA SOUTH", "AYAMELUM", "DUNUKOFIA", "EKWUSIGO", "IDEMILI NORTH",
                 "IDEMILI SOUTH", "IHIALA", "NJIKOKA", "NNEWI NORTH", "NNEWI SOUTH",
                 "OGBARU", "ONITSHA NORTH", "ONITSHA SOUTH", "ORUMBA NORTH",
                 "ORUMBA SOUTH", "OYI"]
    },
    "BAUCHI": {
        "codes": ["BAU", "BAUCHI", "BC"],
        "lgas": ["ALKALERI", "BAUCHI", "BOGORO", "DAMBAN", "DARAZO", "DASS",
                 "GAMAWA", "GANJUWA", "GIADE", "ITAS/GADAU", "JAMA'ARE", "KATAGUM",
                 "KIRFI", "MISAU", "NINGI", "SHIRA", "TAFAWA BALEWA", "TORO",
                 "WARJI", "ZAKI"]
    },
    "BAYELSA": {
        "codes": ["BAY", "BAYELSA", "BY"],
        "lgas": ["BRASS", "EKEREMOR", "KOLOKUMA/OPOKUMA", "NEMBE", "OGBIA",
                 "SAGBAMA", "SOUTHERN IJAW", "YENAGOA"]
    },
    "BENUE": {
        "codes": ["BEN", "BENUE", "BN"],
        "lgas": ["ADO", "AGATU", "APA", "BURUKU", "GBOKO", "GUMA", "GWER EAST",
                 "GWER WEST", "KATSINA ALA", "KONSHISHA", "KWANDE", "LOGO",
                 "MAKURDI", "OBI", "OGBADIBO", "OHIMINI", "OJU", "OKPOKWU",
                 "OTUKPO", "TARKA", "UKUM", "USHONGO", "VANDEIKYA"]
    },
    "BORNO": {
        "codes": ["BOR", "BORNO", "BO"],
        "lgas": ["ABADAM", "ASKIRA/UBA", "BAMA", "BAYO", "BIU", "CHIBOK", "DAMBOA",
                 "DIKWA", "GUBIO", "GUZAMALA", "GWOZA", "HAWUL", "JERE", "KAGA",
                 "KALA/BALGE", "KONDUGA", "KUKAWA", "KWAYA KUSAR", "MAFA",
                 "MAGUMERI", "MAIDUGURI", "MARTE", "MOBBAR", "MONGUNO", "NGALA",
                 "NGANZAI", "SHANI"]
    },
    "CROSSRIVER": {
        "codes": ["CRS", "CROSSRIVER", "CR"],
        "lgas": ["ABI", "AKAMKPA", "AKPABUYO", "BAKASSI", "BEKWARRA", "BIASE",
                 "BOKI", "CALABAR MUNICIPAL", "CALABAR SOUTH", "ETUNG", "IKOM",
                 "OBANLIKU", "OBUBRA", "OBUDU", "ODUKPANI", "OGOJA", "YAKUUR", "YALA"]
    },
    "DELTA": {
        "codes": ["DEL", "DELTA", "DT"],
        "lgas": ["ANIOCHA NORTH", "ANIOCHA SOUTH", "BOMADI", "BURUTU", "ETHIOPE EAST",
                 "ETHIOPE WEST", "IKA NORTH EAST", "IKA SOUTH", "ISOKO NORTH",
                 "ISOKO SOUTH", "NDOKWA EAST", "NDOKWA WEST", "OKPE", "OSHIMILI NORTH",
                 "OSHIMILI SOUTH", "PATANI", "SAPELE", "UDU", "UGHELLI NORTH",
                 "UGHELLI SOUTH", "UKWUANI", "UVWIE", "WARRI NORTH", "WARRI SOUTH",
                 "WARRI SOUTH WEST"]
    },
    "EBONYI": {
        "codes": ["EBO", "EBONYI", "EB"],
        "lgas": ["ABAKALIKI", "AFIKPO NORTH", "AFIKPO SOUTH", "EBONYI", "EZZA NORTH",
                 "EZZA SOUTH", "IKWO", "ISHIELU", "IVO", "IZZI", "OHAOZARA",
                 "OHAUKWU", "ONICHA"]
    },
    "EDO": {
        "codes": ["EDO", "ED", "EDO"],
        "lgas": ["AKOKO-EDO", "EGOR", "ESAN CENTRAL", "ESAN NORTH-EAST", "ESAN SOUTH-EAST",
                 "ESAN WEST", "ETSAKO CENTRAL", "ETSAKO EAST", "ETSAKO WEST", "IGUEBEN",
                 "IKPOBA OKHA", "OREDO", "ORHIONMWON", "OVIA NORTH-EAST", "OVIA SOUTH-WEST",
                 "OWAN EAST", "OWAN WEST", "UHUNMWONDE"]
    },
    "EKITI": {
        "codes": ["EKT", "EKITI", "EK"],
        "lgas": ["ADO EKITI", "EFON", "EKITI EAST", "EKITI SOUTH WEST", "EKITI WEST",
                 "EMURE", "GBONYIN", "IDO OSI", "IJERO", "IKERE", "IKOLE", "ILEJEMEJE",
                 "IREPODUN/IFELODUN", "ISE/ORUN", "MOBA", "OYE"]
    },
    "ENUGU": {
        "codes": ["ENU", "ENUGU", "EN"],
        "lgas": ["ANINRI", "AWGU", "ENUGU EAST", "ENUGU NORTH", "ENUGU SOUTH", "EZEAGU",
                 "IGBO ETITI", "IGBO EZE NORTH", "IGBO EZE SOUTH", "ISI UZO", "NKANU EAST",
                 "NKANU WEST", "NSUKKA", "OJI RIVER", "UDENU", "UDI", "UZO UWANI"]
    },
    "GOMBE": {
        "codes": ["GOM", "GOMBE", "GM"],
        "lgas": ["AKKO", "BALANGA", "BILLIRI", "DUKKU", "FUNAKAYE", "GOMBE", "KALTUNGO",
                 "KWAMI", "NAFADA", "SHONGOM", "YAMALTU/DEBA"]
    },
    "IMO": {
        "codes": ["IMO", "IM"],
        "lgas": ["ABOH MBAISE", "AHIAZU MBAISE", "EHIME MBANO", "EZINIHITTE", "IDEATO NORTH",
                 "IDEATO SOUTH", "IHITTE/UBOMA", "IKEDURU", "ISIALA MBANO", "ISU", "MBAITOLI",
                 "NGOR OKPALA", "NJABA", "NKWERRE", "NWANGELE", "OBOWO", "OGUTA",
                 "OHAJI/EGBEMA", "OKIGWE", "ORLU", "ORSU", "ORU EAST", "ORU WEST",
                 "OWERRI MUNICIPAL", "OWERRI NORTH", "OWERRI WEST", "UNUIMO"]
    },
    "JIGAWA": {
        "codes": ["JIG", "JIGAWA", "JG"],
        "lgas": ["AUYO", "BABURA", "BIRINIWA", "BIRNIN KUDU", "BUJI", "DUTSE", "GAGARAWA",
                 "GARKI", "GUMEL", "GURI", "GWARAM", "GWIWA", "HADEJIA", "JAHUN",
                 "KAFIN HAUSA", "KAUGAMA", "KAZAURE", "KIRI KASAMA", "KIYAWA", "MAIGATARI",
                 "MALAM MADORI", "MIGA", "RINGIM", "RONI", "SULE TANKARKAR", "TAURA", "YANKWASHI"]
    },
    "KADUNA": {
        "codes": ["KAD", "KADUNA", "KD"],
        "lgas": ["BIRNIN GWARI", "CHIKUN", "GIWA", "IGABI", "IKARA", "JABA", "JEMA'A",
                 "KACHIA", "KADUNA NORTH", "KADUNA SOUTH", "KAGARKO", "KAJURU", "KAURA",
                 "KAURU", "KUBAU", "KUDAN", "LERE", "MAKARFI", "SABON GARI", "SANGA",
                 "SOBA", "ZANGON KATAF", "ZARIA"]
    },
    "KANO": {
        "codes": ["KAN", "KANO", "KN"],
        "lgas": ["AJINGI", "ALBASU", "BAGWAI", "BEBEJI", "BICHI", "BUNKURE", "DALA",
                 "DAMBATTA", "DAWAKIN KUDU", "DAWAKIN TOFA", "DOGUWA", "FAGGE", "GABASAWA",
                 "GARKO", "GARUN MALLAM", "GAYA", "GEZAWA", "GWALE", "GWARZO", "KABO",
                 "KANO MUNICIPAL", "KARAYE", "KIBIYA", "KIRU", "KUMBOTSO", "KUNCHI", "KURA",
                 "MADOBI", "MAKODA", "MINJIBIR", "NASARAWA", "RANO", "RIMIN GADO", "ROGO",
                 "SHANONO", "SUMAILA", "TAKAI", "TARAUNI", "TOFA", "TSANYAWA", "TUDUN WADA",
                 "UNGOGO", "WARAWA", "WUDIL"]
    },
    "KATSINA": {
        "codes": ["KAT", "KATSINA", "KT"],
        "lgas": ["BAKORI", "BATAGARAWA", "BATSARI", "BAURE", "BINDAWA", "CHARANCHI",
                 "DANDUME", "DANJA", "DAN MUSA", "DAURA", "DUTSI", "DUTSIN MA", "FASKARI",
                 "FUNTUA", "INGAWA", "JIBIA", "KAFUR", "KAITA", "KANKARA", "KANKIA",
                 "KATSINA", "KURFI", "KUSADA", "MAI ADUA", "MALUMFASHI", "MANI", "MASHI",
                 "MATAZU", "MUSAWA", "RIMI", "SABUWA", "SAFANA", "SANDAMU", "ZANGO"]
    },
    "KEBBI": {
        "codes": ["KEB", "KEBBI", "KB"],
        "lgas": ["ALEIRO", "AREWA DANDI", "ARGUNGU", "AUGIE", "BAGUDO", "BIRNIN KEBBI",
                 "BUNZA", "DANDI", "FAKAI", "GWANDU", "JEGA", "KALGO", "KOKO/BESSE",
                 "MAIYAMA", "NGASKI", "SAKABA", "SHANGA", "SURU", "WASAGU/DANKO", "YAURI", "ZURU"]
    },
    "KOGI": {
        "codes": ["KOG", "KOGI", "KG"],
        "lgas": ["ADAVI", "AJAOKUTA", "ANKPA", "BASSA", "DEKINA", "IBAJI", "IDAH",
                 "IGALAMELA ODOLU", "IJUMU", "KABBA/BUNU", "KOGI", "LOKOJA", "MOPA MURO",
                 "OFU", "OGORI/MAGONGO", "OKEHI", "OKENE", "OLAMABORO", "OMALA",
                 "YAGBA EAST", "YAGBA WEST"]
    },
    "KWARA": {
        "codes": ["KWR", "KWARA", "KW"],
        "lgas": ["ASA", "BARUTEN", "EDU", "EKITI", "IFELODUN", "ILORIN EAST", "ILORIN SOUTH",
                 "ILORIN WEST", "IREPODUN", "ISIN", "KAIAMA", "MORO", "OFFA", "OKE ERO",
                 "OYUN", "PATEGI"]
    },
    "LAGOS": {
        "codes": ["LAG", "LGS", "KJA", "AAA", "AKD", "AGL", "APP", "BDG", "EKY",
                  "FST", "GGE", "KRD", "KSF", "KTU", "LND", "LSD", "LSR", "MUS", "SMK", "OJO", "JJJ"],
        "lgas": ["AGEGE", "AJEROMI-IFELODUN", "ALIMOSHO", "AMUWO-ODOFIN", "APAPA", "BADAGRY",
                 "EPE", "ETI-OSA", "IBEJU-LEKKI", "IFAKO-IJAIYE", "IKEJA", "IKORODU", "KOSOFE",
                 "LAGOS ISLAND", "LAGOS MAINLAND", "MUSHIN", "OJO", "OSHODI-ISOLO", "SHOMOLU", "SURULERE",]
    },
    "NASARAWA": {
        "codes": ["NAS", "NASARAWA", "NW"],
        "lgas": ["AKWANGA", "AWE", "DOMA", "KARU", "KEANA", "KEFFI", "KOKONA", "LAFIA",
                 "NASARAWA", "NASARAWA EGON", "OBI", "TOTO", "WAMBA"]
    },
    "NIGER": {
        "codes": ["NIG", "NIGER", "NI"],
        "lgas": ["AGAIE", "AGWARA", "BIDA", "BORGU", "BOSSO", "CHANCHAGA", "EDATI", "GBAKO",
                 "GURARA", "KATCHA", "KONTAGORA", "LAPAI", "LAVUN", "MAGAMA", "MARIGA",
                 "MASHEGU", "MOKWA", "MOYA", "PAIKORO", "RAFI", "RIJAU", "SHIRORO", "SULEJA",
                 "TAFA", "WUSHISHI"]
    },
    "OGUN": {
        "codes": ["OGN", "OGUN", "OG"],
        "lgas": ["ABEOKUTA NORTH", "ABEOKUTA SOUTH", "ADO-ODO/OTA", "EWEKORO", "IFO",
                 "IJEBU EAST", "IJEBU NORTH", "IJEBU NORTH EAST", "IJEBU ODE", "IKENNE",
                 "IMEKO AFON", "IPOKIA", "OBAFEMI OWODE", "ODEDA", "ODOGBOLU",
                 "OGUN WATERSIDE", "REMO NORTH", "SAGAMU", "YEWA NORTH", "YEWA SOUTH"]
    },
    "ONDO": {
        "codes": ["OND","JTA", "ONDO", "ON"],
        "lgas": ["AKOKO NORTH-EAST", "AKOKO NORTH-WEST", "AKOKO SOUTH-EAST", "AKOKO SOUTH-WEST",
                 "AKURE NORTH", "AKURE SOUTH", "ESE ODO", "IDANRE", "IFEDORE", "ILAJE",
                 "ILE OLUJI/OKEIGBO", "IRELE", "ODIGBO", "OKITIPUPA", "OWO"]
    },
    "OSUN": {
        "codes": ["OSN", "OSUN", "OS", "RGB"],
        "lgas": ["ADE OGUN", "ATAKUMOSA EAST", "ATAKUMOSA WEST", "AYEDAADE", "AYEDIRE",
                 "BOLUWADURO", "BORIPE", "EDE NORTH", "EDE SOUTH", "EGBEDORE", "EJIGBO",
                 "IFE CENTRAL", "IFE EAST", "IFE NORTH", "IFE SOUTH", "IFEDAYO", "IFELODUN",
                 "ILA", "ILESA EAST", "ILESA WEST", "IREPODUN", "IREWOLE", "ISOKAN", "IWO",
                 "OBOKUN", "ODO OTIN", "OLA OLUWA", "OLORUNDA", "ORIADE", "OROLU", "OSOGBO"]
    },
    "OYO": {
        "codes": ["OYO", "OY"],
        "lgas": ["AFIJIO", "AKINYELE", "ATIBA", "ATISBO", "EGBEDA", "IBADAN NORTH",
                 "IBADAN NORTH-EAST", "IBADAN NORTH-WEST", "IBADAN SOUTH-EAST",
                 "IBADAN SOUTH-WEST", "IBARAPA CENTRAL", "IBARAPA EAST", "IBARAPA NORTH",
                 "IDO", "IREPO", "ISEYIN", "ITESIWAJU", "IWAJOWA", "KAJOLA", "LAGELU",
                 "OGBOMOSHO NORTH", "OGBOMOSHO SOUTH", "OGO OLUWA", "OLORUNSOGO", "OLUYOLE",
                 "ONA ARA", "ORELOPE", "ORI IRE", "OYO EAST", "OYO WEST", "SAKI EAST",
                 "SAKI WEST", "SURULERE"]
    },
    "PLATEAU": {
        "codes": ["PLT", "PLATEAU", "PL"],
        "lgas": ["BARKIN LADI", "BASSA", "BOKKOS", "JOS EAST", "JOS NORTH", "JOS SOUTH",
                 "KANAM", "KANKE", "LANGTANG NORTH", "LANGTANG SOUTH", "MANGU", "MIKANG",
                 "PANKSHIN", "QUA'AN PAN", "RIYOM", "SHENDAM", "WASE"]
    },
    "RIVERS": {
        "codes": ["RIV", "RIVERS", "RIVER", "RS"],
        "lgas": ["ABUA/ODUAL", "AHOADA EAST", "AHOADA WEST", "AKUKU-TORU", "ANDONI",
                 "ASARI-TORU", "BONNY", "DEGEMA", "ELEME", "EMUOHA", "ETCHE", "GOKANA",
                 "IKWERRE", "KHANA", "OBIO-AKPOR", "OGBA/EGBEMA/NDONI", "OGU/BOLO",
                 "OKRIKA", "OMUMA", "OPOBO/NKORO", "OYIGBO", "PORT HARCOURT", "TAI"]
    },
    "SOKOTO": {
        "codes": ["SOK", "SOKOTO", "SK"],
        "lgas": ["BINJI", "BODINGA", "DANGE SHUNI", "GADA", "GORONYO", "GUDU", "GWADABAWA",
                 "ILLELA", "ISA", "KEBBE", "KWARE", "RABAH", "SABON BIRNI", "SHAGARI",
                 "SILAME", "SOKOTO NORTH", "SOKOTO SOUTH", "TAMBUWAL", "TANGAZA", "TURETA",
                 "WAMAKO", "WURNO", "YABO"]
    },
    "TARABA": {
        "codes": ["TAR", "TARABA", "TB"],
        "lgas": ["ARDO KOLA", "BALI", "DONGA", "GASHAKA", "GASSOL", "IBI", "JALINGO",
                 "KAR DAGA", "KURMI", "LAU", "SARDAUNA", "TAKUM", "USSA", "WUKARI", "YORRO", "ZING"]
    },
    "YOBE": {
        "codes": ["YOB", "YOBE", "YB"],
        "lgas": ["BADE", "BURSARI", "DAMATURU", "FIKA", "FUNE", "GEIDAM", "GUJBA", "GULANI",
                 "JAKUSKO", "KARASUWA", "MACHINA", "NANGERE", "NGURU", "POTISKUM", "TARMUWA",
                 "YUNUSARI", "YUSUFARI"]
    },
    "ZAMFARA": {
        "codes": ["ZAM", "ZAMFARA", "ZF"],
        "lgas": ["ANKA", "BAKURA", "BIRNIN MAGAJI/KIYAW", "BUKKUYUM", "BUNGUDU", "GUMMI",
                 "GUSAU", "KAURA NAMODA", "MARADUN", "MARU", "SHINKAFI", "TALATA MAFARA",
                 "TSAFE", "ZURMI"]
    },
}

LGA_PREFIX_TO_STATE = {
    "ABA": "ABIA", "BND": "ABIA", "ACH": "ABIA", "HAF": "ABIA", "UMA": "ABIA", "KPU": "ABIA", "OBG": "ABIA", "ISK": "ABIA",
    "DSA": "ADAMAWA", "FUR": "ADAMAWA", "GAN": "ADAMAWA", "GRE": "ADAMAWA", "GMB": "ADAMAWA", "GUY": "ADAMAWA", "HNG": "ADAMAWA", "JMT": "ADAMAWA", "MUB": "ADAMAWA", "NUM": "ADAMAWA", "YLA": "ADAMAWA", "MYO": "ADAMAWA", "SHE": "ADAMAWA", "TRG": "ADAMAWA",
    "ABK": "AKWAIBOM", "KRT": "AKWAIBOM", "KET": "AKWAIBOM", "KST": "AKWAIBOM", "AFH": "AKWAIBOM", "AEE": "AKWAIBOM", "ETN": "AKWAIBOM", "UYO": "AKWAIBOM", "OKP": "AKWAIBOM", "IKN": "AKWAIBOM", "MKT": "AKWAIBOM", "NSD": "AKWAIBOM", "UDG": "AKWAIBOM", "URU": "AKWAIBOM",
    "AGU": "ANAMBRA", "ABN": "ANAMBRA", "ACA": "ANAMBRA", "AJL": "ANAMBRA", "HAL": "ANAMBRA", "HTE": "ANAMBRA", "AWK": "ANAMBRA", "NNE": "ANAMBRA", "ONN": "ANAMBRA", "OGA": "ANAMBRA", "OGZ": "ANAMBRA",
    "BAU": "BAUCHI", "BLR": "BAUCHI", "DAS": "BAUCHI", "DKU": "BAUCHI", "DRZ": "BAUCHI", "AKK": "BAUCHI", "KAT": "BAUCHI", "GML": "BAUCHI", "JMR": "BAUCHI", "KKW": "BAUCHI", "MSH": "BAUCHI", "NNR": "BAUCHI", "SHR": "BAUCHI", "TFW": "BAUCHI", "TRO": "BAUCHI", "WRJ": "BAUCHI", "ZAK": "BAUCHI",
    "YEN": "BAYELSA", "KMR": "BAYELSA", "KMK": "BAYELSA", "NEM": "BAYELSA", "GBB": "BAYELSA", "SAG": "BAYELSA", "SPR": "BAYELSA", "BRS": "BAYELSA",
    "BEN": "BENUE", "PKG": "BENUE", "GBK": "BENUE", "MKD": "BENUE", "OTU": "BENUE", "ADK": "BENUE", "AGT": "BENUE", "ALE": "BENUE", "BRK": "BENUE", "GUM": "BENUE", "GWR": "BENUE", "KND": "BENUE", "KWA": "BENUE", "LGO": "BENUE", "ODZ": "BENUE", "OGW": "BENUE", "OKP": "BENUE", "UKM": "BENUE", "USD": "BENUE",
    "BAM": "BORNO", "BBU": "BORNO", "DAM": "BORNO", "DKW": "BORNO", "HWL": "BORNO", "MAI": "BORNO", "MUG": "BORNO", "ASK": "BORNO", "CHD": "BORNO", "GGN": "BORNO", "GZR": "BORNO", "JRE": "BORNO", "KAL": "BORNO", "KBB": "BORNO", "KWY": "BORNO", "MFN": "BORNO", "MRT": "BORNO", "NGZ": "BORNO",
    "DUK": "CROSSRIVER", "CAL": "CROSSRIVER", "IKM": "CROSSRIVER", "OBU": "CROSSRIVER", "UGE": "CROSSRIVER", "AKP": "CROSSRIVER", "BKL": "CROSSRIVER", "BKR": "CROSSRIVER", "BND": "CROSSRIVER", "ETG": "CROSSRIVER", "OBN": "CROSSRIVER", "ODK": "CROSSRIVER",
    "ABH": "DELTA", "AGB": "DELTA", "BMA": "DELTA", "BUR": "DELTA", "DET": "DELTA", "DNB": "DELTA", "DSZ": "DELTA", "ASB": "DELTA", "WAR": "DELTA", "UGH": "DELTA", "SLG": "DELTA", "OKR": "DELTA", "UKW": "DELTA", "UVW": "DELTA",
    "HKW": "EBONYI", "AFK": "EBONYI", "EZA": "EBONYI", "OHZ": "EBONYI", "ABI": "EBONYI", "EBH": "EBONYI", "IKW": "EBONYI", "ISN": "EBONYI", "OZZ": "EBONYI",
    "ABD": "EDO", "AFZ": "EDO", "AGD": "EDO", "AUB": "EDO", "IGU": "EDO", "UBJ": "EDO", "UCH": "EDO", "OKP": "EDO", "OVB": "EDO",
    "EFY": "EKITI", "EAA": "EKITI", "GED": "EKITI", "IER": "EKITI", "KRE": "EKITI", "MUE": "EKITI", "TUN": "EKITI", "YEK": "EKITI", "EKT": "EKITI", "MOB": "EKITI", "OYE": "EKITI",
    "AGN": "ENUGU", "AGW": "ENUGU", "BBG": "ENUGU", "ENU": "ENUGU", "AWD": "ENUGU", "UDI": "ENUGU", "NSK": "ENUGU", "UZO": "ENUGU", "OJI": "ENUGU",
    "ABC": "ABUJA", "ABJ": "ABUJA", "BWR": "ABUJA", "GWA": "ABUJA", "KUJ": "ABUJA", "KWL": "ABUJA", "RBC": "ABUJA", "RSH": "ABUJA", "YAB": "ABUJA",
    "GME": "GOMBE", "BKK": "GOMBE", "KMG": "GOMBE", "NFD": "GOMBE", "DBS": "GOMBE", "BLN": "GOMBE", "FNY": "GOMBE", "KKR": "GOMBE", "SHM": "GOMBE", "YAM": "GOMBE",
    "WER": "IMO", "ORL": "IMO", "OKI": "IMO", "MGB": "IMO", "KGE": "IMO", "NKR": "IMO", "TTK": "IMO", "UMD": "IMO", "EZN": "IMO", "HJK": "IMO", "ISL": "IMO", "OGT": "IMO", "OHJ": "IMO", "ONJ": "IMO",
    "BBR": "JIGAWA", "BMW": "JIGAWA", "DTU": "JIGAWA", "HJA": "JIGAWA", "KZR": "JIGAWA", "RNG": "JIGAWA", "GRL": "JIGAWA", "GWR": "JIGAWA", "GZK": "JIGAWA", "KYW": "JIGAWA", "MKN": "JIGAWA", "MLR": "JIGAWA", "MYM": "JIGAWA", "RNN": "JIGAWA", "SRN": "JIGAWA", "TKW": "JIGAWA", "YAK": "JIGAWA",
    "KAD": "KADUNA", "DKA": "KADUNA", "MKA": "KADUNA", "ZAR": "KADUNA", "TRN": "KADUNA", "BNG": "KADUNA", "KAF": "KADUNA", "KCH": "KADUNA", "MGN": "KADUNA", "SAB": "KADUNA", "ZKW": "KADUNA", "GGM": "KADUNA", "JMK": "KADUNA", "KBK": "KADUNA", "KUB": "KADUNA", "LRE": "KADUNA", "TBN": "KADUNA",
    "KAN": "KANO", "KMC": "KANO", "BKN": "KANO", "DBT": "KANO", "ABS": "KANO", "AJG": "KANO", "BBJ": "KANO", "BCH": "KANO", "DAL": "KANO", "DGW": "KANO", "DKD": "KANO", "DTA": "KANO", "DTF": "KANO", "WUD": "KANO", "GRN": "KANO", "GWL": "KANO", "GWZ": "KANO", "KBB": "KANO", "KGR": "KANO", "KNG": "KANO", "KRY": "KANO", "MNJ": "KANO", "NSR": "KANO", "RNJ": "KANO", "RRN": "KANO", "SBN": "KANO", "TRK": "KANO", "TSY": "KAN"
}

# ==========================================================
# BUILD REVERSE LOOKUP
# ==========================================================

PLATE_CODE_TO_STATE = {}

for state, data in STATES_LGA.items():
    for code in data["codes"]:
        PLATE_CODE_TO_STATE[code.upper()] = state

# ==========================================================
# CHARACTER CORRECTION (LLL-DDD-LL)
# ==========================================================

DIGIT_TO_LETTER = {'0':'O','1':'I','2':'Z','5':'S','8':'B','6':'G','4':'A','7':'T'}
LETTER_TO_DIGIT = {'O':'0','I':'1','L':'1','Z':'2','S':'5','B':'8','G':'6','T':'7','A':'4','E':'3'}

PLATE_POSITION_TYPE = {
    0:'L',1:'L',2:'L',
    3:'D',4:'D',5:'D',
    6:'L',7:'L'
}

def correct_plate_characters(raw: str) -> str:
    clean = re.sub(r'[^A-Z0-9]', '', raw.upper())
    if len(clean) < 8:
        return clean

    out = []
    for i, ch in enumerate(clean[:8]):
        expected = PLATE_POSITION_TYPE.get(i)
        if expected == 'L':
            out.append(DIGIT_TO_LETTER.get(ch, ch))
        elif expected == 'D':
            out.append(LETTER_TO_DIGIT.get(ch, ch))
        else:
            out.append(ch)
    return "".join(out)

# ==========================================================
# VALIDATION
# ==========================================================

def validate_plate_format(plate_number: str) -> dict:
    if not plate_number:
        return {"valid": False, "format": "NONE", "message": "Empty"}

    clean = re.sub(r'[^A-Z0-9]', '', plate_number.upper())

    if re.match(r'^[A-Z]{3}\d{3}[A-Z]{2}$', clean):
        return {"valid": True, "format": "LLL-DDD-LL", "message": "Standard ✅"}

    if re.match(r'^[A-Z]{2}\d{3}[A-Z]{3}$', clean):
        return {"valid": True, "format": "LL-DDD-LLL", "message": "Old ✅"}

    if re.match(r'^[A-Z]{2,3}\d{2,4}[A-Z]{2,3}$', clean):
        return {"valid": True, "format": "FLEXIBLE", "message": "Flexible ⚠️"}

    return {"valid": False, "format": "INVALID", "message": "No pattern ❌"}

def format_and_validate(plate_string: str) -> dict:
    raw = re.sub(r'[^A-Z0-9]', '', plate_string.upper())
    corrected = correct_plate_characters(raw)

    if re.match(r'^([A-Z]{3})(\d{3})([A-Z]{2})$', corrected):
        formatted = f"{corrected[:3]}-{corrected[3:6]}-{corrected[6:8]}"
    else:
        formatted = corrected

    return {
        "corrected_plate": formatted,
        "validation": validate_plate_format(formatted)
    }

# ==========================================================
# STATE RESOLUTION
# ==========================================================

def get_state_from_plate(plate_number: str) -> str:
    clean = re.sub(r'[^A-Z0-9]', '', plate_number.upper())

    # Try prefix
    if len(clean) >= 3:
        prefix = clean[:3]
        if prefix in PLATE_CODE_TO_STATE:
            return PLATE_CODE_TO_STATE[prefix]

    # Try suffix
    if len(clean) >= 2:
        suffix = clean[-2:]
        if suffix in PLATE_CODE_TO_STATE:
            return PLATE_CODE_TO_STATE[suffix]

    return "Unknown"

def get_lgas_for_state(state_name: str) -> list:
    return STATES_LGA.get(state_name.upper(), {}).get("lgas", [])

# ==========================================================
# ENRICHMENT
# ==========================================================

def enrich_plate_data(plate_number: str, detected_state: str = None) -> dict:
    validation = validate_plate_format(plate_number)
    plate_state = get_state_from_plate(plate_number)
    lgas = get_lgas_for_state(plate_state)

    state_match = True
    if detected_state and detected_state.upper() not in ("UNKNOWN", "N/A", ""):
        state_match = detected_state.upper() == plate_state.upper()

    return {
        "plate_number": plate_number,
        "plate_state": plate_state.capitalize(),
        "detected_state": (detected_state or "Unknown").capitalize(),
        "state_match": state_match,
        "lgas": lgas,
        "lga_count": len(lgas),
        "format_valid": validation["valid"],
        "plate_format": validation["format"],
        "format_message": validation["message"],
    }

# ==========================================================
# SAFETY CHECK
# ==========================================================

_REQUIRED = [
    "enrich_plate_data",
    "validate_plate_format",
    "get_state_from_plate",
    "format_and_validate",
    "correct_plate_characters"
]

_missing = [fn for fn in _REQUIRED if fn not in globals()]
if _missing:
    raise ImportError(f"statelga.py incomplete. Missing: {_missing}")