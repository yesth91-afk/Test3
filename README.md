# 🛒 쇼핑 리스트

아이템 추가 · 수정 · 삭제 · 체크를 지원하는 간단한 Streamlit 웹 앱입니다.

## 실행

```
pip install -r requirements.txt
streamlit run app.py
```

## 데이터 저장 방식

- 접속하면 주소에 `?list=토큰`이 붙고, 이 토큰마다 `data/<토큰>.json`에 목록이 따로 저장됩니다.
- **주소(URL)를 북마크하면 내 목록을 다시 볼 수 있습니다.** 주소를 아는 사람은 같은 목록을 볼 수 있으니 공유에 주의하세요.
- Streamlit Community Cloud는 파일이 영구 보관되지 않아 앱이 재시작되면 목록이 사라질 수 있습니다. 오래 보관하려면 외부 저장소(Google Sheets, Supabase 등)가 필요합니다.

## 배포 (Streamlit Community Cloud)

1. 이 폴더를 GitHub 저장소에 올립니다. (`data/`는 `.gitignore`로 제외됨)
2. [share.streamlit.io](https://share.streamlit.io)에서 저장소, 브랜치, `app.py`를 선택해 Deploy 합니다.
