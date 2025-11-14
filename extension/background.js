// background.js

let socket; // WebSocket 연결 객체를 저장할 변수

function connectWebSocket() {
  socket = new WebSocket("ws://localhost:9090");

  socket.onopen = function(e) {
    console.log("[WebSocket] 서버에 연결되었습니다.");
    // 연결되자마자 현재 탭 목록을 가져와서 전송
    sendCurrentTabs();
  };

  // -------------------------------------------------
  // [신규] Python 서버로부터 '명령'을 받는 리스너
  // -------------------------------------------------
  socket.onmessage = function(event) {
    console.log(`[WebSocket] 서버로부터 메시지 수신: ${event.data}`);
    
    try {
      // 1. Python이 보낸 JSON 명령을 파싱
      const command = JSON.parse(event.data);

      // 2. '탭 닫기' 명령인지 확인
      if (command.action === "close_tab" && command.title) {
        console.log(`'${command.title}' 탭 닫기 명령 수신...`);
        
        // 3. 현재 열린 모든 탭을 검색
        chrome.tabs.query({}, function(tabs) {
          // 4. 명령으로 받은 '제목'과 일치하는 탭을 찾음
          const tabToClose = tabs.find(tab => tab.title === command.title);
          
          if (tabToClose) {
            // 5. 탭을 닫음!
            chrome.tabs.remove(tabToClose.id);
            console.log(`'${command.title}' (ID: ${tabToClose.id}) 탭을 닫았습니다.`);
            // 탭을 닫으면 onRemoved 이벤트가 발생하여 
            // 탭 목록이 자동으로 갱신되어 Python으로 전송됩니다.
          } else {
            console.log(`'${command.title}' 탭을 찾을 수 없습니다.`);
          }
        });
      }
      else if (command.action === "activate_tab" && command.title) {
        console.log(`'${command.title}' 탭 이동 명령 수신...`);
        
        chrome.tabs.query({}, function(tabs) {
          // 제목이 일치하는 탭 찾기
          const tabToActivate = tabs.find(tab => tab.title === command.title);
          
          if (tabToActivate) {
            // 1) 해당 탭을 활성화 (Active)
            chrome.tabs.update(tabToActivate.id, { active: true });
            
            // 2) 해당 탭이 있는 브라우저 창 자체를 맨 앞으로 (Focus)
            chrome.windows.update(tabToActivate.windowId, { focused: true });
            
            console.log(`탭 이동 완료.`);
          } else {
            console.log("해당 제목의 탭을 찾을 수 없습니다.");
          }
        });
      }
    } catch (e) {
      console.error("[WebSocket] 서버 메시지 파싱 오류:", e);
    }
  };
  // -------------------------------------------------

  socket.onclose = function(event) {
    console.log("[WebSocket] 연결이 끊겼습니다. 5초 후 재시도합니다.");
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
      // console.log("현재 탭 목록을 서버로 전송합니다."); // (너무 자주 찍히므로 주석 처리)
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
  if (changeInfo.status === 'complete' || changeInfo.title) {
    // console.log("탭 업데이트됨, 목록 갱신"); // (너무 자주 찍히므로 주석 처리)
    sendCurrentTabs();
  }
});

// 확장 프로그램이 처음 로드될 때 WebSocket 연결 시작
connectWebSocket();