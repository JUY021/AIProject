# gemini_processor.py

import google.generativeai as genai
import os
import json
import re
# [수정] 타임아웃 예외를 잡을 필요가 없으므로 import 제거
# import google.api_core.exceptions 

model = None

def configure_gemini():
    """Gemini API 키를 설정하고 모델을 초기화합니다."""
    global model
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            print("="*50); print("오류: GEMINI_API_KEY 환경 변수가 없습니다."); print("="*50); exit()
        
        genai.configure(api_key=api_key)
        
        # [수정] 님이 확인하신 'gemini-2.5-flash' 모델을 사용합니다.
        model = genai.GenerativeModel('gemini-2.5-flash') 
        print("Gemini 모델이 성공적으로 설정되었습니다. ('gemini-2.5-flash' 사용)")
        return model
    except Exception as e:
        print(f"오류: API 키 설정에 실패했습니다: {e}"); exit()

def get_summary_from_gemini(tab_titles, window_titles):
    """두 목록을 받아 Gemini에게 요약 JSON을 요청합니다."""
    global model
    if not model:
        print("오류: Gemini 모델이 초기화되지 않았습니다.")
        return []

    prompt = f"""
    당신은 사용자의 작업 목록을 분석하고 그룹화하는 AI 어시턴트입니다.
    사용자의 브라우저 탭 목록과 프로그램 창 목록을 분석하여, 관련 있는 항목끼리 묶어주세요.

    [요구 사항]
    1. 반드시 "JSON 리스트" 형식으로만 응답해야 합니다.
    2. 다른 설명이나 '```json' 같은 마크다운은 절대 포함하지 마세요.
    3. 각 그룹은 'category'(그룹 이름), 'summary'(1줄 요약), 'items'(항목 리스트) 키를 가져야 합니다.
    
    [JSON 형식 예시]
    [
      {{"category": "업무 문서 작업", "summary": "엑셀과 노션으로 문서를 작성 중입니다.", "items": ["보고서.xlsx", "회의록 - Notion"]}},
      {{"category": "소셜 미디어", "summary": "유튜브와 트위터를 보고 있습니다.", "items": ["YouTube", "X.com"]}}
    ]

    [사용자 데이터]
    - 브라우저 탭: {tab_titles}
    - 프로그램 창: {window_titles}

    이제 이 데이터를 분석하여 JSON 리스트를 생성해 주세요:
    """
    print(f"Gemini(Flash 2.5)에게 {len(tab_titles)}개 탭과 {len(window_titles)}개 창의 JSON 그룹핑을 요청합니다...")
    
    ai_response_text = None 
    try:
        # -------------------------------------------------
        # [수정] 15초 타임아웃(request_options) 로직 제거
        # -------------------------------------------------
        response = model.generate_content(prompt)
        ai_response_text = response.text 
        
        text = ai_response_text.strip()
        
        match = re.search(r'\[.*\]|\{.*\}', text, re.DOTALL)
        if match:
            cleaned_json = match.group(0)
        else:
            cleaned_json = text.replace("```json", "").replace("```", "")
        
        return json.loads(cleaned_json)

    # [수정] 타임아웃 예외 블록 제거
    
    except Exception as e:
        print(f"Gemini API 오류 또는 JSON 파싱 오류: {e}")
        if ai_response_text:
            print(f"AI 원본 응답 (파싱 실패): {ai_response_text}")
        return [] # 오류 시 빈 리스트 반환