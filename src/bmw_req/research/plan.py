"""Research plan as data: vehicle lines × markets × agents (knowledge-base.md). Wave-3 tasks simulate
'market events' — new information that arrives later in the multi-wave process (Q-012, D-027)."""

from bmw_req.research.agents import Task

# (line, derivative, market, main rivals in that market, BMW model name for reviews)
LINE_MARKETS = [
    ("5 Series", "G60", "US", "Mercedes E-Class, Audi A6 e-tron, Lexus ES, Genesis G80, Tesla Model 3", "BMW 5 Series / i5"),
    ("5 Series", "G60", "EU", "Mercedes E-Class, Audi A6 / A6 e-tron, Tesla Model 3", "BMW 5 Series / i5"),
    ("5 Series", "G68", "CN", "Mercedes E-Class L, Audi A6L, Xiaomi SU7, Tesla Model 3, NIO ET5/ET7, AITO", "BMW 5 Series long wheelbase (5 Series Li / i5 LWB)"),
    ("7 Series", "G70", "US", "Mercedes S-Class, Lexus LS, Porsche Panamera, Audi A8", "BMW 7 Series / i7"),
    ("7 Series", "G70", "CN", "Mercedes S-Class / Maybach S, Maextro S800, AITO M9, Yangwang U7, Audi A8L", "BMW 7 Series / i7"),
    ("7 Series", "G70", "EU", "Mercedes S-Class / EQS, Audi A8, Porsche Panamera", "BMW 7 Series / i7"),
    ("1 Series", "F70", "EU", "Audi A3, Mercedes A-Class / CLA, VW Golf GTI, Volvo EX30", "BMW 1 Series (F70)"),
    ("1 Series", "F70", "RoW", "Audi A3, Mercedes A-Class / CLA, VW Golf GTI (Japan, UK-adjacent markets)", "BMW 1 Series (F70)"),
]

TREND_FOCUS = ("software and AI voice assistant, ADAS experience, charging/range, interior and rear-seat comfort, "
               "physical vs touch controls, personalisation")


def _slug(*parts) -> str:
    return ":".join(p for p in parts if p)


def build_plan() -> list[Task]:
    tasks: list[Task] = []
    for line, d, m, rivals, bmw_name in LINE_MARKETS:
        ctx = {"Main rivals": rivals}
        tasks.append(Task(_slug("cs", d, m), "competitor_scout", line, d, m,
                          f"What do {rivals} offer customers in {m} in 2025-2026 that the {bmw_name} lacks or does worse?", context=ctx))
        tasks.append(Task(_slug("rm", d, m), "review_miner", line, d, m,
                          f"Professional reviews (2024-2026) of the {bmw_name} and its main rival(s) ({rivals}) in {m}: "
                          "praise and criticism on interior, infotainment/iDrive, comfort, driving, ADAS, range/charging.", context=ctx))
        tasks.append(Task(_slug("ts", d, m), "trend_scout", line, d, m,
                          f"What will premium {'compact' if line == '1 Series' else 'luxury' if line == '7 Series' else 'executive-sedan'} "
                          f"buyers in {m} expect by 2029-2031: {TREND_FOCUS}."))
    # deepest line (5 Series) gets an extra competitor angle per market and a sales analyst
    tasks += [
        Task("cs2:G68:CN", "competitor_scout", "5 Series", "G68", "CN",
             "Chinese premium EV/EREV sedans and SUVs (Xiaomi SU7/YU7, AITO, Zeekr, NIO): smart cockpit, Huawei/HarmonyOS ecosystem, "
             "intelligent driving (city NOA), rear-seat features that draw buyers away from German executive sedans."),
        Task("cs2:G60:US", "competitor_scout", "5 Series", "G60", "US",
             "Driver assistance (hands-free highway driving such as Super Cruise / BlueCruise / Tesla FSD), connectivity and "
             "reliability that US midsize-luxury buyers value in rivals of the BMW 5 Series."),
        Task("cs2:G60:EU", "competitor_scout", "5 Series", "G60", "EU",
             "New Mercedes CLA/E-Class MB.OS and Audi A6 e-tron features in Europe: AI assistant, charging speed, range, OTA updates."),
        Task("ma:G68:CN", "market_analyst", "5 Series", "G68", "CN",
             "Sales and growth of executive sedans (BMW 5 Series LWB, Audi A6L, Mercedes E-Class L) and new-energy rivals in China 2025-2026."),
        Task("ma:G60:EU", "market_analyst", "5 Series", "G60", "EU",
             "Executive sedan and wagon sales in Europe 2025-2026 (BMW 5 Series/i5, Mercedes E-Class, Audi A6) and BEV share."),
        Task("ma:G60:US", "market_analyst", "5 Series", "G60", "US",
             "US midsize luxury sedan sales 2025-2026 and EV demand after the federal tax credit ended."),
        Task("ma:G70:CN", "market_analyst", "7 Series", "G70", "CN",
             "China ultra-luxury sedan sales 2025-2026 (Maextro S800, BMW 7 Series, Mercedes S-Class/Maybach, Yangwang U7)."),
    ]
    for m, focus in [
        ("EU", "Climate (winter range, heat), annual mileage and long-distance motorway use, charging infrastructure (public chargers, fast-charging growth), powertrain mix 2025-2026, attitudes to Chinese brands."),
        ("US", "Climate extremes and EV range, annual mileage and commuting, home vs public charging and fast-charging availability, powertrain mix after the tax credit ended, premium buyer attitudes."),
        ("CN", "Climate (north-east winters, south humidity), urban usage and chauffeur/rear-seat culture, charging/battery swap infrastructure, NEV/EREV mix, smart-cockpit culture among premium buyers."),
        ("RoW", "Japan and South Korea premium car markets: usage, compact-car culture, charging infrastructure and powertrain mix (hybrids), import premium brand demand."),
    ]:
        tasks.append(Task(f"mp:{m}", "market_profile_scout", None, None, m, focus))
    # wave-3 'market events' (most recent news, simulated as arriving later)
    tasks += [
        Task("ev:G70:EU:mbos", "competitor_scout", "7 Series", "G70", "EU",
             "Latest 2026 news: Mercedes S-Class facelift / MB.OS features (AI assistant, MB.DRIVE, rear comfort) and customer reception.", wave=3),
        Task("ev:G70:CN:maextro", "competitor_scout", "7 Series", "G70", "CN",
             "Latest 2026 Chinese ultra-luxury launches and updates (Maextro S800, AITO M9/M8, Yangwang U7, Hongqi): new customer-facing features and sales momentum.", wave=3),
        Task("ev:G68:CN:nk", "competitor_scout", "5 Series", "G68", "CN",
             "Latest 2026 news on BMW Neue Klasse iX3 long wheelbase / i3 for China (OS X China, Momenta ADAS, Huawei/Alibaba/DeepSeek features) and how Chinese media and buyers received it versus local rivals.", wave=3),
        Task("ev:G60:US:ev", "market_analyst", "5 Series", "G60", "US",
             "Latest 2026 news on the US EV demand shift (post tax credit), hybrid/PHEV demand and luxury buyers' powertrain preferences.", wave=3),
        Task("ev:G60:EU:eclass", "competitor_scout", "5 Series", "G60", "EU",
             "Latest 2026 news: new Mercedes E-Class / electric C-Class and Audi A6 updates in Europe (MB.OS, AI assistant, charging, range).", wave=3),
        Task("ev:F70:EU:cla", "competitor_scout", "1 Series", "F70", "EU",
             "Latest 2026 news: Mercedes CLA (MB.OS) and Chinese compact premium EVs in Europe - customer-facing features, reviews and early sales.", wave=3),
    ]
    ids = [t.id for t in tasks]
    assert len(ids) == len(set(ids)), "duplicate task ids"
    return tasks


PILOT_TASK_IDS = ["cs:G68:CN", "rm:G60:US", "ts:G60:EU"]
