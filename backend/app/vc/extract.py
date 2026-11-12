"""기사 제목·본문에서 투자 라운드 정보를 뽑는 규칙 기반 추출기.
보도자료 문형이 정형적이라는 점에 기대는 방식이라 오인식이 있을 수 있다. 원문 링크를 항상 함께 저장한다."""
import html
import re

QUOTES = r"['\"‘’“”「」『』]"
ROUND_PATTERNS = [
    (r"프리\s*-?\s*IPO|pre\s*-?\s*ipo|상장\s*전\s*투자", "Pre-IPO"),
    (r"프리\s*-?\s*시리즈\s*-?\s*([A-Ga-g])|프리\s*-?\s*([A-Ga-g])\b|pre\s*-?\s*(?:series\s*)?-?([A-Ga-g])\b", "Pre-{}"),
    (r"시리즈\s*-?\s*([A-Ga-g])\s*(?:[1-3]\s*)?(?:브릿지|브리지)", "Series {} Bridge"),
    (r"시리즈\s*-?\s*([A-Ga-g])|series\s*-?\s*([A-Ga-g])\b", "Series {}"),
    (r"프리\s*-?\s*시드|pre\s*-?\s*seed", "Pre-Seed"),
    (r"시드|seed", "Seed"),
    (r"브릿지|브리지", "Bridge"),
    (r"팁스|TIPS", "TIPS"),
    (r"전략적\s*투자|\bSI\b", "SI"),
]
INVEST_KW = re.compile(r"투자\s*유치|투자유치|투자\s*받|투자\s*확보|규모\s*투자|후속\s*투자|추가\s*유치|억\s*원?\s*유치|펀딩|라운드\s*(?:마무리|완료|클로징)|"
                       r"시리즈\s*-?\s*[A-Ga-g]|프리\s*-?\s*[A-Ga-g]\b|시드\s*투자|프리\s*IPO|팁스\s*선정|TIPS\s*선정", re.I)
MNA_KW = re.compile(r"인수\s*합병|M&A|인수(?!\s*금융)|품는다|품었다|합병|매각|흡수합병|지분\s*\d+%?\s*(?:인수|취득)")
FUND_KW = re.compile(r"펀드|투자조합|벤처투자조합")
FUND_ACT = re.compile(r"결성|조성|출범|클로징|결성\s*완료|조성\s*완료")
# 여러 기업을 묶어 다루는 기사나 행사·지원사업 기사는 개별 라운드가 아니다
SKIP_KW = re.compile(r"\d+\s*곳|\d+\s*개\s*사|\d+\s*개사|주간|월간|결산|총정리|투자\s*유치\s*(?:지원|설명회|역량|교육|컨설팅|행사|대회|상담|프로그램|IR)|"
                     r"데모데이|IR\s*피칭|투자\s*동향|투자\s*현황|모집|개최|성료|세미나|포럼|간담회|업무\s*협약|MOU|투자유치\s*스타트업$|"
                     r"지원|성과|육성|모색|도전|노하우|멘토링|의향서|검토|논의|추진|전망|루머|소문|\?|뭉칫돈|어디서|협상|될까|앞두고|베팅|위클리|돌입|미확정|재공시|급등|급락|특징주|주가|→|매각|프리즘|잭팟|활기|몸값|IPO설|투자설|없다|K-스타트업")
GENERIC_NAMES = {"스타트업", "기업", "사업", "추가", "회사", "업체", "국내", "정부", "한국", "韓", "美", "中", "日", "벤처", "창업기업",
                 "중소기업", "자회사", "계열사", "사업부", "지분", "경영권"}
INSTITUTION = re.compile(r"(센터|진흥원|협회|대학교|대학|[가-힣]대|시청|도청|은행|공사|공단|재단|위원회|창경|중기부|산업부|과기부|정부|연구원|"
                         r"특별시|광역시|[가-힣]{2}시|[가-힣]{2}도|[가-힣]{2}군|진흥회|조합)$")
TAIL_WORDS = re.compile(r"^(로보틱스|테라퓨틱스|바이오|바이오텍|랩스|랩|테크|AI|에이아이|벤처스|게임즈|엔터테인먼트|모빌리티|에너지|헬스케어|"
                        r"사이언스|파마|메디컬|솔루션|시스템즈|네트웍스|스튜디오|컴퍼니|코리아|테크놀로지|테크놀로지스)$")
INVESTOR_SUFFIX = re.compile(
    r"(인베스트먼트|인베스트|벤처스|파트너스|캐피탈|캐피털|벤처투자|창업투자|창투|투자|증권|은행|자산운용|기술지주|액셀러레이터|"
    r"홀딩스|벤처캐피탈|VC|랩스|엔젤|엔젤스|재단|펀드|기금|공사|금융|금융그룹|스튜디오|파운더스|이노베이션|신용보증기금|기술보증기금|"
    r"Ventures|Capital|Partners|Investment|Investments|Labs|Fund)$", re.I)
STOP_TOKENS = {"이번", "기존", "신규", "투자", "투자자", "투자사", "다수", "등", "국내", "해외", "글로벌", "복수", "회사", "당사",
               "전략적 투자자", "재무적 투자자", "기관", "기관투자자", "벤처캐피탈", "VC", "액셀러레이터", "관계자", "누적", "총"}
DESCRIPTORS = re.compile(r"^(?:기존|신규|리드|주요|글로벌|국내|해외|미국|일본|후속|공동|전략적|재무적)\s*(?:투자자|투자사|주주)?(?:인|로|로서|이자)?\s*")
POS = re.compile(r"유치|선정|수상|흑자|돌파|출시|협약|상장|성장|확대|수출|진출|인증|달성|신고가|최대")
NEG = re.compile(r"적자|폐업|구조조정|소송|횡령|감원|파산|논란|철수|중단|해고|법정관리|회생|압수수색|부도|손실|매출\s*급감")


def clean_text(s: str) -> str:
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s or "", flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def norm_name(name: str) -> str:
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사|Inc\.?|Co\.?,?\s*Ltd\.?|Corp\.?", "", name, flags=re.I)
    return re.sub(r"[\s\-_·.,'\"‘’“”()]", "", s).lower()


AMOUNT_RE = re.compile(r"(\d[\d,]*\.?\d*)\s*(조|천억|백억|억|천만|백만|만)\s*(?:(\d[\d,]*)\s*(천억|백억|억|천만|백만|만)\s*)?(원|달러|불|엔|유로)?")
VALUATION_BEFORE = re.compile(r"(기업\s*가치|밸류에이션|밸류|가치|시가총액|몸값)\s*(?:는|가|를|최대|약)?\s*$")
VALUATION_AFTER = re.compile(r"^\s*(?:의|규모의)?\s*(?:기업\s*가치|밸류|가치|몸값)")


def _amount_of(m) -> float:
    unit = {"조": 1e12, "천억": 1e11, "백억": 1e10, "억": 1e8, "천만": 1e7, "백만": 1e6, "만": 1e4}
    amt = float(m.group(1).replace(",", "")) * unit[m.group(2)]
    if m.group(3):
        amt += float(m.group(3).replace(",", "")) * unit[m.group(4)]
    return amt * {"달러": 1380.0, "불": 1380.0, "엔": 9.0, "유로": 1500.0}.get(m.group(5) or "원", 1.0)


def split_amounts(text: str) -> tuple[tuple[float | None, str | None], float | None]:
    """제목의 금액 중 기업가치 표현은 떼어내고 (투자금, 원문), 기업가치를 돌려준다."""
    invest, valuation = (None, None), None
    for m in AMOUNT_RE.finditer(text):
        amt = _amount_of(m)
        if amt < 1e7:
            continue
        # 제목 맨 앞 금액('2조 딥엑스 프리IPO')은 몸값 수식어로 쓰이는 경우가 많다
        if m.start() == 0 or VALUATION_BEFORE.search(text[max(0, m.start() - 12):m.start()]) or VALUATION_AFTER.search(text[m.end():m.end() + 8]):
            valuation = valuation or amt
        elif invest[0] is None:
            invest = (amt, m.group(0).strip())
    if invest[0] is None:
        m = re.search(r"(수십|수백|수천)\s*(억|만)\s*(원|달러)?", text)
        if m:
            invest = (None, m.group(0).strip())
    return invest, valuation


def parse_amount(text: str) -> tuple[float | None, str | None]:
    """'120억 원', '1조 2000억', '3000만 달러', '수십억 원' → (원 단위 금액, 원문 표기)."""
    m = re.search(r"(\d[\d,]*\.?\d*)\s*(조|억|만)\s*(?:(\d[\d,]*)\s*(억|만|천만)\s*)?(원|달러|불|엔|유로)?", text)
    if m:
        unit = {"조": 1e12, "억": 1e8, "만": 1e4, "천만": 1e7}
        amt = float(m.group(1).replace(",", "")) * unit[m.group(2)]
        if m.group(3):
            amt += float(m.group(3).replace(",", "")) * unit[m.group(4)]
        cur = m.group(5) or "원"
        fx = {"달러": 1380.0, "불": 1380.0, "엔": 9.0, "유로": 1500.0}.get(cur, 1.0)
        if amt * fx < 1e7:  # '3만 명' 같은 문맥의 오인식 방지: 1천만 원 미만은 버린다
            return None, None
        return amt * fx, m.group(0).strip()
    m = re.search(r"(수십|수백|수천)\s*(억|만)\s*(원|달러)?", text)
    if m:
        return None, m.group(0).strip()
    return None, None


def parse_round(text: str) -> str | None:
    for pat, label in ROUND_PATTERNS:
        m = re.search(pat, text, re.I)
        if m:
            letter = next((g for g in m.groups() if g), None) if m.groups() else None
            return label.format(letter.upper()) if letter else label.replace(" {}", "").replace("-{}", "")
    return None


def _strip_title(title: str) -> str:
    t = html.unescape(title or "").replace("\ufeff", "").strip()
    t = re.sub(r"(?:\s+[-|–]\s+[^-|–]{2,25}){1,2}$", "", t)   # 구글 뉴스의 ' - 매체명'
    t = re.sub(r"^.{2,30}\s::\s", "", t)                        # '매체명 :: 제목'
    t = re.sub(r"^(?:\[[^\]]{1,20}\]|\([^)]{1,12}\)|【[^】]{1,20}】)\s*", "", t)  # 머리말 [단독] 등
    return t.strip()


def _name_from_subject(subj: str) -> str | None:
    subj = re.split(r"…|\.\.\.|···", subj.strip())[-1].strip()   # '구호…회사명' 꼴은 뒤쪽이 주어
    m = re.search(QUOTES + r"([^'\"‘’“”「」『』]{1,30})" + QUOTES, subj)
    if m:
        rest = re.sub(r"\([^)]*\)", "", subj[m.end():]).strip()
        if not rest:
            name = m.group(1).strip()
            return None if name in GENERIC_NAMES else name
        subj = rest   # "'드론 설계·운영' 프리뉴" 꼴: 따옴표 안은 설명, 뒤가 회사명
    subj = re.sub(r"\([^)]*\)", "", subj).strip()
    toks = subj.split()
    if not toks:
        return None
    name = toks[-1]
    if len(toks) >= 2 and TAIL_WORDS.match(name) and not re.search(r"(스타트업|기업|운영사|개발사|회사|플랫폼)$", toks[-2]):
        name = toks[-2] + " " + name   # '파운드리 로보틱스'처럼 두 단어로 된 이름
    if len(name) > 3 and re.search(r"[가-힣](는|은)$", name):
        name = name[:-1]
    name = name.strip(" '\"‘’“”「」『』")
    if (len(name) < 2 or len(name) > 30 or re.fullmatch(r"[\d,.%]+", name) or name in GENERIC_NAMES
            or re.match(r"(프리|시리즈|IPO|상장|투자|펀드|[\d①-⑳])", name, re.I) or re.search(r"설$|들$", name)):
        return None
    return name


def company_from_title(title: str) -> str | None:
    t = _strip_title(title)
    head = t.split(",", 1)[0]
    if "," in t and not INVEST_KW.search(head):
        subj = head
    else:
        m = re.search(r"^(.+?)\s+(?:\d[\d,.]*\s*(?:조|억|만)|시리즈|프리|시드|투자|총\s*\d|누적)", head)
        if not m:
            return None
        subj = m.group(1)
    if len(subj) > 45:
        return None
    name = _name_from_subject(subj)
    if name and INSTITUTION.search(name):
        return None
    return name


def _split_names(seg: str) -> list[str]:
    seg = re.sub(r"\([^)]*\)", "", seg)
    parts = re.split(r"\s*(?:,|·|ㆍ|/|、|\s및\s|\s그리고\s|(?<=[가-힣A-Za-z])(?:와|과)\s)\s*", seg)
    out = []
    for p in parts:
        p = DESCRIPTORS.sub("", p.strip())
        p = re.sub(r"^(?:이번\s*(?:투자|라운드)(?:에는|에|는)?|투자에는|이번에는)\s*", "", p)
        p = re.sub(r"\s*(?:등|등이|등의|등에서|총\s*\d+곳|이|가|도)$", "", p).strip(" ,.")
        if 2 <= len(p) <= 28 and p not in STOP_TOKENS and not re.search(r"[다요음]$|했|됐|한다|이며|으로|에서|부터", p):
            out.append(p)
    return out


def investors_from_text(text: str, company: str | None = None) -> list[tuple[str, bool]]:
    """(투자자명, 리드 여부) 목록."""
    found: dict[str, bool] = {}
    sents = re.split(r"(?<=[다요음])\.\s+|(?<=다)\s(?=[가-힣A-Z])", text)
    for s in sents[:40]:
        if not re.search(r"투자|라운드|참여|리드|유치", s):
            continue
        segs = []
        for m in re.finditer(r"(?:투자에는|라운드에는|투자사로는|투자자로는|투자는)\s*(.{2,220}?)\s*(?:등이|등\s*\d+곳이|이|가)\s*(?:신규\s*|공동\s*|후속\s*)?(?:참여|참가|투자자로)", s):
            segs.append((m.group(1), True))
        for m in re.finditer(r"([^.]{2,160}?)\s*(?:등으로부터|등에서|으로부터|로부터)\s*[^.]{0,30}?(?:투자|유치|받)", s):
            seg = re.split(r"(?:했으며|으며|이며|하고|했고|,\s*이번)\s+", m.group(1))[-1]
            segs.append((seg.split("는 ")[-1].split("은 ")[-1], False))
        for m in re.finditer(r"리드\s*투자(?:자|사)는\s*([^,.]{2,30}?)(?:이다|다|이며|로|으로)(?:[\s.,]|$)", s):
            nm = m.group(1).strip()
            if INVESTOR_SUFFIX.search(nm):
                found[nm] = True
        for m in re.finditer(r"([^,.]{2,40}?)(?:이|가)\s*(?:리드\s*투자자|리드|주도|단독으로?\s*투자)", s):
            for nm in _split_names(m.group(1).split("는 ")[-1].split("은 ")[-1]):
                if INVESTOR_SUFFIX.search(nm):
                    found[nm] = True
        for seg, trusted in segs:
            for nm in _split_names(seg):
                if company and norm_name(nm) == norm_name(company):
                    continue
                if INVESTOR_SUFFIX.search(nm) or (trusted and re.fullmatch(r"[A-Za-z0-9가-힣&.\- ]{2,20}", nm) and len(nm.split()) <= 3):
                    found.setdefault(nm, False)
    return list(found.items())


def investors_from_title(title: str) -> list[tuple[str, bool]]:
    """'A, B·C서 20억 유치' 꼴의 제목에서 투자자를 뽑는다."""
    t = _strip_title(title)
    m = re.search(r",\s*(.{2,60}?)(?:으로부터|로부터|에서|서)\s*(?:\d|투자|시리즈|프리|시드|후속|추가)", t)
    if not m:
        return []
    return [(n, False) for n in _split_names(m.group(1)) if INVESTOR_SUFFIX.search(n)]


def sentiment(text: str) -> str:
    p, n = len(POS.findall(text)), len(NEG.findall(text))
    return "positive" if p > n else "negative" if n > p else "neutral"


def classify(title: str) -> str:
    t = _strip_title(title)
    if FUND_KW.search(t) and FUND_ACT.search(t):
        return "fund"
    if INVEST_KW.search(t):
        return "funding"
    if MNA_KW.search(t):
        return "mna"
    return "general"


def extract(title: str, body: str = "") -> dict | None:
    """기사 1건 → 라운드 정보. 개별 라운드 기사가 아니면 None."""
    t = _strip_title(title)
    kind = classify(title)
    if kind == "general" or SKIP_KW.search(t):
        return None
    text = clean_text(body)
    if kind == "fund":
        m = re.search(QUOTES + r"([^'\"‘’“”]{3,50}(?:펀드|투자조합|조합)[^'\"‘’“”]{0,10})" + QUOTES, t)
        subj = t.split(",", 1)[0] if "," in t else None
        manager = _name_from_subject(subj) if subj and len(subj) <= 40 else None
        amount, amount_text = parse_amount(t)
        if amount is None and amount_text is None:
            amount, amount_text = parse_amount(text[:400])
        name = m.group(1).strip() if m else None
        if not name and not manager:
            return None
        return dict(kind="fund", fund_name=name or f"{manager} 펀드", manager=manager, amount=amount, amount_text=amount_text)
    if kind == "mna":
        m = re.search(r"^(.{2,30}?),\s*(.{2,40}?)\s*(?:를|을)?\s*(?:전격\s*)?(?:인수|품는다|품었다|흡수합병|합병)", t)
        if not m:
            return None
        acquirer = _name_from_subject(m.group(1))
        target = _name_from_subject(re.sub(r"\s*(?:지분\s*[\d.]+%?|경영권|사업부|전격)\s*$", "", m.group(2)))
        if not acquirer or not target or re.search(r"\d|추진|검토|무산|철회", m.group(2)) or INSTITUTION.search(target):
            return None
        amount, amount_text = parse_amount(t)
        return dict(kind="mna", company=target, acquirer=acquirer, round="M&A", amount=amount, amount_text=amount_text,
                    investors=[(acquirer, True)],
                    foreign=is_foreign(target, t, amount_text) or is_foreign(acquirer, t, amount_text)
                    or re.fullmatch(r"[A-Za-z0-9 .&\-]+", target) is not None or re.fullmatch(r"[A-Za-z0-9 .&\-]+", acquirer) is not None)
    company = company_from_title(title)
    if not company:
        return None
    (amount, amount_text), valuation = split_amounts(t)
    if amount is None and amount_text is None and text:
        m = re.search(r"[^.]{0,80}(?:투자\s*유치|투자유치|규모|유치)[^.]{0,80}", text[:600])
        if m:
            amount, amount_text = parse_amount(m.group(0))
    rnd = parse_round(t) or parse_round(text[:500])
    inv = dict(investors_from_title(title))
    for name, lead in investors_from_text(text, company):
        inv[name] = inv.get(name, False) or lead
    inv = {k: v for k, v in inv.items() if norm_name(k) != norm_name(company)}
    return dict(kind="investment", company=company, round=rnd, amount=amount, amount_text=amount_text, valuation=valuation,
                investors=list(inv.items()),
                foreign=is_foreign(company, t, amount_text) or bool(re.match(r"\s*\[(?:글로벌|해외|외신)", html.unescape(title or ""))))


CATEGORY_KW = [
    ("AI", r"\bAI\b|인공지능|LLM|생성형|머신러닝|딥러닝"), ("바이오·헬스케어", r"바이오|신약|헬스케어|의료|제약|진단|치료제|디지털\s*헬스"),
    ("핀테크", r"핀테크|결제|금융|보험|인슈어테크|자산관리|대출"), ("로봇", r"로봇|로보틱스|자율주행|드론"),
    ("반도체", r"반도체|팹리스|칩|NPU"), ("모빌리티", r"모빌리티|전기차|충전|물류|배터리|이차전지"),
    ("커머스", r"커머스|쇼핑|리테일|유통|마켓플레이스|브랜드"), ("콘텐츠·게임", r"콘텐츠|게임|웹툰|엔터|미디어|영상"),
    ("푸드", r"푸드|식품|외식|농업|애그테크|대체육"), ("에듀테크", r"에듀테크|교육|학습"),
    ("프롭테크", r"프롭테크|부동산|건설|공간"), ("클라우드·SaaS", r"SaaS|클라우드|B2B\s*솔루션|소프트웨어|보안|데이터"),
    ("에너지·환경", r"에너지|기후|탄소|환경|ESG|수소|태양광|원전"), ("우주·항공", r"우주|위성|항공|발사체"),
    ("뷰티·패션", r"뷰티|화장품|패션|의류"), ("블록체인", r"블록체인|가상자산|웹3|Web3|토큰"),
]


def guess_category(text: str) -> str | None:
    for label, pat in CATEGORY_KW:
        if re.search(pat, text, re.I):
            return label
    return None


FOREIGN_MARK = re.compile(r"\[(?:글로벌|해외|외신)[^\]]*\]|^(?:美|中|日|英|獨|佛|印|이스라엘|미국|중국|일본|영국|독일|프랑스|인도|싱가포르|대만|베트남)\s|"
                          r"(?:^|\s)(?:美|中|日)\s*(?:AI|스타트업|유니콘)|실리콘밸리|오픈AI|앤트로픽|OpenAI|Anthropic|xAI|"
                          r"(?:유럽|미국|중국|일본|이스라엘|프랑스|영국|독일|사우디|캐나다)\s*(?:\S+\s+){0,2}(?:스타트업|유니콘)|AGI\s*스타트업")
KOREAN_MARK = re.compile(r"국내|한국|K-|韓|토종|서울|판교|부산|대구|광주|대전|중기부|팁스|TIPS")


def is_foreign(company: str, title: str, amount_text: str | None) -> bool:
    """한국 스타트업 DB에 맞지 않는 해외 딜을 가려낸다. 확실한 표지가 없으면 국내로 본다."""
    if KOREAN_MARK.search(title):
        return False
    if FOREIGN_MARK.search(title):
        return True
    if amount_text and re.search(r"달러|유로|불|엔", amount_text):
        return True   # 국내 스타트업 투자는 대부분 원화로 보도된다
    latin = re.fullmatch(r"[A-Za-z0-9 .&\-]+", company or "") is not None
    return latin and not re.search(r"[가-힣]", title.split(",")[0])
