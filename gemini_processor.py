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
        
        # 님의 요청대로 'gemini-2.5-pro' 모델을 사용합니다.
        model = genai.GenerativeModel('gemini-2.5-pro') 
        print("Gemini 모델이 성공적으로 설정되었습니다. ('gemini-2.5-pro' 사용)")
        return model
    except Exception as e:
        print(f"오류: API 키 설정에 실패했습니다: {e}"); exit()

def get_summary_from_gemini(tab_titles, window_titles):
    """두 목록을 받아 Gemini에게 '그룹핑 JSON'을 요청합니다. (요약 없음)"""
    global model
    if not model:
        print("오류: Gemini 모델이 초기화되지 않았습니다.")
        return []

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
3. [데이터]를 기반으로 3~5개의 카테고리로 세분화하여 그룹화하세요.  # <-- [수정] 2-4개 -> 3-5개
4. '시스템 및 유틸리티', '새 탭' 같은 무의미한 그룹은 만들지 말고, 실제 작업 위주로 묶어주세요. # <-- [추가] 품질 향상

[JSON 형식 예시]
[
  {{"category": "업무 문서 작업", "items": ["보고서.xlsx", "회의록 - Notion"]}}
]

[JSON 응답 시작]
[
"""

    print(f"Gemini(2.5 Pro)에게 {len(tab_titles)}개 탭과 {len(window_titles)}개 창의 JSON 그룹핑을 요청합니다...")
    
    ai_response_text = None 
    try:
        response = model.generate_content(prompt)
        ai_response_text = response.text 
        
        print(f"[DEBUG] AI 원본 응답 수신:\n{ai_response_text}")
        
        text = ai_response_text.strip()
        
        json_start_index = -1
        first_brace = text.find('[')
        first_bracket = text.find('{')

        if first_brace != -1 and (first_brace < first_bracket or first_bracket == -1):
            json_start_index = first_brace
        elif first_bracket != -1:
            json_start_index = first_bracket
        
        if json_start_index == -1:
             raise ValueError("AI 응답에서 JSON 시작점( '[' 또는 '{' )을 찾을 수 없습니다.")

        cleaned_json = text[json_start_index:]
        
        if cleaned_json.startswith('{'):
            print("[DEBUG] AI가 '['를 빠뜨렸습니다. JSON을 수동으로 복구합니다...")
            cleaned_json = '[' + cleaned_json
        
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