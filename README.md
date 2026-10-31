# 선린인터넷고 · 용산경찰서 재정공개

서울특별시교육청 열린 서울교육(선린인터넷고 학교회계)과 서울경찰청 용산경찰서(서장 업무추진비)가
공시한 재정 자료를 CSV로 보존하고, 웹 조회 페이지와 읽기 전용 REST API로 제공합니다.

원본은 각 기관의 공시입니다. 이 저장소의 값은 **사본**이며, 공시 사이트와 실시간으로 맞춰 두지 않습니다.

| 들어 있는 것 | 개수 |
| --- | ---: |
| 선린 세부사업 집행실적 (2012년 4분기 ~ 2026년 9월) | 12,908행 |
| 선린 수의계약 (2021년 12월 ~ 2026년 9월) | 3,037건 |
| 선린 업무추진비 (2012년 12월 ~ 2026년 8월) | 2,533건 |
| 용산경찰서장 업무추진비 (2016년 1월 ~ 2026년 9월) | 1,203건 |
| 결산 · 세입 · 세출 · 예산 회차 · 학교발전기금 요약표 | 6개 표 |

---

# 설치하기 (Ubuntu Server 처음 쓰는 분용)

**이 장만 위에서 아래로 따라 치면 켜집니다.** 명령어는 한 줄씩 복사해서 붙여 넣고 Enter를 누르세요.
`$` 기호는 입력하지 않습니다.

컴퓨터에 설치되는 건 Docker 하나뿐이고, 나머지는 전부 컨테이너 안에서 돕니다.

## 1단계 — 서버에 접속합니다

이미 서버 화면 앞에 있다면 이 단계는 넘어가세요. 다른 컴퓨터에서 접속한다면:

```bash
ssh 사용자이름@서버주소
```

## 2단계 — Docker를 설치합니다

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2 git
```

설치가 끝나면 Docker를 켜고, 서버가 재부팅돼도 자동으로 켜지게 해 둡니다.

```bash
sudo systemctl enable --now docker
```

제대로 깔렸는지 확인합니다. 버전 숫자가 나오면 성공입니다.

```bash
sudo docker --version
```

> `docker-compose-v2` 패키지가 없다는 오류가 나오면 Ubuntu 버전이 조금 오래된 것입니다.
> 그 줄만 빼고 `sudo apt install -y docker.io git` 로 다시 설치한 뒤,
> 아래 4단계에서 **방법 B**를 쓰세요.

## 3단계 — 이 저장소를 받아옵니다

```bash
cd ~
git clone https://github.com/holy0unjinx/hoesik.git
cd hoesik
```

이제부터 나오는 명령어는 모두 이 `~/hoesik` 폴더 안에서 실행합니다.
다른 곳에 가 있으면 `cd ~/hoesik` 를 먼저 치세요.

## 4단계 — 띄웁니다

**방법 A (권장)** — 2단계에서 `docker-compose-v2` 가 설치됐다면:

```bash
sudo docker compose up -d --build
```

**방법 B** — compose가 없다면:

```bash
sudo docker build -t sunrin-web .
sudo docker run -d --name sunrin-web --restart unless-stopped \
  -p 0.0.0.0:8890:80 \
  -v "$(pwd)/site/data:/app/site/data:ro" \
  sunrin-web
```

처음 실행하면 이미지를 만드느라 2~5분쯤 걸립니다. 기다리세요.

## 5단계 — 잘 떴는지 확인합니다

```bash
curl http://127.0.0.1:8890/api/health
```

아래처럼 행 수가 적힌 JSON이 나오면 성공입니다.

```json
{"status":"ok","tables":{"expense":2533,"contracts":3037,"execution":12908,"ys_expense":1203}}
```

아무것도 안 나오거나 `Connection refused` 가 나오면 [문제가 생겼을 때](#문제가-생겼을-때)로 가세요.

## 6단계 — 바깥에서 접속할 수 있게 방화벽을 엽니다

```bash
sudo ufw allow 8890/tcp
```

> `ufw: command not found` 가 나오면 방화벽이 안 깔린 것이고, 그럼 이미 열려 있습니다. 넘어가세요.
> 클라우드(AWS·오라클·네이버클라우드 등)를 쓴다면 그 회사 콘솔의 **보안 그룹**에서도
> 8890 포트를 따로 열어 줘야 합니다.

## 7단계 — 브라우저로 들어갑니다

서버 주소를 모르면 이걸로 확인합니다.

```bash
curl -s ifconfig.me; echo
```

그 주소를 브라우저에 칩니다.

```
http://서버주소:8890/
```

| 주소 | 보이는 것 |
| --- | --- |
| `http://서버주소:8890/` | 선린인터넷고 학교회계 조회 |
| `http://서버주소:8890/police.html` | 용산경찰서장 업무추진비 조회 |
| `http://서버주소:8890/api/docs` | API 설명서 (Swagger UI) |

**여기까지가 설치 끝입니다.**

> 로그인이 없습니다. 8890 포트를 열면 주소를 아는 누구나 볼 수 있습니다.
> 공시된 자료만 들어 있으니 공개해도 되지만, 비공개로 두고 싶으면 6단계를 건너뛰고
> SSH 터널(`ssh -L 8890:127.0.0.1:8890 사용자이름@서버주소`)로 혼자만 보세요.

---

# 평소에 쓰는 명령어

모두 `~/hoesik` 폴더에서 실행합니다.

| 하고 싶은 것 | 명령어 |
| --- | --- |
| 지금 돌고 있는지 보기 | `sudo docker ps` |
| 멈추기 | `sudo docker stop sunrin-web` |
| 다시 켜기 | `sudo docker start sunrin-web` |
| 기록(로그) 보기 | `sudo docker logs --tail 50 sunrin-web` |
| 새 버전 받아서 다시 띄우기 | `git pull && sudo docker compose up -d --build` |
| 완전히 지우기 | `sudo docker rm -f sunrin-web` |

데이터 CSV만 바꿨을 때는 다시 빌드할 필요 없이 재시작만 하면 됩니다.
API는 켜질 때 CSV를 메모리에 올리기 때문에, 재시작하지 않으면 바뀐 값이 안 보입니다.

```bash
sudo docker restart sunrin-web
```

---

# 자동 갱신 (cron)

새 자료는 학교가 **매월 초**, 경찰서가 **매월 중순**에 공시합니다.
매달 사람이 받아 올 필요 없이, cron이 알아서 받아 커밋하고 GitHub에 올려 줍니다.

**과거 자료를 다시 긁지 않습니다.** CSV에 아직 없는 달만 확인하고, 그 달만 받아옵니다.
보통 한 번에 요청 10~20번, 1~2분이면 끝납니다. 받아올 게 없으면 아무 파일도 건드리지 않고 그냥 끝냅니다.

## 1단계 — 수집에 필요한 것을 설치합니다

경찰서 자료는 PDF에서 표를 뽑아내야 해서 라이브러리가 하나 더 필요합니다.

```bash
sudo apt install -y python3-pip
pip3 install --user -r requirements-update.txt
```

## 2단계 — 커밋에 쓸 이름을 정합니다

```bash
cd ~/hoesik
git config user.name "holy0unjinx"
git config user.email "holy_unjinx@naver.com"
```

## 3단계 — GitHub 토큰을 넣어 둡니다

cron이 사람 없이 `git push` 를 하려면 토큰이 서버에 있어야 합니다.

GitHub에서 **Settings → Developer settings → Personal access tokens → Tokens (classic) →
Generate new token** 으로 들어가, `repo` 권한만 체크해서 만듭니다. `ghp_` 로 시작하는 문자열이 나옵니다.

그 토큰을 아래 파일에 적습니다. 저장소 밖에 두고, 본인만 읽을 수 있게 권한을 막습니다.

```bash
mkdir -p ~/.config/hoesik
chmod 700 ~/.config/hoesik
nano ~/.config/hoesik/env
```

편집기가 열리면 아래 내용을 적습니다. `ghp_여기에붙여넣기` 자리에 토큰을 넣으세요.

```sh
GITHUB_TOKEN=ghp_여기에붙여넣기
GIT_AUTHOR_NAME=holy0unjinx
GIT_AUTHOR_EMAIL=holy_unjinx@naver.com
RESTART_CONTAINER=sunrin-web
```

`Ctrl+O` → `Enter` 로 저장하고 `Ctrl+X` 로 나옵니다. 그리고 권한을 막습니다.

```bash
chmod 600 ~/.config/hoesik/env
```

> 이 파일은 저장소 밖(`~/.config`)에 있고 `.gitignore` 에도 걸려 있어서 GitHub에 올라가지 않습니다.
> push를 자동으로 하고 싶지 않으면 `GITHUB_TOKEN` 줄을 빼세요. 그럼 커밋까지만 하고 멈춥니다.

## 4단계 — 한 번 직접 돌려 봅니다

cron에 넣기 전에, 받아만 보고 파일은 건드리지 않는 모드로 확인합니다.

```bash
cd ~/hoesik
python3 scripts/update.py --dry-run
```

사이트가 느려서 1~3분쯤 걸립니다. `새 행 0개` 라고 나오면 이미 최신이라는 뜻이고, 정상입니다.

이제 진짜로 한 번 돌립니다.

```bash
bash scripts/cron_update.sh
cat ~/.local/state/hoesik/update.log
```

## 5단계 — cron에 등록합니다

```bash
crontab -e
```

편집기가 열리면(처음이면 `1` 을 눌러 nano를 고릅니다) 맨 아래에 이 두 줄을 붙여 넣습니다.

```cron
HOME=/home/사용자이름
17 3 8,22 * * cd $HOME/hoesik && bash scripts/cron_update.sh
```

`사용자이름` 은 본인 계정으로 바꾸세요. `whoami` 로 확인할 수 있습니다.
매월 **8일과 22일 새벽 3시 17분**에 한 번씩 돌아갑니다. 학교 공시(월초)와 경찰서 공시(월중순)를
각각 지나간 뒤입니다.

저장하고 나온 뒤 등록을 확인합니다.

```bash
crontab -l
```

## 잘 돌고 있는지 보기

```bash
tail -30 ~/.local/state/hoesik/update.log
```

## 직접 돌리는 명령어

```bash
python3 scripts/update.py              # 학교 + 경찰서
python3 scripts/update.py --school     # 학교만
python3 scripts/update.py --police     # 경찰서만
python3 scripts/update.py --dry-run    # 받아만 보고 파일은 그대로
```

## 수집 스크립트가 하는 일

| 파일 | 역할 |
| --- | --- |
| `scripts/update.py` | 진입점. 없는 달만 골라 받고, 마스킹한 뒤 CSV를 다시 씀 |
| `scripts/update_school.py` | 열린 서울교육 목록 첫 장 → 새 기준월만 상세 조회 |
| `scripts/update_police.py` | 경찰서 게시판 첫 장 → 새 글의 PDF만 받아 표 파싱 |
| `scripts/anonymize.py` | 개인 이름 마스킹 (아래 [개인정보](#개인정보) 참고) |
| `scripts/sources.py` | HTTP 호출·재시도·HTML 표 파싱 |
| `scripts/cron_update.sh` | cron 진입점. 수집 → 커밋 → push → 컨테이너 재시작 |

원 서버는 요청당 10~20초가 걸리고 간헐적으로 빈 응답을 돌려주므로, 모든 호출에 재시도가 들어 있습니다.
동시 요청은 쓰지 않습니다.

---

# 문제가 생겼을 때

**`curl: (7) Failed to connect` 또는 화면이 안 열린다**

컨테이너가 돌고 있는지 봅니다.

```bash
sudo docker ps -a
```

`sunrin-web` 이 `Up` 이 아니면 로그에 이유가 적혀 있습니다.

```bash
sudo docker logs --tail 50 sunrin-web
```

**`permission denied while trying to connect to the Docker daemon`**

`sudo` 를 빼먹은 것입니다. 매번 치기 싫으면 본인 계정을 docker 그룹에 넣고 다시 로그인하세요.

```bash
sudo usermod -aG docker $USER
```

**`port is already allocated` (8890을 다른 게 쓰고 있다)**

쓰고 있는 것을 찾습니다.

```bash
sudo ss -tlnp | grep 8890
```

포트를 바꾸려면 `docker-compose.yml` 의 `"8890:80"` 에서 앞 숫자만 고치고 다시 띄웁니다.

**서버 안에서는 열리는데 바깥에서 안 열린다**

6단계의 방화벽, 그리고 클라우드 콘솔의 보안 그룹을 확인하세요.

**cron이 안 돈다**

cron은 로그인 셸이 아니어서 `PATH` 가 좁습니다. `crontab -e` 에 `HOME=/home/사용자이름` 줄이
있는지 확인하고, 로그를 보세요.

```bash
tail -30 ~/.local/state/hoesik/update.log
grep CRON /var/log/syslog | tail -20
```

**`pdfplumber` 가 없다는 오류**

경찰서 PDF 파싱에 필요합니다. 자동 갱신 1단계를 다시 하세요.

```bash
pip3 install --user -r requirements-update.txt
```

**`data/ 에 커밋되지 않은 변경이 있다` 로 멈춘다**

사람이 손으로 고친 CSV를 덮어쓰지 않으려고 일부러 멈춥니다. 정리한 뒤 다시 돌리세요.

```bash
cd ~/hoesik && git status
```

---

# 구조

```
api.py                 FastAPI 읽기 전용 API (컨테이너 안에서 127.0.0.1:8000)
site/                  정적 페이지와 CSV
  index.html             선린 학교회계 조회
  police.html            용산경찰서장 업무추진비 조회
  data/*.csv             페이지와 API가 읽는 원본
data/*.csv             수집 원본 (id 열 없는 그대로의 꼴)
scripts/               월 1회 증분 수집
docker/                nginx 설정과 컨테이너 진입점
docs/plan.md           수집 계획과 알려진 구멍
```

컨테이너 하나 안에서 nginx가 80 포트를 열고, API는 루프백 `127.0.0.1:8000` 에만 붙습니다.
바깥에서 API에 직접 붙을 수는 없고, nginx가 `/api/` 를 넘겨 줍니다.

`data/` 와 `site/data/` 는 같은 자료입니다. `site/data/` 쪽에 `id` 열(`기준월-번호`)이 붙어 있고,
`data/` 쪽은 공시 화면 그대로의 열 구성입니다. 둘 다 올려 둡니다.

## API

읽기 전용 GET만 있습니다. 기간은 학교는 `YYYYMM`, 경찰서는 `YYYY-MM` 입니다.

- `GET /api/health` — 적재된 표 행 수
- `GET /api/datasets` — 출처와 알려진 구멍 목록
- `GET /api/school/settlement?year=2025`
- `GET /api/school/revenue`, `/spending`, `/budget-rounds`, `/budget2026`, `/fund`
- `GET /api/school/expense?from=202401&to=202412&q=협의회&kind=meal`
- `GET /api/school/expense/venues?merge=true`
- `GET /api/school/contracts`, `/contracts/vendors`
- `GET /api/school/execution?period=202609`
- `GET /api/police/expense?from=2024-01&to=2024-12`
- `GET /api/police/expense/venues`, `/police/expense/months`
- `GET /api/tables/{name}` — CSV 원본을 JSON으로. `name` 은 `/api/datasets` 참고

전체 목록과 각 항목 설명은 `/api/docs` 에 있습니다.

## 검사

```bash
python3 test_api.py
```

소켓을 열지 않고 ASGI를 직접 호출합니다. Docker 없이도 됩니다.

---

# 데이터

## 출처

| 대상 | 출처 |
| --- | --- |
| 선린인터넷고 학교회계 | 서울특별시교육청 열린 서울교육 (`open.sen.go.kr`, schoolCode 7010536) |
| 용산경찰서장 업무추진비 | 서울경찰청 용산경찰서 사전정보공표 (`smpa.go.kr`, ps_opendata_id 113) |

두 기관 모두 공식 Open API가 없습니다. 열린 서울교육은 JS로 그리는 HTML만, 용산경찰서는 PDF 첨부만
줍니다. 그래서 이 저장소의 값은 사본이고, 갱신은 수집 스크립트를 다시 돌려야 합니다.

## 알려진 구멍

기계로 읽은 값이라 원본과 어긋나는 구간이 있습니다. 숨기지 않고 페이지와 `/api/datasets` 에
그대로 둡니다.

- 선린 수의계약: 목록에는 2012년 12월부터 있으나, 상세는 2021년 12월 이후만 서버에 남아 있음
- 선린 업무추진비 2026년 9월, 집행실적 2014년 1분기: 공시 공백
- 용산경찰서 2015년 12월 이전 게시글 38건: 본문·첨부에 내역 자체가 없음
- 용산경찰서 2016년 2월: 첨부가 스캔 이미지라 텍스트 추출 불가
- 용산경찰서 2016-12, 2017-03, 2017-04, 2023-04, 2024-10: 월 합계가 PDF 명시 합계와 어긋남
  (표가 여러 줄로 쪼개진 행을 놓친 것으로 보임)

## 개인정보

공시 원본에는 경조사비 수령인, 수당 지급 대상 같은 **개인 실명**이 그대로 들어 있습니다.
이 저장소는 공개되어 있으므로, 개인에게 귀속되는 이름만 가리고 업체명·기관명은 원본대로 둡니다.

| 대상 | 처리 |
| --- | --- |
| 업무추진비 `집행장소` 가 개인 수령인인 경우 (74명) | `개인` |
| `승인자` 실명 | 가운데를 `O` 로 (`김동환` → `김O환`) |
| `참석자` 의 `직위 실명` | 가운데를 `O` 로 (`교사 이효진 외 4명` → `교사 이O진 외 4명`) |
| 상호에 사업주 실명이 들어간 경우 | 상호는 남기고 이름만 (`영플라워(이혜영)` → `영플라워(이O영)`) |
| 업체명 · 기관명 · 직위 · 금액 · 날짜 · 집행목적 | 원본 그대로 |

마스킹 방식은 공시 원본이 이미 쓰고 있는 관례(`박O은`, `교사 하ㅇㅇ`)를 따릅니다.
규칙은 `scripts/anonymize.py` 에 있고, cron이 새로 받아온 행에도 같은 규칙이 적용되므로
갱신해도 마스킹이 유지됩니다.

금액·날짜·집행목적·업체명은 손대지 않았으므로, 예산 감시 용도의 분석에는 영향이 없습니다.

---

# 라이선스와 출처 표시

데이터는 두 공공기관의 공시 자료이며, 이 저장소는 그 사본과 조회 도구입니다.
값을 인용할 때는 원 공시를 함께 확인하시기 바랍니다. 기계 판독 과정의 오류가 있을 수 있습니다.
