import html
import json
import os
import re
import secrets
import uuid
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MAX_NAME_LEN = 100
LIST_ID_RE = re.compile(r"[A-Za-z0-9_-]{8,32}")  # 파일 경로에 쓰이므로 엄격히 검증


# ---------- 목록 식별 (사용자별 분리) ----------
def init_list_id():
    """URL의 ?list=토큰으로 목록을 구분한다. 없거나 형식이 틀리면 새로 발급한다."""
    if "list_id" in st.session_state:
        return
    token = st.query_params.get("list", "")
    if not LIST_ID_RE.fullmatch(token):
        token = secrets.token_urlsafe(9)  # 12자, 추측하기 어려운 값
    if st.query_params.get("list") != token:
        st.query_params["list"] = token
    st.session_state.list_id = token


def data_file() -> Path:
    return DATA_DIR / f"{st.session_state.list_id}.json"


# ---------- 저장 / 불러오기 (F7) ----------
def sanitize_items(data) -> list:
    """파일 내용을 검증해 올바른 아이템 목록만 돌려준다."""
    if not isinstance(data, list):
        return []
    items, seen_ids = [], set()
    for d in data:
        if not isinstance(d, dict):
            continue
        name = str(d.get("name", "")).strip()[:MAX_NAME_LEN]
        if not name:
            continue
        item_id = str(d.get("id") or "")
        if not item_id or item_id in seen_ids:  # 비었거나 중복이면 새로 발급
            item_id = str(uuid.uuid4())
        seen_ids.add(item_id)
        items.append({"id": item_id, "name": name, "checked": d.get("checked") is True})
    return items


def load_items() -> list:
    """저장 파일을 읽는다. 깨진 파일은 .bak으로 보존하고 빈 목록으로 시작한다."""
    path = data_file()
    try:
        raw = path.read_text(encoding="utf-8-sig")  # BOM이 있어도 읽는다
    except OSError:
        return []
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("list가 아님")
    except ValueError:
        try:
            os.replace(path, path.with_suffix(".bak"))  # 다음 저장이 원본을 덮어쓰지 않게 보존
        except OSError:
            pass
        return []
    return sanitize_items(data)


def save_items():
    """임시 파일에 쓴 뒤 교체해서 쓰다가 끊겨도 파일이 깨지지 않게 한다."""
    path = data_file()
    tmp = path.with_suffix(f".{uuid.uuid4().hex[:8]}.tmp")
    try:
        DATA_DIR.mkdir(exist_ok=True)
        tmp.write_text(
            json.dumps(st.session_state.shopping_items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, path)
        st.session_state.save_failed = False
    except OSError:
        st.session_state.save_failed = True
        try:
            tmp.unlink()
        except OSError:
            pass


# ---------- 상태 초기화 ----------
def init_state():
    # 아이템 구조: {"id": str(uuid), "name": str, "checked": bool}
    # 주의: st.session_state.items는 dict.items()와 충돌하므로 쓰지 않는다.
    init_list_id()
    if "shopping_items" not in st.session_state:
        st.session_state.shopping_items = load_items()
    st.session_state.setdefault("save_failed", False)


# ---------- 기능 함수 ----------
def find_item(item_id: str):
    for item in st.session_state.shopping_items:
        if item["id"] == item_id:
            return item
    return None


def name_exists(name: str, exclude_id: str | None = None) -> bool:
    key = name.casefold()
    return any(
        i["name"].casefold() == key and i["id"] != exclude_id
        for i in st.session_state.shopping_items
    )


def add_item(name: str) -> str:
    """'ok' / 'empty' / 'dup' 중 하나를 돌려준다."""
    name = name.strip()
    if not name:
        return "empty"
    if name_exists(name):
        return "dup"
    st.session_state.shopping_items.append(
        {"id": str(uuid.uuid4()), "name": name, "checked": False}
    )
    save_items()
    return "ok"


def update_item(item_id: str, new_name: str) -> str | None:
    """성공하면 None, 실패하면 오류 문구를 돌려준다."""
    new_name = new_name.strip()
    if not new_name:
        return "이름을 입력해주세요."
    if name_exists(new_name, exclude_id=item_id):
        return "이미 목록에 있는 이름이에요."
    item = find_item(item_id)
    if item is None:
        return "항목을 찾을 수 없어요."
    item["name"] = new_name
    save_items()
    return None


def forget_row_state(item_id: str):
    for key in (f"editing_{item_id}", f"edit_error_{item_id}", f"edit_input_{item_id}", f"chk_{item_id}"):
        st.session_state.pop(key, None)


def toggle_item(item_id: str):
    # 체크박스 위젯의 현재 값을 아이템에 반영한다.
    item = find_item(item_id)
    if item is not None:
        item["checked"] = bool(st.session_state.get(f"chk_{item_id}", False))
        save_items()


def delete_item(item_id: str):
    st.session_state.shopping_items = [
        i for i in st.session_state.shopping_items if i["id"] != item_id
    ]
    forget_row_state(item_id)
    save_items()


def clear_checked():
    for i in st.session_state.shopping_items:
        if i["checked"]:
            forget_row_state(i["id"])
    st.session_state.shopping_items = [
        i for i in st.session_state.shopping_items if not i["checked"]
    ]
    save_items()


# ---------- 수정 모드 (행별 상태) ----------
def start_edit(item_id: str):
    st.session_state.pop(f"edit_input_{item_id}", None)  # 이전 입력값 초기화
    st.session_state.pop(f"edit_error_{item_id}", None)
    st.session_state[f"editing_{item_id}"] = True


def cancel_edit(item_id: str):
    st.session_state.pop(f"edit_input_{item_id}", None)
    st.session_state.pop(f"edit_error_{item_id}", None)
    st.session_state[f"editing_{item_id}"] = False


def save_edit(item_id: str):
    new_name = st.session_state.get(f"edit_input_{item_id}", "")
    error = update_item(item_id, new_name)
    if error:
        st.session_state[f"edit_error_{item_id}"] = error  # 수정 모드 유지
    else:
        cancel_edit(item_id)


# ---------- 화면 ----------
def load_css():
    try:
        css = (BASE_DIR / "style.css").read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    except OSError:
        pass  # 스타일 파일이 없어도 기능은 동작한다


def set_page_lang():
    """Streamlit 기본 <html lang="en">을 ko로 바꾼다 (스크린리더 발음용)."""
    try:
        with st.container(key="lang_shim"):
            st.html(
                "<script>document.documentElement.lang='ko'</script>",
                unsafe_allow_javascript=True,
            )
    except TypeError:
        pass  # 옛 Streamlit 버전에서는 건너뛴다


# 참고: 행별 st.fragment로도 시도했으나 100개 기준에서 체크/삭제/추가가 오히려
# 2배 느려져(전체 재실행 + 이중 실행) 일반 콜백 방식을 유지한다.
def render_item(item: dict):
    item_id = item["id"]
    with st.container(key=f"item_{item_id}"):
        if st.session_state.get(f"editing_{item_id}", False):
            render_edit_row(item)
        else:
            render_view_row(item)


def render_edit_row(item: dict):
    item_id = item["id"]
    with st.container(key=f"editrow_{item_id}"):
        # Enter로도 저장되도록 form 사용
        with st.form(key=f"edit_form_{item_id}", border=False):
            c_input, c_save, c_cancel = st.columns([6, 1.2, 1.2])
            c_input.text_input(
                "이름 수정",
                value=item["name"],
                key=f"edit_input_{item_id}",
                max_chars=MAX_NAME_LEN,
                label_visibility="collapsed",
            )
            c_save.form_submit_button(
                "저장",
                on_click=save_edit,
                args=(item_id,),
                use_container_width=True,
                type="primary",
            )
            c_cancel.form_submit_button(
                "취소", on_click=cancel_edit, args=(item_id,), use_container_width=True
            )
    error = st.session_state.get(f"edit_error_{item_id}")
    if error:
        st.error(error)


def render_view_row(item: dict):
    item_id = item["id"]
    with st.container(key=f"row_{item_id}"):
        c_chk, c_name, c_edit, c_del = st.columns([0.6, 8, 0.8, 0.8])
        c_chk.checkbox(
            f"{item['name']} 완료",
            value=item["checked"],
            key=f"chk_{item_id}",
            on_change=toggle_item,
            args=(item_id,),
            label_visibility="collapsed",
        )
        # 이름은 HTML 이스케이프 후 st.html로 그대로 출력한다.
        # (마크다운을 거치지 않아 URL, :이모지코드:, *서식* 이 변형되지 않는다)
        css_class = "item-name done" if item["checked"] else "item-name"
        c_name.html(f'<span class="{css_class}">{html.escape(item["name"])}</span>')
        c_edit.button(
            "수정",
            icon=":material/edit:",
            key=f"edit_{item_id}",
            on_click=start_edit,
            args=(item_id,),
        )
        c_del.button(
            "삭제",
            icon=":material/delete:",
            key=f"del_{item_id}",
            on_click=delete_item,
            args=(item_id,),
        )


init_state()
load_css()

st.title("🛒 쇼핑 리스트")

with st.form("add_form", clear_on_submit=True):
    col_input, col_btn = st.columns([5, 1.3])
    new_name = col_input.text_input(
        "아이템",
        placeholder="살 물건을 입력하고 Enter",
        max_chars=MAX_NAME_LEN,
        label_visibility="collapsed",
    )
    submitted = col_btn.form_submit_button(
        "추가", use_container_width=True, type="primary"
    )

if submitted and add_item(new_name) == "dup":
    st.warning("이미 목록에 있는 아이템이에요.")

if st.session_state.save_failed:
    st.warning("저장하지 못했어요. 새로고침하면 변경 내용이 사라질 수 있어요.")

items = st.session_state.shopping_items

if not items:
    st.markdown(
        '<div class="empty-state"><span class="emoji">🧺</span>'
        "아직 추가된 아이템이 없어요</div>",
        unsafe_allow_html=True,  # 고정 문구만 사용 (사용자 입력 없음)
    )
else:
    done = sum(1 for i in items if i["checked"])
    st.caption(f"전체 {len(items)}개 중 {done}개 완료")
    st.progress(done / len(items))

    for item in items:
        render_item(item)

    st.button(
        "완료 항목 모두 삭제",
        key="clear_btn",
        on_click=clear_checked,
        disabled=done == 0,
    )
    st.caption("🔗 이 페이지 주소(URL)를 북마크하면 내 목록을 다시 볼 수 있어요.")

set_page_lang()  # 레이아웃 간격에 영향이 없도록 맨 끝에서 호출
