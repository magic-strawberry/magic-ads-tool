# 마법의딸기 AI 광고 대시보드 — 예시본 구조 반영 (탭 구성)
# CSV/XLSX 업로드 → 기간/캠페인 필터 → 대시보드/캠페인/키워드/제품/마진 계산기
# 배포: Streamlit Cloud (requirements.txt에 openpyxl 포함)

import numpy as np
import pandas as pd
import streamlit as st

# ===== 날짜 파서 (여러 포맷 + 엑셀 직렬숫자 대응) =====
def parse_date_series(s: pd.Series) -> pd.Series:
    import pandas as pd
    s0 = s.copy()

    # 0) 문자열로 통일 + 공백 제거 + ".0" 제거(엑셀로 인한 정수->실수 흔적)
    s_str = s0.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)

    # 결과 컨테이너: 전부 NaT로 시작
    out = pd.Series(pd.NaT, index=s_str.index, dtype="datetime64[ns]")

    # 1) 정확히 8자리 숫자(YYYYMMDD) → 우선순위 가장 높음
    m8 = s_str.str.match(r"^\d{8}$")
    if m8.any():
        out.loc[m8] = pd.to_datetime(s_str.loc[m8], format="%Y%m%d", errors="coerce")

    # 2) 점/슬래시 포맷
    m_dot = out.isna() & s_str.str.match(r"^\d{4}\.\d{2}\.\d{2}$")
    if m_dot.any():
        out.loc[m_dot] = pd.to_datetime(s_str.loc[m_dot], format="%Y.%m.%d", errors="coerce")

    m_slash = out.isna() & s_str.str.match(r"^\d{4}/\d{2}/\d{2}$")
    if m_slash.any():
        out.loc[m_slash] = pd.to_datetime(s_str.loc[m_slash], format="%Y/%m/%d", errors="coerce")

    # 3) 일반 자동 파싱 (남은 것)
    m_auto = out.isna()
    if m_auto.any():
        out.loc[m_auto] = pd.to_datetime(s_str.loc[m_auto], errors="coerce")

    # 4) 엑셀 직렬숫자(날짜) 처리: 순수 숫자이지만 8자리가 아닌 경우
    #    (예: 45432 → 2024-05-24)
    m_excel = out.isna() & s_str.str.match(r"^\d+$")
    if m_excel.any():
        out.loc[m_excel] = pd.to_datetime(pd.to_numeric(s_str.loc[m_excel], errors="coerce"),
                                          unit="d", origin="1899-12-30", errors="coerce")

    return out.dt.date

st.set_page_config(page_title="마법의딸기 AI 광고 대시보드", layout="wide")
st.markdown(
    """
    <style>
    .small-note {color:#6b7280;font-size:0.9rem;}
    .tight {margin-top:-0.5rem}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🍓 마법의딸기 — AI 광고 대시보드")
st.caption("CSV/XLSX 업로드 → 기간 선택 → 대시보드/캠페인/키워드/제품별 분석 → 마진 계산기")

# ===== 스키마 정의 =====
REQUIRED_BASE_COLS = [
    "date", "campaign", "ad_group", "keyword", "product_id", "product_name",
    "impressions", "clicks", "spend", "orders", "revenue"
]
OPTIONAL_COLS = ["channel", "device", "placement", "match_type"]
METRIC_COLS = ["impressions", "clicks", "spend", "orders", "revenue"]

# ===== 유틸 =====
def coerce_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            try:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
            except Exception:
                # 변환 실패 시 그냥 넘어가기
                pass
        else:
            # 컬럼이 없으면 0으로 채운 임시 컬럼 생성
            df[c] = 0
    return df

def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ctr"] = np.where(df["impressions"]>0, df["clicks"]/df["impressions"], 0.0)
    df["cpc"] = np.where(df["clicks"]>0, df["spend"]/df["clicks"], 0.0)
    df["cvr"] = np.where(df["clicks"]>0, df["orders"]/df["clicks"], 0.0)
    df["roas"] = np.where(df["spend"]>0, df["revenue"]/df["spend"], 0.0)          # 비율(배수)
    df["acos"] = np.where(df["revenue"]>0, df["spend"]/df["revenue"], 0.0)        # 비율(배수)
    return df

def parse_date_series(s: pd.Series) -> pd.Series:
    """쿠팡 리포트의 다양한 날짜 포맷을 안전하게 변환."""
    # 1차: ISO/일반 자동
    out = pd.to_datetime(s, errors="coerce")
    # 2차: 흔한 점 표기(YYYY.MM.DD)
    mask = out.isna()
    if mask.any():
        out.loc[mask] = pd.to_datetime(s[mask], format="%Y.%m.%d", errors="coerce")
    # 3차: 슬래시(YYYY/MM/DD)
    mask = out.isna()
    if mask.any():
        out.loc[mask] = pd.to_datetime(s[mask], format="%Y/%m/%d", errors="coerce")
    # 드롭 NaT
    return out.dt.date

# ===== 사이드바: 업로드 & 안내 =====
with st.sidebar:
    st.header("1) 파일 업로드")
    f = st.file_uploader("쿠팡 광고 리포트 파일 업로드 (CSV/XLSX)", type=["csv","xlsx","xls"])
    st.markdown(
        """
        **필수 컬럼**  
        `date, campaign, ad_group, keyword, product_id, product_name, impressions, clicks, spend, orders, revenue`  
        <span class='small-note'>*자동 매핑 실패 시 아래 '열 매핑'에서 연결</span>
        """,
        unsafe_allow_html=True,
    )

if f is None:
    st.info("왼쪽 사이드바에서 CSV/XLSX 파일을 업로드하세요. (쿠팡 원본 가능)")
    st.stop()

# ===== 파일 로딩: 엑셀/CSV 자동 처리 =====
name = f.name.lower()
raw = None
if name.endswith(("xlsx", "xls")):
    raw = pd.read_excel(f)
else:
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            f.seek(0)
            raw = pd.read_csv(f, encoding=enc)
            break
        except Exception:
            pass
if raw is None:
    st.error("파일을 읽지 못했습니다. CSV는 UTF-8 또는 CP949로 저장해 주세요.")
    st.stop()

# ===== 자동 매핑 (쿠팡 한글 → 표준 컬럼) =====
auto_alias = {
    # 날짜/기본
    "날짜": "date", "일자": "date",
    "캠페인명": "campaign", "캠페인": "campaign",
    "광고그룹": "ad_group", "광고그룹명": "ad_group",
    "키워드": "keyword", "검색어": "keyword",
    # 상품/옵션
    "광고집행 상품명": "product_name", "광고전환매출발생 상품명": "product_name",
    "광고집행 옵션id": "product_id", "광고전환매출발생 옵션id": "product_id",
    # 지표
    "노출수": "impressions", "노출": "impressions",
    "클릭수": "clicks", "클릭": "clicks",
    "광고비": "spend", "광고비용": "spend",
    "총 판매수량(14일)": "orders", "총 주문수(14일)": "orders",
    "총 전환매출액(14일)": "revenue", "전환매출액": "revenue",
    # 선택
    "디바이스": "device",
    "광고 노출 지면": "placement", "노출매체": "placement", "매체": "placement",
    "매칭방식": "match_type",
}
for orig in list(raw.columns):
    norm = orig.strip().lower().replace(" ", "")
    for alias, target in auto_alias.items():
        if norm == alias.strip().lower().replace(" ", ""):
            raw = raw.rename(columns={orig: target})

# ===== 열 매핑(필요 시) =====
raw_columns = list(raw.columns)
missing = [c for c in REQUIRED_BASE_COLS if c not in raw.columns]
if missing:
    with st.expander("열 매핑(필요 시)"):
        st.write("업로드한 파일의 열을 표준 스키마에 연결하세요.")
        mapped = {}
        for col in missing + OPTIONAL_COLS:
            mapped[col] = st.selectbox(
                f"{col} ← 업로드 열 선택",
                [None] + raw_columns, index=0
            )
        manual_map = {v: k for k, v in mapped.items() if v}
        if manual_map:
            raw = raw.rename(columns=manual_map)

# 중복 컬럼명 제거(첫 번째 것만 유지)
raw = raw.loc[:, ~raw.columns.duplicated()]

# ===== 정규화/파생 =====
df = raw.copy()
# 날짜 변환(1970년 방지: 다양한 포맷 허용 + 실패행 제거)
if "date" in df.columns:
    # 강제 문자열 변환 후 파서 적용 (YYYYMMDD → 정상 인식)
    df["date"] = parse_date_series(df["date"].astype(str))
    df = df.dropna(subset=["date"])
# 숫자화
df = coerce_numeric(df, METRIC_COLS)
# 파생지표
df = add_metrics(df)

# ===== 필터 =====
with st.sidebar:
    st.header("2) 필터")
    # 날짜 범위
    if "date" in df.columns and not df["date"].dropna().empty:
        min_d, max_d = df["date"].min(), df["date"].max()
        start, end = st.date_input("기간 선택", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    else:
        start, end = None, None
    # 캠페인
    campaigns = sorted(df["campaign"].dropna().unique().tolist()) if "campaign" in df.columns else []
    sel_campaigns = st.multiselect("캠페인 선택(미선택=전체)", campaigns)

# 필터 적용
view = df.copy()
if start and end:
    view = view[(view["date"] >= start) & (view["date"] <= end)]
if sel_campaigns:
    view = view[view["campaign"].isin(sel_campaigns)]

if view.empty:
    st.warning("선택한 조건에 데이터가 없습니다. (기간/캠페인 필터를 조정해보세요)")
    st.stop()


# --- 좌측 보기 선택 (PPT 좌측 메뉴 느낌) ---
with st.sidebar:
    st.header("3) 보기 선택")
view_name = st.radio(
        "분석 화면",
        ["대시보드", "캠페인 분석", "키워드 분석", "제품 분석", "마진 계산기"]
    )

    # --- 대시보드 계산 설정(수수료 %) ---
    st.header("대시보드 계산 설정")
    fee_pct_input = st.number_input("수수료(%)", value=12.0, step=0.5) / 100.0

# === 대시보드 ===
if view_name == "대시보드":
    st.subheader("📊 요약 KPI")

    spend  = float(view["spend"].sum())
    rev    = float(view["revenue"].sum())
    clicks = int(view["clicks"].sum())
    impr   = int(view["impressions"].sum())

    roas   = (rev/spend) if spend>0 else 0.0
    acos   = (spend/rev) if rev>0 else 0.0

    net_sales = rev - spend
    est_fee   = rev * fee_pct_input
    profit    = rev - spend - est_fee

    # 첫 줄 (3개)
    row1_col1, row1_col2, row1_col3 = st.columns(3)
    row1_col1.metric("광고매출", f"{rev:,.0f}")
    row1_col2.metric("ROAS", f"{roas*100:,.2f}%")
    row1_col3.metric("광고비", f"{spend:,.0f}")

    # 두 번째 줄 (4개)
    row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4)
    row2_col1.metric("순수매출", f"{net_sales:,.0f}")
    row2_col2.metric("순이익(간단)", f"{profit:,.0f}")
    row2_col3.metric("클릭", f"{clicks:,.0f}")
    row2_col4.metric("노출", f"{impr:,.0f}")
# === 캠페인 분석 ===
elif view_name == "캠페인 분석":
    st.subheader("📈 캠페인별 성과")
    camp = view.groupby("campaign", as_index=False).agg({
        "impressions":"sum","clicks":"sum","spend":"sum","orders":"sum","revenue":"sum"
    })
    camp = add_metrics(camp)
    camp["ROAS(%)"] = camp["roas"]*100
    camp["ACoS(%)"] = camp["acos"]*100
    st.dataframe(
        camp[["campaign","impressions","clicks","spend","orders","revenue","ROAS(%)","ACoS(%)","cpc","ctr","cvr"]]
            .sort_values("revenue", ascending=False),
        use_container_width=True
    )

# === 키워드 분석 ===
elif view_name == "키워드 분석":
    st.subheader("🔑 키워드별 성과")
    if "keyword" in view.columns:
        group_cols = ["keyword"]
        if "match_type" in view.columns:
            group_cols.append("match_type")
        elif "ad_group" in view.columns:
            group_cols.append("ad_group")
        kw = view.groupby(group_cols, as_index=False).agg({
            "impressions":"sum","clicks":"sum","spend":"sum","orders":"sum","revenue":"sum"
        })
        kw = add_metrics(kw)
        kw["ROAS(%)"] = kw["roas"]*100
        kw["ACoS(%)"] = kw["acos"]*100
        st.dataframe(kw.sort_values("revenue", ascending=False), use_container_width=True)
    else:
        st.info("키워드 열이 없습니다. (열 매핑 필요)")

# === 제품 분석 ===
elif view_name == "제품 분석":
    st.subheader("📦 제품(옵션)별 성과")
    if {"product_id","product_name"}.issubset(view.columns):
        prod = view.groupby(["product_id","product_name"], as_index=False).agg({
            "impressions":"sum","clicks":"sum","spend":"sum","orders":"sum","revenue":"sum"
        })
        prod = add_metrics(prod)
        prod["ROAS(%)"] = prod["roas"]*100
        prod["ACoS(%)"] = prod["acos"]*100
        st.dataframe(prod.sort_values("revenue", ascending=False), use_container_width=True)
    else:
        st.info("product_id/product_name 열이 없습니다. (열 매핑에서 연결)")

# === 마진 계산기 ===
elif view_name == "마진 계산기":
    st.subheader("💰 마진 계산기")
    left, right = st.columns([1,2])
    with left:
        price_adj = st.number_input("판매가 조정(총액)", value=0.0, step=100.0)
        cost      = st.number_input("원가(총합)", value=0.0, step=100.0)
        fee_pct   = st.number_input("채널 수수료(%)", value=12.0, step=0.5)/100.0
        ship      = st.number_input("배송비(총합)", value=0.0, step=100.0)
        other     = st.number_input("기타비용(총합)", value=0.0, step=100.0)
    with right:
        rev = float(view["revenue"].sum()) + price_adj
        spend = float(view["spend"].sum())
        fee  = rev * fee_pct
        profit = rev - spend - fee - ship - other - cost
        margin = (profit/rev)*100 if rev>0 else 0.0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("매출", f"{rev:,.0f}")
        c2.metric("광고비", f"{spend:,.0f}")
        c3.metric("수수료", f"{fee:,.0f}")
        c4.metric("순이익", f"{profit:,.0f}")
        st.metric("마진율", f"{margin:,.2f}%")

