"""공시 사이트 호출과 HTML 표 파싱.

두 원 서버는 모두 응답이 느리고(요청당 10~20초) 간헐적으로 빈 본문을 돌려준다.
그래서 모든 호출은 재시도를 전제로 하고, 동시 요청은 쓰지 않는다. 증분 갱신은
한 달에 몇 번만 호출하므로 직렬로 충분하다.
"""

import html
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) sunrin-hoesik/1.0"

# 두 기관 모두 중간 인증서 체인이 불완전한 때가 있어 검증을 끈다.
# 받아오는 값은 공개 공시 자료이고 쓰기 요청은 하지 않는다.
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


class FetchError(RuntimeError):
    pass


def fetch(url, data=None, referer=None, tries=4, timeout=90, delay=3.0):
    """URL 하나를 받아온다. 빈 응답·타임아웃은 재시도한다."""
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data, encoding="utf-8").encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    last = None
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
                raw = resp.read()
            if raw:
                return raw
            last = "빈 응답"
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            last = f"{type(exc).__name__}: {exc}"
        if attempt < tries:
            time.sleep(delay * attempt)
    raise FetchError(f"{url} 실패 ({tries}회): {last}")


def fetch_text(url, **kw):
    return fetch(url, **kw).decode("utf-8", "replace")


def _cell(fragment):
    """td/th 안쪽을 평문으로. 태그를 공백으로 바꾼 뒤 공백을 정리한다."""
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def rows_of(markup, which=-1):
    """마지막 tbody 의 행들을 셀 리스트로. 빈 행은 버린다."""
    bodies = re.findall(r"<tbody.*?</tbody>", markup, re.S)
    if not bodies:
        return []
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", bodies[which], re.S):
        cells = [_cell(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if any(cells):
            out.append(cells)
    return out


def links_of(markup, which=0):
    """tbody 각 행의 href/onclick 값을 모은다."""
    bodies = re.findall(r"<tbody.*?</tbody>", markup, re.S)
    if not bodies:
        return []
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", bodies[which], re.S):
        found = re.findall(r"(?:href|onclick)\s*=\s*\"([^\"]+)\"", tr)
        out.append([html.unescape(x) for x in found])
    return out
