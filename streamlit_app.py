from io import BytesIO
import hashlib

import pandas as pd
import streamlit as st

st.set_page_config(page_title="학생 성취 분석·학습지원", page_icon="📚", layout="wide")

SCORES = {"math score": "수학", "reading score": "읽기", "writing score": "쓰기"}
GROUPS = {
    "gender": "성별",
    "race/ethnicity": "인종·민족",
    "parental level of education": "부모 학력",
    "lunch": "급식 유형",
    "test preparation course": "시험 준비 과정",
}
LABELS = {
    "female": "여학생", "male": "남학생",
    "completed": "이수", "none": "미이수",
    "standard": "일반", "free/reduced": "무료·할인",
    "some high school": "고등학교 일부 이수", "high school": "고등학교 졸업",
    "some college": "대학 일부 이수", "associate's degree": "전문학사",
    "bachelor's degree": "학사", "master's degree": "석사",
}


def load_data(file_bytes):
    """업로드 내용을 검증하고 분석에 필요한 열만 반환합니다."""
    try:
        frame = pd.read_csv(BytesIO(file_bytes), sep=None, engine="python", encoding="utf-8-sig")
    except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError, ValueError):
        raise ValueError("UTF-8 형식의 CSV 또는 탭 구분 파일을 사용해 주세요.") from None
    frame.columns = frame.columns.str.strip()
    required = list(GROUPS) + list(SCORES)
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError("필수 열이 없습니다: " + ", ".join(missing))
    if frame.columns.duplicated().any():
        raise ValueError("열 이름이 중복되어 있습니다. 열 이름을 확인해 주세요.")
    frame = frame[required].copy()
    if frame.empty:
        raise ValueError("학생 데이터가 없습니다. 제목 행 아래에 데이터를 넣어 주세요.")
    for column in GROUPS:
        frame[column] = frame[column].astype("string").str.strip()
        if frame[column].isna().any() or frame[column].eq("").any():
            raise ValueError("집단 항목에 빈칸이 있습니다. 빈칸을 채운 후 다시 업로드해 주세요.")
    for column in SCORES:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any() or not frame[column].between(0, 100).all():
            raise ValueError("점수는 빈칸 없이 0~100 사이 숫자로 입력해 주세요.")
    return frame


st.title("📚 학생 성취 분석·학습지원")
st.write("집단별 성취 경향을 살펴보고, 설정한 점수 기준에 따라 학습지원 규모를 확인하세요.")
uploaded = st.file_uploader("학생 데이터 파일을 드래그 앤 드롭하거나 선택하세요", type=["csv", "tsv", "txt"])
st.caption("UTF-8 CSV 또는 탭 구분 텍스트를 지원합니다. 업로드 파일을 프로젝트에 저장하거나 공용 데이터 캐시에 보관하지 않습니다.")
with st.expander("파일에 필요한 열 확인"):
    st.code(", ".join(list(GROUPS) + list(SCORES)), language=None)
    st.write("한 행에 학생 한 명을 입력하고, 세 과목 점수는 0~100 사이 숫자로 입력하세요. 시험 준비 과정은 completed(이수) 또는 none(미이수)으로 표시합니다. 추가 열은 분석에서 제외합니다.")
if uploaded is None:
    for column in GROUPS:
        st.session_state.pop(column, None)
    st.session_state.pop("uploaded_fingerprint", None)
    st.info("파일을 업로드하면 분석 결과가 표시됩니다.")
    st.stop()

file_bytes = uploaded.getvalue()
fingerprint = hashlib.sha256(file_bytes).hexdigest()
if st.session_state.get("uploaded_fingerprint") != fingerprint:
    for column in GROUPS:
        st.session_state.pop(column, None)
    st.session_state["uploaded_fingerprint"] = fingerprint
try:
    data = load_data(file_bytes)
except ValueError as error:
    st.error(str(error))
    st.stop()
st.caption("집단 간 차이는 관찰된 연관성이며, 시험 준비 과정의 효과나 개인의 능력을 단정하는 근거가 아닙니다.")

st.sidebar.header("분석할 집단")
filtered = data.copy()
for column, label in GROUPS.items():
    options = sorted(data[column].unique())
    selected = st.sidebar.multiselect(
        label, options, default=options,
        format_func=lambda value: LABELS.get(value, value), key=column,
    )
    filtered = filtered[filtered[column].isin(selected)]
st.sidebar.caption("항목을 모두 해제하면 해당 조건에 맞는 학생이 없습니다.")
st.sidebar.header("학습지원 기준")
math_cutoff = st.sidebar.slider("수학 기준 점수", 0, 100, 60)
writing_cutoff = st.sidebar.slider("쓰기 기준 점수", 0, 100, 60)
st.sidebar.caption("각 기준 점수 미만을 지원 검토 대상으로 집계합니다. 실제 지원 여부는 추가 정보를 함께 검토하세요.")

if filtered.empty:
    st.warning("선택한 조건에 해당하는 학생이 없습니다. 왼쪽 필터를 조정해 주세요.")
    st.stop()

both = (filtered["math score"] < math_cutoff) & (filtered["writing score"] < writing_cutoff)
metrics = st.columns(5)
metrics[0].metric("선택된 학생", f"{len(filtered):,}명")
for col, (score, label) in zip(metrics[1:4], SCORES.items()):
    col.metric(f"{label} 평균", f"{filtered[score].mean():.1f}점")
metrics[4].metric("수학·쓰기 동시 지원 검토", f"{both.sum():,}명", f"전체의 {both.mean():.1%}", delta_color="off")

reading_tab, support_tab, group_tab = st.tabs(["읽기 점수 분포", "수학·쓰기 학습지원", "집단별 성취 비교"])

with reading_tab:
    st.subheader("시험 준비 과정을 거친 학생들의 읽기 점수는 어떤가요?")
    prepared = filtered[filtered["test preparation course"] == "completed"]
    if prepared.empty:
        st.info("현재 필터에는 시험 준비 과정 이수 학생이 없습니다.")
    else:
        cols = st.columns(4)
        cols[0].metric("이수 학생", f"{len(prepared):,}명")
        cols[1].metric("읽기 평균", f"{prepared['reading score'].mean():.1f}점")
        cols[2].metric("읽기 중앙값", f"{prepared['reading score'].median():.1f}점")
        cols[3].metric("읽기 25~75백분위", f"{prepared['reading score'].quantile(.25):.1f}~{prepared['reading score'].quantile(.75):.1f}점")
    scale = st.radio("분포 표시 방식", ["집단 내 비율(%)", "학생 수"], horizontal=True)
    bins = list(range(0, 101, 10)) + [101]
    bin_labels = [f"{n}~{n + 9}" for n in range(0, 100, 10)] + ["100"]
    counts = pd.crosstab(
        pd.cut(filtered["reading score"], bins=bins, right=False, labels=bin_labels),
        filtered["test preparation course"], dropna=False,
    ).reindex(bin_labels, fill_value=0)
    distribution = counts.copy()
    if scale == "집단 내 비율(%)":
        distribution = counts.div(counts.sum().replace(0, float("nan")), axis=1).mul(100).fillna(0)
    distribution = distribution.rename(columns=LABELS)
    st.bar_chart(distribution, x_label="읽기 점수 구간", y_label=scale, stack=False)
    st.caption("각 집단의 크기가 다르므로 분포를 비교할 때는 집단 내 비율을 함께 확인하세요. 100점은 별도 구간입니다.")
    summary = filtered.groupby("test preparation course")["reading score"].agg(
        학생수="count", 평균="mean", 중앙값="median", 표준편차="std", 최솟값="min", 최댓값="max",
    ).rename(index=LABELS).rename_axis("시험 준비 과정")
    st.dataframe(summary.round(1), width="stretch")

with support_tab:
    st.subheader("수학과 쓰기에서 함께 지원이 필요한 학생은 몇 명인가요?")
    math_low = filtered["math score"] < math_cutoff
    writing_low = filtered["writing score"] < writing_cutoff
    st.write(f"수학 **{math_cutoff}점 미만**이면서 쓰기 **{writing_cutoff}점 미만**인 학생은 **{both.sum():,}명 ({both.mean():.1%})**입니다.")
    support = pd.DataFrame({
        "지원 구분": ["수학·쓰기 모두", "수학만", "쓰기만", "두 과목 기준 이상"],
        "학생 수": [int(both.sum()), int((math_low & ~writing_low).sum()), int((~math_low & writing_low).sum()), int((~math_low & ~writing_low).sum())],
    })
    support["비율(%)"] = support["학생 수"] / len(filtered) * 100
    st.bar_chart(support.set_index("지원 구분")[["학생 수"]], y_label="학생 수")
    st.dataframe(support.round(1), hide_index=True, width="stretch")
    st.subheader("수학·쓰기 점수의 관계")
    points = filtered[["math score", "writing score"]].copy()
    points["지원 구분"] = "그 외"
    points.loc[both, "지원 구분"] = "동시 지원 검토"
    st.scatter_chart(points, x="math score", y="writing score", color="지원 구분", x_label="수학 점수", y_label="쓰기 점수")
    st.caption("점이 겹칠 수 있으므로 정확한 학생 수는 위 집계표를 확인하세요.")
    st.download_button("지원 규모 집계표 CSV 다운로드", support.to_csv(index=False).encode("utf-8-sig"), "learning_support_summary.csv", "text/csv")

with group_tab:
    st.subheader("집단별 평균과 지원 규모 비교")
    group = st.selectbox("비교 기준", list(GROUPS), format_func=lambda value: GROUPS[value])
    grouped = filtered.assign(동시지원=both).groupby(group)
    table = grouped[list(SCORES)].mean().rename(columns=SCORES)
    table.insert(0, "학생 수", grouped.size())
    table["동시 지원 학생 수"] = grouped["동시지원"].sum().astype(int)
    table["동시 지원 비율(%)"] = grouped["동시지원"].mean() * 100
    table = table.rename(index=LABELS).rename_axis(GROUPS[group])
    st.bar_chart(table[list(SCORES.values())], stack=False, y_label="평균 점수")
    st.dataframe(table.round(1), width="stretch")
    st.caption("작은 집단의 평균은 일부 학생의 점수에 크게 영향을 받을 수 있습니다. 학생 수와 함께 해석하세요. 인종·민족 표기는 제공된 데이터의 원문 범주를 유지했습니다.")
    st.download_button("집단별 집계표 CSV 다운로드", table.round(2).to_csv().encode("utf-8-sig"), "group_summary.csv", "text/csv")
