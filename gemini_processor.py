# gemini_processor.py

import google.generativeai as genai
import os
import json
# [수정] re 모듈을 사용하지 않습니다.

model = None

def configure_gemini():
    """Gemini API 키를 설정하고 모델을 초기화합니다."""
    global model
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            print("="*50); print("오류: GEMINI_API_KEY 환경 변수가 없습니다."); print("="*50); exit()
        
        genai.configure(api_key=api_key)
        
        # 님의 요청대로 'gemini-2.5-flash' 모델을 사용합니다.
        model = genai.GenerativeModel('gemini-2.5-flash') 
        print("Gemini 모델이 성공적으로 설정되었습니다. ('gemini-2.5-flash' 사용)")
        return model
    except Exception as e:
        print(f"오류: API 키 설정에 실패했습니다: {e}"); exit()

def get_summary_from_gemini(tab_titles, window_titles):
    """두 목록을 받아 Gemini에게 '그룹핑 JSON'을 요청합니다."""
    global model
    if not model:
        print("오류: Gemini 모델이 초기화되지 않았습니다.")
        return []

    # -------------------------------------------------
    # [수정] AI가 "요약(summary)"을 하지 않도록 프롬프트를 수정
    # -------------------------------------------------
    prompt = f"""
[데이터]
- 브라우저 탭: {tab_titles}
- 프로그램 창: {window_titles}

[임무]
당신은 [데이터]를 분석하여 JSON으로 그룹화하는 로봇입니다.
인사말이나 불필요한 설명을 절대 하지 마세요.

[규칙]
1. 반드시 "JSON 리스트" 형식으로만 응답해야 합니다.
2. 각 그룹은 'category'(그룹 이름)와 'items'(항목 리스트) 키만 가져야 합니다.
3. [데이터]를 기반으로 2~4개의 카테고리로 그룹화하세요.

[JSON 형식 예시]
[
  {{"category": "업무 문서 작업", "items": ["보고서.xlsx", "회의록 - Notion"]}}
]

[JSON 응답 시작]
[
"""
    # -------------------------------------------------

    print(f"Gemini(Flash 2.5)에게 {len(tab_titles)}개 탭과 {len(window_titles)}개 창의 JSON 그룹핑을 요청합니다...")
    
    ai_response_text = None 
    try:
        # 타임아웃 제거됨
        response = model.generate_content(prompt)
        ai_response_text = response.text 
        
        print(f"[DEBUG] AI 원본 응답 수신:\n{ai_response_text}")
        
        text = ai_response_text.strip()
        
        # [수정] re(정규식)를 사용하지 않는 원래의 간단한 파싱 방식
        
        # AI가 '['로 시작하지 않을 수 있으니, 첫 '['를 찾습니다.
        json_start_index = text.find('[')
        if json_start_index == -1:
             raise ValueError("AI 응답에서 JSON 시작점( '[' )을 찾을 수 없습니다.")

        # '['부터 끝까지가 JSON이라고 가정
        cleaned_json = text[json_start_index:]
        
        parsed_json = json.loads(cleaned_json)
        print(f"[DEBUG] JSON 파싱 성공. {len(parsed_json)}개 카테고리 반환.")
        return parsed_json

    except Exception as e:
        print("="*50)
        print(f"[DEBUG] !!! CRITICAL ERROR IN GEMINI PROCESSOR !!!")
        print(f"[DEBUG] 오류: {e}")
        if ai_response_text:
            print(f"[DEBUG] AI 원본 응답 (파싱 실패): {ai_response_text}")
        print("="*50)
        return [] # 오류 시 빈 리스트 반환