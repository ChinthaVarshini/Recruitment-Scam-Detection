import re


LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "unknown": "Unknown",
}

RISK_PATTERNS = {
    "hi": {
        "PAYMENT_REQUEST": [
            r"(?:रजिस्ट्रेशन|पंजीकरण|आवेदन|जॉइनिंग|सिक्योरिटी)\s*(?:फीस|फी|शुल्क|जमा)",
            r"(?:पैसे|रुपये|राशि).{0,30}(?:जमा|भेजें|भुगतान|दीजिए|दें)",
            r"(?:नौकरी|जॉब).{0,30}(?:फीस|शुल्क|पैसे|रुपये)",
            r"\b(?:naukri|job)\s+ke\s+liye\s+paise\b",
            r"\bpaise\s+(?:jama|bhej|bhare)\s+(?:kare|karo|kijiye)?\b",
        ],
        "URGENCY": [
            r"(?:तुरंत|अभी|आज ही).{0,25}(?:आवेदन|संपर्क|भुगतान|जमा)",
            r"(?:सीमित|केवल कुछ).{0,20}(?:पद|जगह|सीट)",
            r"\b(?:abhi|turant)\s+(?:apply|sampark|payment)\b",
            r"\baaj\s+hi\b",
        ],
        "SALARY": [
            r"(?:गारंटीड|गारंटी|निश्चित).{0,20}(?:कमाई|वेतन|आय)",
            r"(?:घर बैठे|आसान).{0,20}(?:कमाएं|कमाई|पैसा)",
            r"\bghar\s+baithe\s+(?:kamaye|kamai)\b",
        ],
        "NO_EXPERIENCE": [
            r"(?:बिना अनुभव|अनुभव की आवश्यकता नहीं|अनुभव जरूरी नहीं)",
            r"\b(?:bina\s+anubhav|experience\s+ki\s+zarurat\s+nahi)\b",
        ],
        "CONTACT": [
            r"(?:व्हाट्सऐप|व्हाट्सएप|टेलीग्राम|संपर्क करें)",
            r"\b(?:whatsapp|telegram)\s+(?:par|pe)\s+(?:sampark|message)\b",
        ],
    },
    "te": {
        "PAYMENT_REQUEST": [
            r"(?:రిజిస్ట్రేషన్|నమోదు|దరఖాస్తు|జాయినింగ్|సెక్యూరిటీ)\s*(?:ఫీజు|ఫీ|రుసుము|డిపాజిట్)",
            r"(?:డబ్బు|డబ్బులు|రూపాయలు|ఫీజు).{0,30}(?:చెల్లించండి|జమ చేయండి|పంపండి|కట్టండి)",
            r"(?:ఉద్యోగం|జాబ్).{0,30}(?:ఫీజు|రుసుము|డబ్బులు)",
            r"\b(?:munduga|modatiga)\s+(?:dabbulu|dabbu)\s+(?:kattandi|chellinchandi)\b",
            r"\b(?:job|udyogam)\s+kosam\s+(?:dabbulu|fee)\b",
            r"\bregistration\s+fee\s+(?:kattandi|chellinchandi)\b",
        ],
        "URGENCY": [
            r"(?:వెంటనే|ఇప్పుడే|ఈరోజే).{0,25}(?:దరఖాస్తు|సంప్రదించండి|చెల్లించండి|పంపండి)",
            r"(?:పరిమిత|కొన్ని మాత్రమే).{0,20}(?:ఖాళీలు|అవకాశాలు|పోస్టులు)",
            r"\b(?:ventane|ippude)\s+(?:apply|sampradinchandi)\b",
            r"\b(?:ee\s+roje|konni\s+vacancies)\b",
        ],
        "SALARY": [
            r"(?:గ్యారంటీ|హామీ).{0,20}(?:జీతం|ఆదాయం|సంపాదన)",
            r"(?:ఇంటి నుంచే|ఇంట్లో ఉండి).{0,20}(?:సంపాదించండి|ఆదాయం)",
            r"\b(?:intlo|inti\s+nunchi)\s+(?:undi\s+)?sampadinchandi\b",
        ],
        "NO_EXPERIENCE": [
            r"(?:అనుభవం అవసరం లేదు|అనుభవం అక్కర్లేదు|అనుభవం లేకపోయినా)",
            r"\b(?:anubhavam|experience)\s+(?:avasaram|av?saram)\s+ledu\b",
        ],
        "CONTACT": [
            r"(?:వాట్సాప్|టెలిగ్రామ్|వెంటనే సంప్రదించండి)",
            r"\b(?:whatsapp|telegram)\s+(?:lo|dwara)\s+(?:sampradinchandi|message)\b",
        ],
    },
}

RISK_METADATA = {
    "PAYMENT_REQUEST": (
        "CRITICAL",
        "Possible recruitment fee or payment request detected in the job text.",
    ),
    "URGENCY": (
        "HIGH",
        "Urgency or pressure-based recruitment wording detected in the job text.",
    ),
    "SALARY": (
        "MEDIUM",
        "Guaranteed or unusually easy earning wording detected in the job text.",
    ),
    "NO_EXPERIENCE": (
        "MEDIUM",
        "No-experience hiring wording detected in the job text.",
    ),
    "CONTACT": (
        "LOW",
        "Direct messaging or contact wording detected in the job text.",
    ),
}


def detect_language(text: str) -> str:
    if re.search(r"[\u0c00-\u0c7f]", text):
        return "te"
    if re.search(r"[\u0900-\u097f]", text):
        return "hi"

    lowered = text.lower()
    for language, categories in RISK_PATTERNS.items():
        if any(
            re.search(pattern, lowered, flags=re.IGNORECASE)
            for patterns in categories.values()
            for pattern in patterns
        ):
            return language
    if re.search(r"[a-z]", lowered):
        return "en"
    return "unknown"


def detect_multilingual_risk_indicators(text: str) -> tuple[str, list[dict[str, str]]]:
    language = detect_language(text)
    patterns_by_category = RISK_PATTERNS.get(language)
    if not patterns_by_category:
        return language, []

    indicators = []
    for category, patterns in patterns_by_category.items():
        match = next(
            (
                found
                for pattern in patterns
                if (found := re.search(pattern, text, flags=re.IGNORECASE))
            ),
            None,
        )
        if not match:
            continue

        severity, message = RISK_METADATA[category]
        indicators.append(
            {
                "type": category,
                "severity": severity,
                "message": message,
                "evidence": match.group(0)[:160],
                "language": language,
            }
        )
    return language, indicators
