"""English / Hindi / Telugu strings. Hindi and Telugu are drafts: have a native speaker review them."""
LANGS = [("en", "English"), ("hi", "हिन्दी"), ("te", "తెలుగు")]

ALERTS = {
    "en": {
        "dry_critical": "{field} is critically dry ({v}%). Water now.",
        "over_wet": "{field} looks over-irrigated ({v}%). Pause watering.",
        "battery_low": "Sensor battery low on {field} ({v}%).",
        "water_planned": "{field}: water at {time} for {mins} min ({litres} L).",
        "rain_skip": "{field}: rain expected, watering skipped.",
        "sensor_stuck": "The sensor on {field} looks stuck. Please check it.",
        "sensor_jump": "The sensor reading on {field} jumped suddenly. Please check it.",
        "valve_fault": "The valve on {field} did not respond.",
    },
    "hi": {
        "dry_critical": "{field} की मिट्टी बहुत सूखी है ({v}%)। तुरंत पानी दें।",
        "over_wet": "{field} में ज़रूरत से ज़्यादा पानी है ({v}%)। सिंचाई रोकें।",
        "battery_low": "{field} के सेंसर की बैटरी कम है ({v}%)।",
        "water_planned": "{field}: {time} बजे {mins} मिनट पानी दें ({litres} लीटर)।",
        "rain_skip": "{field}: बारिश की संभावना है, सिंचाई टाली गई।",
        "sensor_stuck": "{field} का सेंसर अटका हुआ लगता है। कृपया जाँचें।",
        "sensor_jump": "{field} के सेंसर की रीडिंग अचानक बदल गई। कृपया जाँचें।",
        "valve_fault": "{field} का वाल्व जवाब नहीं दे रहा।",
    },
    "te": {
        "dry_critical": "{field} నేల చాలా పొడిగా ఉంది ({v}%). వెంటనే నీరు పెట్టండి.",
        "over_wet": "{field}లో నీరు ఎక్కువగా ఉంది ({v}%). నీటి పారుదల ఆపండి.",
        "battery_low": "{field} సెన్సార్ బ్యాటరీ తక్కువగా ఉంది ({v}%).",
        "water_planned": "{field}: {time} గంటలకు {mins} నిమిషాలు నీరు పెట్టండి ({litres} లీటర్లు).",
        "rain_skip": "{field}: వర్షం వచ్చే అవకాశం ఉంది, నీటి పారుదల వాయిదా వేశాం.",
        "sensor_stuck": "{field} సెన్సార్ ఆగిపోయినట్లు ఉంది. దయచేసి తనిఖీ చేయండి.",
        "sensor_jump": "{field} సెన్సార్ రీడింగ్ అకస్మాత్తుగా మారింది. దయచేసి తనిఖీ చేయండి.",
        "valve_fault": "{field} వాల్వ్ స్పందించడం లేదు.",
    },
}

UI = {
    "en": {
        "nav_fields": "My fields", "nav_manage": "Manage", "nav_explore": "Explore regions", "nav_schedule": "Irrigation schedule",
        "nav_alerts": "Alerts", "nav_savings": "Water savings", "nav_health": "Sensor health", "nav_reports": "Reports",
        "nav_coop": "Cooperative view", "logout": "Sign out", "language": "Language",
        "last_reading": "Last reading", "soil_moisture": "soil moisture", "air": "Air", "soil": "Soil", "humidity": "Humidity",
        "battery": "Sensor battery", "next_watering": "Next watering", "needs_attention": "Needs attention",
        "all_clear": "All clear for this field.", "nothing_planned": "Nothing planned.", "field_details": "Field details",
        "status_dry": "Dry", "status_ok": "Good", "status_wet": "Wet",
        "lede_irrigate": "Moisture is forecast to fall to {p}% within six hours. Water for {m} minutes.",
        "lede_hold": "Moisture should hold near {p}% over the next six hours. No watering needed.",
        "lede_rain": "Rain is expected soon, so watering is on hold. Moisture should reach about {p}%.",
        "lede_offline": "Live forecast is offline. Showing the latest sensor reading only.",
        "valve": "Irrigation valve", "valve_open": "Open", "valve_closed": "Closed", "valve_auto": "Automatic", "valve_off": "Off",
        "water_now": "Water now", "stop": "Stop", "minutes": "minutes", "growth_stage": "Growth stage",
        "forecast_accuracy": "Forecast accuracy", "settings": "Field settings",
    },
    "hi": {
        "nav_fields": "मेरे खेत", "nav_manage": "प्रबंधन", "nav_explore": "क्षेत्र खोजें", "nav_schedule": "सिंचाई कार्यक्रम",
        "nav_alerts": "चेतावनियाँ", "nav_savings": "पानी की बचत", "nav_health": "सेंसर की स्थिति", "nav_reports": "रिपोर्ट",
        "nav_coop": "सहकारी समिति दृश्य", "logout": "बाहर निकलें", "language": "भाषा",
        "last_reading": "आखिरी रीडिंग", "soil_moisture": "मिट्टी की नमी", "air": "हवा", "soil": "मिट्टी", "humidity": "आर्द्रता",
        "battery": "सेंसर बैटरी", "next_watering": "अगली सिंचाई", "needs_attention": "ध्यान दें",
        "all_clear": "इस खेत में सब ठीक है।", "nothing_planned": "कुछ तय नहीं है।", "field_details": "खेत की जानकारी",
        "status_dry": "सूखा", "status_ok": "ठीक", "status_wet": "गीला",
        "lede_irrigate": "अगले छह घंटों में नमी घटकर {p}% होने का अनुमान है। {m} मिनट पानी दें।",
        "lede_hold": "अगले छह घंटों में नमी लगभग {p}% रहेगी। पानी की ज़रूरत नहीं।",
        "lede_rain": "जल्द बारिश की संभावना है, इसलिए सिंचाई रुकी है। नमी लगभग {p}% तक पहुँचेगी।",
        "lede_offline": "पूर्वानुमान अभी उपलब्ध नहीं है। सिर्फ़ ताज़ा रीडिंग दिख रही है।",
        "valve": "सिंचाई वाल्व", "valve_open": "खुला", "valve_closed": "बंद", "valve_auto": "स्वचालित", "valve_off": "बंद रखें",
        "water_now": "अभी पानी दें", "stop": "रोकें", "minutes": "मिनट", "growth_stage": "फसल की अवस्था",
        "forecast_accuracy": "पूर्वानुमान की सटीकता", "settings": "खेत की सेटिंग",
    },
    "te": {
        "nav_fields": "నా పొలాలు", "nav_manage": "నిర్వహణ", "nav_explore": "ప్రాంతాలను చూడండి", "nav_schedule": "నీటి పారుదల షెడ్యూల్",
        "nav_alerts": "హెచ్చరికలు", "nav_savings": "నీటి ఆదా", "nav_health": "సెన్సార్ స్థితి", "nav_reports": "నివేదికలు",
        "nav_coop": "సహకార సంఘం వీక్షణ", "logout": "సైన్ అవుట్", "language": "భాష",
        "last_reading": "చివరి రీడింగ్", "soil_moisture": "నేల తేమ", "air": "గాలి", "soil": "నేల", "humidity": "ఆర్ద్రత",
        "battery": "సెన్సార్ బ్యాటరీ", "next_watering": "తదుపరి నీటి పారుదల", "needs_attention": "శ్రద్ధ అవసరం",
        "all_clear": "ఈ పొలంలో అంతా బాగుంది.", "nothing_planned": "ఏమీ ప్లాన్ చేయలేదు.", "field_details": "పొలం వివరాలు",
        "status_dry": "పొడి", "status_ok": "మంచిది", "status_wet": "తడి",
        "lede_irrigate": "తదుపరి ఆరు గంటల్లో తేమ {p}%కి తగ్గుతుందని అంచనా. {m} నిమిషాలు నీరు పెట్టండి.",
        "lede_hold": "తదుపరి ఆరు గంటల్లో తేమ సుమారు {p}% ఉంటుంది. నీరు అవసరం లేదు.",
        "lede_rain": "త్వరలో వర్షం పడే అవకాశం ఉంది, అందుకే నీటి పారుదల ఆగింది. తేమ సుమారు {p}%కి చేరుతుంది.",
        "lede_offline": "అంచనా ప్రస్తుతం అందుబాటులో లేదు. తాజా రీడింగ్ మాత్రమే చూపిస్తున్నాం.",
        "valve": "నీటి వాల్వ్", "valve_open": "తెరిచి ఉంది", "valve_closed": "మూసి ఉంది", "valve_auto": "ఆటోమేటిక్", "valve_off": "ఆఫ్",
        "water_now": "ఇప్పుడే నీరు పెట్టండి", "stop": "ఆపండి", "minutes": "నిమిషాలు", "growth_stage": "పంట దశ",
        "forecast_accuracy": "అంచనా ఖచ్చితత్వం", "settings": "పొలం సెట్టింగ్‌లు",
    },
}


def _get(table, lang, key):
    return table.get(lang, {}).get(key) or table["en"][key]


def alert_text(lang, key, **kw):
    return _get(ALERTS, lang if lang in ALERTS else "en", key).format(**kw)


def ui(lang, key, **kw):
    s = _get(UI, lang if lang in UI else "en", key)
    return s.format(**kw) if kw else s
