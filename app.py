# app.py — 마법의딸기 AI 광고 대시보드 (Streamlit MVP)
# 실행:  streamlit run app.py   (또는)  python3 -m streamlit run app.py

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="마법의딸기 AI 광고 대시보드", layout="wide")
st.title("🍓 마법의딸기 — AI 광고 대시보드 (MVP)")
st.caption("CSV 업로드 → 기간 선택 → 캠페인/키워드/제품 분석 → 마진 계산기 → 액션 내보내기")

REQUIRED_BASE_COLS = [
    "date", "campaign", "ad_group", "keyword", "product_id", "product_name",
    "impressions", "clicks", "spend", "orders", "revenue"
]
OPTIONAL_COLS = ["channel", "device", "placement", "match_type"]
METRIC_COLS = ["impressions", "clicks", "spend", "orders", "revenue"]

def coerce_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df

@st.cache_data(show_spinner=False)
def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ctr"] = np.where(df["impressions"]>0, df["clicks"]/df["impressions"], 0)
    df["cpc"] = np.where(df["clicks"]>0, df["spend"]/df["clicks"], 0)
    df["cvr"] = np.where(df["clicks"]>0, df["orders"]/df["clicks"], 0)
    df["roas"] = np.where(df["spend"]>0, df["revenue"]/df["spend"], 0)
    df["acos"] = np.where(df["revenue"]>0, df["spend"]/df["revenue"], 0)
    return df

with st.sidebar:
    st.header("1) 파일 업로드")
    # CSV + 엑셀 허용
    f = st.file_uploader("쿠팡 광고 리포트 파일 업로드 (CSV/XLSX)", type=["csv","xlsx","xls"])
    st.markdown(
        """
        **표준 스키마 권장 열**
        - 날짜/일자, 캠페인명, 광고그룹, 키워드, 상품ID, 상품명
        - 노출수, 클릭수, 광고비(광고비용), 주문수(판매수량), 매출액(전환매출액)
        """
    )

if f is None:
    st.info("왼쪽 사이드바에서 CSV/XLSX 파일을 업로드하세요. (쿠팡 원본 가능)")
    st.stop()

# ---- 파일 로딩: 엑셀/CSV 자동 처리 ----
name = f.name.lower()
raw = None
if name.endswith(("xlsx", "xls")):
    raw = pd.read_excel(f)   # 엑셀 읽기
else:
    # CSV 인코딩 자동 추정: UTF-8 → CP949 → EUC-KR
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

# 열 매핑 expander에서 필요하므로, 원본 컬럼 목록을 준비
raw_columns = list(raw.columns)

with st.expander("열 매핑(필요 시)", expanded=False):
    st.write("업로드한 CSV 열을 표준 스키마에 맞게 연결하세요.")
    mapped = {}
    for col in REQUIRED_BASE_COLS + OPTIONAL_COLS:
        mapped[col] = st.selectbox(
            f"{col} ← 업로드 열 선택", [None] + raw_columns, index=(raw_columns.index(col)+1 if col in raw_columns else 0)
        )

rename_map = {v:k for k,v in mapped.items() if v}
df = raw.rename(columns=rename_map).copy()

missing = [c for c in REQUIRED_BASE_COLS if c not in df.columns]
if missing:
    st.error(f"필수 열 누락: {missing}. 열 매핑에서 연결하거나 CSV를 수정하세요.")
    st.stop()

try:
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
except Exception:
    st.error("date 열을 날짜 형식으로 변환 실패. YYYY-MM-DD 권장")
    st.stop()

df = coerce_numeric(df, METRIC_COLS)
df = add_metrics(df)

with st.sidebar:
    st.header("2) 필터")
    min_d, max_d = df["date"].min(), df["date"].max()
    start, end = st.date_input("기간 선택", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    if isinstance(start, tuple):  # 구버전 호환
        start, end = start
    campaigns = sorted(df["campaign"].dropna().unique().tolist())
    sel_campaigns = st.multiselect("캠페인 선택(미선택=전체)", campaigns)

mask = (df["date"]>=start) & (df["date"]<=end)
if sel_campaigns:
    mask &= df["campaign"].isin(sel_campaigns)
view = df.loc[mask].copy()

if view.empty:
    st.warning("선택한 조건에 데이터가 없습니다.")
    st.stop()

# KPI
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("지출(Spend)", f"{view['spend'].sum():,.0f}")
col2.metric("매출(Revenue)", f"{view['revenue'].sum():,.0f}")
roas = (view["revenue"].sum()/view["spend"].sum()) if view["spend"].sum()>0 else 0
acos = (view["spend"].sum()/view["revenue"].sum()) if view["revenue"].sum()>0 else 0
col3.metric("ROAS", f"{roas:,.2f}")
col4.metric("ACoS", f"{acos:,.2f}")
col5.metric("클릭", f"{view['clicks'].sum():,.0f}")
col6.metric("노출", f"{view['impressions'].sum():,.0f}")

st.divider()

# 추이 그래프
by_date = view.groupby("date", as_index=False).agg({
    "spend":"sum", "revenue":"sum", "clicks":"sum", "impressions":"sum"
})
by_date["roas"] = np.where(by_date["spend"]>0, by_date["revenue"]/by_date["spend"], 0)

st.subheader("기간별 추이")
st.line_chart(by_date.set_index("date")["spend"])
st.line_chart(by_date.set_index("date")["revenue"])
st.line_chart(by_date.set_index("date")["roas"])

st.divider()

# 캠페인 표
st.subheader("캠페인별 성과")
camp = view.groupby("campaign", as_index=False).agg({
    "impressions":"sum","clicks":"sum","spend":"sum","orders":"sum","revenue":"sum"
})
camp = add_metrics(camp)
sort_by = st.selectbox("정렬 기준", ["revenue","roas","acos","spend","orders","clicks"], index=1)
ascending = st.toggle("오름차순 정렬", value=False)
st.dataframe(camp.sort_values(sort_by, ascending=ascending), use_container_width=True)

st.divider()

# 상세: 키워드/제품
st.subheader("캠페인 상세 보기")
sel_camp = st.selectbox("캠페인 선택", ["(전체)"] + campaigns)
detail = view[view["campaign"]==sel_camp].copy() if sel_camp != "(전체)" else view.copy()

kw, prod = st.tabs(["키워드별", "제품별"])
with kw:
    group_cols = ["keyword"]
    group_cols.append("match_type" if "match_type" in detail.columns else "ad_group")
    kw_tbl = detail.groupby(group_cols, as_index=False).agg({
        "impressions":"sum","clicks":"sum","spend":"sum","orders":"sum","revenue":"sum"
    })
    kw_tbl = add_metrics(kw_tbl)
    st.write("**키워드별 성과**")
    st.dataframe(kw_tbl.sort_values("revenue", ascending=False), use_container_width=True)

    st.write("**성과 모아보기**")
    colA, colB, colC = st.columns(3)
    target_acos = colA.number_input("목표 ACoS", value=0.25, step=0.01)
    min_clicks  = colB.number_input("최소 클릭(분석대상)", value=50, step=10)
    min_orders  = colC.number_input("성과 좋음: 최소 주문수", value=3, step=1)

    good = kw_tbl[(kw_tbl["orders"]>=min_orders) & (kw_tbl["acos"]<=target_acos)]
    zero = kw_tbl[(kw_tbl["clicks"]>=100) & (kw_tbl["orders"]==0)]
    bad  = kw_tbl[(kw_tbl["acos"]>target_acos) & (kw_tbl["clicks"]>=min_clicks)]

    st.markdown("**성과 좋음(승자 후보)**")
    st.dataframe(good.sort_values("roas", ascending=False), use_container_width=True)
    st.markdown("**성과 없음(일시중지 후보)** — 클릭≥100 & 주문=0")
    st.dataframe(zero.sort_values("clicks", ascending=False), use_container_width=True)
    st.markdown("**비효율(입찰↓ 후보)** — ACoS>목표 & 클릭 충분")
    st.dataframe(bad.sort_values("acos", ascending=False), use_container_width=True)

    st.markdown("**액션 CSV 내보내기**")
    action_rows = []
    for _, r in zero.iterrows():
        action_rows.append({"level":"keyword","name":r["keyword"],"action":"pause","reason":"Clicks≥100 & Orders=0"})
    for _, r in bad.iterrows():
        action_rows.append({"level":"keyword","name":r["keyword"],"action":"bid_down","change_pct":-15,"reason":"ACoS>target"})
    for _, r in good.iterrows():
        action_rows.append({"level":"keyword","name":r["keyword"],"action":"bid_up","change_pct":10,"reason":"Good ROAS"})
    if action_rows:
        act_df = pd.DataFrame(action_rows)
        st.dataframe(act_df, use_container_width=True)
        csv = act_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("액션 CSV 다운로드", data=csv, file_name="actions.csv", mime="text/csv")
    else:
        st.info("조건에 맞는 액션이 없습니다. 임계값을 조정하세요.")

with prod:
    prod_tbl = detail.groupby(["product_id", "product_name"], as_index=False).agg({
        "impressions":"sum","clicks":"sum","spend":"sum","orders":"sum","revenue":"sum"
    })
    prod_tbl = add_metrics(prod_tbl)
    st.write("**제품별 성과**")
    st.dataframe(prod_tbl.sort_values("revenue", ascending=False), use_container_width=True)

st.divider()
st.subheader("마진 계산기")
left, right = st.columns([1,2])
with left:
    st.markdown("제품 기본값(없으면 직접 입력)")
    default_cost = st.number_input("원가(매입가)", value=0.0, step=100.0)
    fee_pct = st.number_input("채널 수수료(%)", value=12.0, step=0.5) / 100.0
    shipping = st.number_input("배송비(건)", value=0.0, step=100.0)
    other = st.number_input("기타비용(건)", value=0.0, step=100.0)
with right:
    rev = view["revenue"].sum()
    spend = view["spend"].sum()
    est_fee = rev * fee_pct
    profit = rev - spend - est_fee - shipping - other - default_cost
    margin = (profit/rev) if rev>0 else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("매출", f"{rev:,.0f}")
    c2.metric("광고비", f"{spend:,.0f}")
    c3.metric("예상 수수료", f"{est_fee:,.0f}")
    c4.metric("추정 이익", f"{profit:,.0f}")
    st.metric("마진율", f"{margin*100:,.2f}%")

st.success("완료! 상단에서 기간/캠페인을 바꿔보며 대시보드를 확인하세요.")

