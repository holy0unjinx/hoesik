"""개인 이름 마스킹.

공시 원본에는 경조사비 수령인·수당 지급 대상 같은 개인 실명이 그대로 들어 있다.
저장소는 public 이므로 개인에게 귀속되는 이름만 가리고, 업체명·기관명은 원본대로 둔다.

마스킹 방식은 공시 원본이 이미 쓰고 있는 관례(`박O은`, `교사 하ㅇㅇ`)를 따른다.

- 집행장소가 개인 수령인이면 `개인`
- 승인자·참석자의 실명은 가운데 글자를 `O`로 (`김동환` → `김O환`)
- 업체명·기관명·직위는 그대로

`update_*.py` 가 새로 받아온 행에도 같은 규칙을 적용하므로, cron 으로 갱신해도
마스킹이 유지된다.
"""

import re

# 흔한 한국 성씨. 개인 이름 판별의 1차 조건으로만 쓴다.
SURNAMES = frozenset(
    "김이박최정강조윤장임한오서신권황안송류유홍전고문손양배백허남심노하곽성차주우구"
    "나민진지엄채원천방공현함변염여추도소석선설마길연위표명기반왕금옥육인맹제모탁국어편용"
) | frozenset({"사공", "남궁", "황보", "제갈", "선우", "서문", "독고"})

# 이름처럼 보이지만 업체·장소인 경우를 걸러내는 토큰.
_BUSINESS = re.compile(
    r"원예|플라워|꽃|참치|횟집|식당|갈비|분식|카페|커피|마트|주식|유한|회사|상회|문구|서점"
    r"|제과|정육|농원|농장|조합|기업|산업|스토어|백화|호텔|회관|가든|하우스|푸드|치킨|피자"
    r"|국밥|냉면|칼국|보쌈|족발|초밥|스시|반점|도시락|제빵|베이커|면옥|기획|철물|창고|약국"
    r"|문고|서림|상점|편의점|주유|세탁|인쇄|택시|여행|관광|병원|의원|한의|치과|약방"
)

# 휴리스틱이 개인으로 잘못 잡는 업체명. 데이터를 눈으로 확인해 고정한 예외.
BUSINESS_EXCEPTIONS = frozenset(
    {"강계면옥", "고려기획", "보물창고", "원진철물", "진영각", "송죽원예", "이건참치", "킴준플라워", "더쉐프"}
)

# 개인에게 돈이 나간 집행목적. 이 목적이면 집행장소는 사람 이름으로 본다.
# `조화`·`부조`처럼 짧은 토큰은 `재구조화` 같은 낱말에 걸리므로 쓰지 않는다.
_PERSONAL_PAYMENT = re.compile(
    r"경조|조의금|축의금|부조금|화환|근조|부의금|위로금|격려금|상금|수당|강사료|강사비|사례금|심사료|원고료"
)

# 집행목적만으로는 개인 지급인지 알 수 없지만, 행을 직접 읽어 개인으로 확인한 이름.
# (업무협의회비·여비를 개인 계좌로 받은 경우 등 — 식당 이름과 구분이 안 된다.)
PERSON_EXCEPTIONS = frozenset({"박춘희", "이병일", "이철호", "정세일", "한일환"})

# 상호에 사업주 실명이 들어간 경우. 휴리스틱이 지점명(`공덕점`)과 구분하지 못해
# 데이터를 확인해 직접 적는다. 상호는 남기고 사람 이름만 가린다.
OWNER_IN_BUSINESS_NAME = {
    "영플라워(이혜영)": "영플라워(이O영)",
    "지올팍(박지원)": "지올팍(박O원)",
}

# 참석자 칸의 `직위 이름` 패턴.
_TITLE_NAME = re.compile(
    r"(교장|교감|교사|행정실장|실장|주무관|부장|교육공무직|직원|강사|서장|과장|계장|팀장|소장)"
    r"(\s*)([가-힣]{2,4})(?=\s|$|,|·|ㆍ|외|등|\))"
)

# 직위 뒤에 붙지만 이름이 아닌 말.
_NOT_A_NAME = frozenset(
    {"외", "등", "및", "선생", "선생님", "직원", "전원", "일동", "오찬", "만찬", "간담회", "협의회", "격려", "현장", "업무"}
)

PERSON_PLACEHOLDER = "개인"


def _is_person_name(value: str) -> bool:
    """2~4글자 한글이고 성씨로 시작하며 업체 토큰이 없으면 사람 이름으로 본다."""
    if not value or value in BUSINESS_EXCEPTIONS:
        return False
    if not re.fullmatch(r"[가-힣Oㅇ○]{2,4}", value):
        return False
    if _BUSINESS.search(value):
        return False
    return value[:2] in SURNAMES or value[0] in SURNAMES


def mask_name(value: str) -> str:
    """가운데 글자를 O 로 바꾼다. 공시 원본이 쓰는 관례와 같다."""
    if not value:
        return value
    name = value.strip()
    # 직위·역할은 개인 식별 정보가 아니다.
    if name in ("관리자", "교장", "교감", "행정실장", "-") or not re.fullmatch(r"[가-힣Oㅇ○]{2,4}", name):
        return value
    if len(name) == 2:
        return name[0] + "O"
    return name[0] + "O" * (len(name) - 2) + name[-1]


def is_person_payee(venue: str, purpose: str) -> bool:
    """이 행의 집행장소가 개인 수령인인지. 개인 지급 목적일 때만 참."""
    if not venue:
        return False
    name = venue.strip()
    if not _is_person_name(name):
        return False
    if name in PERSON_EXCEPTIONS:
        return True
    # 이미 원본이 `박O은` 처럼 가려 둔 값은 사람 이름이 확실하다.
    return bool(_PERSONAL_PAYMENT.search(purpose or "")) or bool(re.search(r"[Oㅇ○]", name))


def learn_person_venues(rows: list) -> set:
    """표 전체를 훑어 개인 수령인으로 쓰인 집행장소를 모은다.

    같은 이름이 개인 지급이 아닌 행(예: 직책급 업무추진비)에도 나오므로,
    한 번이라도 개인 수령인이면 그 이름은 표 전체에서 가려야 한다.
    """
    return {
        (r.get("집행장소") or "").strip()
        for r in rows
        if is_person_payee(r.get("집행장소") or "", r.get("집행목적") or "")
    } - {""}


def mask_venue(venue: str, purpose: str, known_persons=frozenset()) -> str:
    """집행장소가 개인 수령인이면 `개인` 으로, 상호 속 사업주 실명이면 그 부분만 가린다."""
    if not venue:
        return venue
    name = venue.strip()
    if name in OWNER_IN_BUSINESS_NAME:
        return OWNER_IN_BUSINESS_NAME[name]
    if name in known_persons or is_person_payee(name, purpose):
        return PERSON_PLACEHOLDER
    return venue


def mask_attendees(value: str) -> str:
    """`교사 이효진 외 4명` → `교사 이OO진 외 4명` 꼴로 직위 뒤 실명만 가린다."""
    if not value:
        return value

    def repl(m):
        title, gap, name = m.group(1), m.group(2), m.group(3)
        if name in _NOT_A_NAME or not _is_person_name(name):
            return m.group(0)
        return title + gap + mask_name(name)

    return _TITLE_NAME.sub(repl, value)


def mask_expense_row(row: dict, known_persons=frozenset()) -> dict:
    """업무추진비 한 행을 마스킹한다. 원본 dict 를 바꾸지 않고 새 dict 를 돌려준다."""
    out = dict(row)
    purpose = out.get("집행목적") or ""
    if "집행장소" in out:
        out["집행장소"] = mask_venue(out["집행장소"], purpose, known_persons)
    if "참석자" in out:
        out["참석자"] = mask_attendees(out["참석자"])
    if "승인자" in out:
        out["승인자"] = mask_name(out["승인자"] or "")
    return out


def mask_approver_row(row: dict, known_persons=frozenset()) -> dict:
    """승인자만 있는 표(집행실적·수의계약)용. 상호 속 사업주 실명도 함께 가린다."""
    out = dict(row)
    if "승인자" in out:
        out["승인자"] = mask_name(out["승인자"] or "")
    vendor = (out.get("계약업체명") or "").strip()
    if vendor in OWNER_IN_BUSINESS_NAME:
        out["계약업체명"] = OWNER_IN_BUSINESS_NAME[vendor]
    return out


# 업무추진비 성격의 표는 집행장소까지, 나머지는 승인자만 가린다.
MASKERS = {
    "expense": mask_expense_row,
    "business_expense": mask_expense_row,
    "execution": mask_approver_row,
    "contracts": mask_approver_row,
}


def mask_table(name: str, rows: list, known_persons=frozenset()) -> tuple:
    """표 이름에 맞는 마스킹을 적용한다.

    `(마스킹된 행, 이 표에서 새로 찾은 개인 이름)` 을 돌려준다.
    규칙이 없는 표는 행을 그대로 돌려준다.
    """
    masker = MASKERS.get(name)
    if masker is None:
        return rows, set()
    persons = set(known_persons)
    if masker is mask_expense_row:
        persons |= learn_person_venues(rows)
    return [masker(r, persons) for r in rows], persons - set(known_persons)
