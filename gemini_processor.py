# gemini_processor.py

import google.generativeai as genai
import os
import json
import re

model = None

def configure_gemini():
    """Gemini API 키를 설정하고 모델을 초기화합니다."""
    global model
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            print("="*50); print("오류: GEMINI_API_KEY 환경 변수가 없습니다."); print("="*50); exit()
        
        genai.configure(api_key=api_key)
        
        # -------------------------------------------------
        # [수정] 님의 요청대로 'gemini-2.5-pro' 모델로 복귀
        # -------------------------------------------------
        model = genai.GenerativeModel('gemini-2.5-pro') 
        print("Gemini 모델이 성공적으로 설정되었습니다. ('gemini-2.5-pro' 사용)")
        return model
    except Exception as e:
        print(f"오류: API 키 설정에 실패했습니다: {e}"); exit()

def get_summary_from_gemini(tab_titles, window_titles):
    """[수정] 'summary'(1줄 요약)을 다시 포함하도록 요청합니다."""
    global model
    if not model:
        print("오류: Gemini 모델이 초기화되지 않았습니다.")
        return []

    # (프롬프트는 동일... 생략)
    prompt = f"""
[데이터]
- 브라우저 탭: {tab_titles}
- 프로그램 창: {window_titles}

[임무]
당신은 [데이터]를 분석하여 JSON으로 그룹화하는 로봇입니다.
인사말이나 불필요한 설명을 절대 하지 마세요.

[규칙]
1. 반드시 "JSON 리스트" 형식으로만 응답해야 합니다.
2. 각 그룹은 'category'(그룹 이름), 'summary'(1줄 요약), 'items'(항목 리스트) 키를 가져야 합니다.
3. [데이터]를 기반으로 3~5개의 카테고리로 세분화하여 그룹화하세요.
4. '시스템 및 유틸리티', '새 탭' 같은 무의미한 그룹은 만들지 말고, 실제 작업 위주로 묶어주세요.

[JSON 형식 예시]
[
  {{"category": "업무 문서 작업", "summary": "엑셀과 노션으로 문서를 작성 중입니다.", "items": ["보고서.xlsx", "회의록 - Notion"]}}
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
        
        # 1. [수정] 마크다운 블록 제거 (더욱 강력하게)
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
            
        if text.endswith("```"):
            text = text[:-3]
            
        text = text.strip() # 다시 공백 제거

        # 2. [수정] JSON 시작점 찾기 (첫 '{' 또는 '[')
        json_start_index = -1
        first_brace = text.find('[')
        first_bracket = text.find('{')

        if first_brace != -1 and (first_brace < first_bracket or first_bracket == -1):
            json_start_index = first_brace
        elif first_bracket != -1:
            json_start_index = first_bracket
        
        if json_start_index == -1:
             raise ValueError("AI 응답에서 JSON 시작점( '[' 또는 '{' )을 찾을 수 없습니다.")

        # 3. [수정] JSON 끝점 찾기 (마지막 '}' 또는 ']')
        last_brace = text.rfind(']')
        last_bracket = text.rfind('}')
        json_end_index = max(last_brace, last_bracket)
        
        if json_end_index == -1:
            raise ValueError("AI 응답에서 JSON 끝점( ']' 또는 '}' )을 찾을 수 없습니다.")

        # 4. [수정] 시작점과 끝점을 기준으로 '정확한' JSON 부분만 잘라내기
        cleaned_json = text[json_start_index : json_end_index + 1]
        
        # 5. [수정] AI가 리스트 괄호([ ])를 빠뜨린 경우 수동 복구
        #    (시작이 '{' 이면, AI가 1개 이상의 객체를 보냈지만 
        #     리스트로 감싸지 않은 것으로 간주하고 강제로 래핑)
        starts_with_bracket = cleaned_json.startswith('[')
        ends_with_bracket = cleaned_json.endswith(']')
        starts_with_brace = cleaned_json.startswith('{')
        ends_with_brace = cleaned_json.endswith('}')

        if starts_with_bracket and ends_with_bracket:
            # "[ { ... } ]" -> 정상
            pass
        elif starts_with_brace and ends_with_brace:
            # "{ ... }" 또는 "{...}, {...}" -> AI가 양쪽 괄호를 모두 빠뜨림
            print("[DEBUG] AI가 리스트 괄호 '['와 ']'를 빠뜨린 것으로 보입니다. 수동 복구합니다...")
            cleaned_json = '[' + cleaned_json + ']'
        elif starts_with_brace and ends_with_bracket:
            # "{ ... } ]" -> AI가 여는 괄호 '['를 빠뜨림 (이번 오류 케이스)
            print("[DEBUG] AI가 여는 괄호 '['를 빠뜨린 것으로 보입니다. 수동 복구합니다...")
            cleaned_json = '[' + cleaned_json
        
        # 6. 파싱
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