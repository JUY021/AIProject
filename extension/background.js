let socket; // WebSocket 연결 객체를 저장할 변수

function connectWebSocket() {
  // Python 서버의 주소 (ws:// = WebSocket 프로토콜)
  socket = new WebSocket("ws://localhost:9090");

  socket.onopen = function(e) {
    console.log("[WebSocket] 서버에 연결되었습니다.");
    // 연결되자마자 현재 탭 목록을 가져와서 전송
    sendCurrentTabs();
  };

  socket.onmessage = function(event) {
    // ----------------------------------------------------
    // 4단계: Python(Gemini)으로부터 받은 요약/그룹화 결과를 처리
    // ----------------------------------------------------
    console.log(`[WebSocket] 서버로부터 메시지 수신: ${event.data}`);
  };

  socket.onclose = function(event) {
    console.log("[WebSocket] 연결이 끊겼습니다. 5초 후 재시도합니다.");
    // 연결이 끊기면 5초 뒤에 다시 연결 시도
    setTimeout(connectWebSocket, 5000);
  };

  socket.onerror = function(error) {
    console.error(`[WebSocket] 오류 발생: ${error.message}`);
  };
}

// 현재 탭 목록을 가져와서 WebSocket으로 전송하는 함수
function sendCurrentTabs() {
  if (socket && socket.readyState === WebSocket.OPEN) {
    chrome.tabs.query({}, function(tabs) {
      console.log("현재 탭 목록을 서버로 전송합니다.");
      // 탭 목록(JSON 객체)을 문자열로 변환하여 전송
      socket.send(JSON.stringify(tabs));
    });
  } else {
    console.log("WebSocket이 아직 연결되지 않았습니다.");
  }
}

// -- 이벤트 리스너 --

// 탭이 생성될 때마다 최신 목록 전송
chrome.tabs.onCreated.addListener(function(tab) {
  console.log("새 탭 열림, 목록 갱신");
  sendCurrentTabs();
});

// 탭이 닫힐 때마다 최신 목록 전송
chrome.tabs.onRemoved.addListener(function(tabId, removeInfo) {
  console.log("탭 닫힘, 목록 갱신");
  sendCurrentTabs();
});

// 탭 정보가 업데이트될 때 (예: 페이지 로딩 완료)
chrome.tabs.onUpdated.addListener(function(tabId, changeInfo, tab) {
  if (changeInfo.status === 'complete') {
    console.log("탭 업데이트됨, 목록 갱신");
    sendCurrentTabs();
  }
});

// 확장 프로그램이 처음 로드될 때 WebSocket 연결 시작
connectWebSocket();