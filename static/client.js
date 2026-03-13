// --- Global Variables ---
let localStream;
let ws;
let peerConnection; 
let remotePeerId;
let searchTimeout;
let appState = 'ready'; 
let currentFacingMode = 'user'; // 'user' = Front, 'environment' = Back

// Google STUN servers
const rtcConfig = {
    iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
};

// --- Cookie Helpers ---
function setCookie(name, value, days) {
    let expires = "";
    if (days) {
        const date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "") + expires + "; path=/; SameSite=Lax";
}

function getCookie(name) {
    const nameEQ = name + "=";
    const ca = document.cookie.split(';');
    for(let i=0;i < ca.length;i++) {
        let c = ca[i];
        while (c.charAt(0)==' ') c = c.substring(1,c.length);
        if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
    }
    return null;
}

// --- 1. Initialization ---
async function initApp() {
    await startCamera(); // 1. Get Video
    connectWebSocket();  // 2. Connect to Server
}

// --- 2. Camera Logic (Robust) ---
async function startCamera() {
    try {
        // Stop old tracks if they exist (to free up hardware)
        if (localStream) {
            localStream.getTracks().forEach(track => track.stop());
        }

        // Check for multiple cameras to show Swap Button
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = devices.filter(device => device.kind === 'videoinput');
        if (videoDevices.length > 1) {
            const swapBtn = document.getElementById("swapBtn");
            if (swapBtn) swapBtn.style.display = "block";
        }

        // Get Stream
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: currentFacingMode },
            audio: true
        });
        
        localStream = stream;
        
        // Setup Local Video Element
        const localVid = document.getElementById("localVideo");
        localVid.srcObject = stream;
        localVid.muted = true; // Prevent echo

        updateStatus("Camera Ready");
        
    } catch (err) {
        console.error("Error accessing camera:", err);
        showToast("Camera blocked! Please allow permissions.", "error");
        updateStatus("Error: Camera Blocked");
    }
}

// --- 3. Switch Camera Logic (The Fix) ---
async function switchCamera() {
    console.log("Attempting camera swap...");
    
    // 1. Capture Current Mic State CAREFULLY
    let shouldBeEnabled = true; // Default to ON
    if (localStream && localStream.getAudioTracks().length > 0) {
        shouldBeEnabled = localStream.getAudioTracks()[0].enabled;
    }
    console.log("Mic state before swap (Enabled?):", shouldBeEnabled);

    // 2. Determine Target Mode
    const targetMode = (currentFacingMode === 'user') ? 'environment' : 'user';
    
    // 3. STOP current tracks to release hardware
    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
    }

    try {
        // 4. Request New Stream
        const newStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: targetMode },
            audio: true // We must request audio again
        });

        // 5. [CRITICAL FIX] Apply the state IMMEDIATELY to the new track
        const newAudioTrack = newStream.getAudioTracks()[0];
        if (newAudioTrack) {
            newAudioTrack.enabled = shouldBeEnabled; // Force it to match old state
            console.log("New audio track enabled state set to:", newAudioTrack.enabled);
        }

        // 6. Update Global Variables
        currentFacingMode = targetMode;
        localStream = newStream;
        
        // 7. Update Local Video Element
        const localVid = document.getElementById("localVideo");
        localVid.srcObject = newStream;
        localVid.muted = true; // Keep local echo off

        // 8. Update WebRTC Connection
        if (peerConnection) {
            // Replace Video
            const newVideoTrack = newStream.getVideoTracks()[0];
            const videoSender = peerConnection.getSenders().find(s => s.track.kind === 'video');
            if (videoSender) {
                await videoSender.replaceTrack(newVideoTrack);
            }
            
            // Replace Audio
            const audioSender = peerConnection.getSenders().find(s => s.track.kind === 'audio');
            if (audioSender && newAudioTrack) {
                await audioSender.replaceTrack(newAudioTrack);
            }
        }
        
        // 9. [UI SYNC] Force the UI buttons to match the reality
        // This ensures if the track is muted, the red icon is definitely shown
        syncMicUI(shouldBeEnabled);

    } catch (err) {
        console.error("Swap Failed:", err);
        showToast("Camera swap failed.", "error");

        // Fallback: Restore old camera
        try {
            const oldStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: currentFacingMode },
                audio: true
            });
            // Restore mic state on fallback
            if (oldStream.getAudioTracks().length > 0) {
                oldStream.getAudioTracks()[0].enabled = shouldBeEnabled;
            }
            localStream = oldStream;
            document.getElementById("localVideo").srcObject = oldStream;
            syncMicUI(shouldBeEnabled); // Sync UI on fallback too
        } catch (recoverErr) {
            console.error("Critical: Could not recover camera", recoverErr);
            showToast("Camera lost. Please refresh.", "error");
        }
    }
}

// Helper function to force UI to match state
function syncMicUI(isEnabled) {
    const btn = document.getElementById("micBtn");
    const iconUnmuted = document.getElementById("icon-unmuted");
    const iconMuted = document.getElementById("icon-muted");
    
    if(!btn || !iconUnmuted || !iconMuted) return;

    if (isEnabled) {
        btn.classList.remove("muted");
        iconUnmuted.style.display = "block";
        iconMuted.style.display = "none";
    } else {
        btn.classList.add("muted");
        iconUnmuted.style.display = "none";
        iconMuted.style.display = "block";
    }
}

// --- 4. WebSocket Connection ---
function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const existingToken = getCookie("strangersync_uid");
    var wsUrl = `${protocol}://${window.location.host}/ws`;

    if (existingToken) {
        wsUrl += `?token=${existingToken}`;
    }

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log("WS Connected");
        updateStatus("Ready");
        updateStatusUI("ready");
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleServerMessage(data);
    };

    ws.onclose = () => {
        updateStatus("Disconnected");
        updateStatusUI("disconnected");
        // Optional: Auto-reconnect logic could go here
    };
}

// --- 5. Message Handling ---
async function handleServerMessage(data) {
    switch (data.status) {
        case "identity":
            console.log("Identity confirmed:", data.user_id);
            setCookie("strangersync_uid", data.user_id, 30);
            break;

        case "waiting":
            updateStatus("Looking for someone...");
            updateStatusUI("searching");
            toggleButtons("searching");
            
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                updateStatus("No users found. Retry?");
                updateStatusUI("ready");
                toggleButtons("ready");
            }, 30000);
            break;
            
        case "matched":
            clearTimeout(searchTimeout);
            remotePeerId = data.peer_id;
            updateStatus("Matched!");
            updateStatusUI("matched");
            toggleButtons("matched");
            
            if (data.initiator) {
                createPeerConnection();
                createOffer();
            } else {
                createPeerConnection();
            }
            break;

        case "signal":
            handleSignal(data.payload);
            break;

        case "peer_left":
            updateStatus("Stranger left. Searching...");
            updateStatusUI("searching");
            toggleButtons("searching");

            closeConnection();
            addChatMessage("system", "Stranger disconnected.");
            
            setTimeout(() => {
                startSearch();
            }, 1500); 
            break;

        case "chat":
            addChatMessage(data.sender, data.msg);
            break;
    }
}

// --- 6. WebRTC Logic ---
function createPeerConnection() {
    peerConnection = new RTCPeerConnection(rtcConfig);

    localStream.getTracks().forEach(track => {
        peerConnection.addTrack(track, localStream);
    });

    peerConnection.ontrack = (event) => {
        const remoteVid = document.getElementById("remoteVideo");
        if (remoteVid.srcObject !== event.streams[0]) {
            remoteVid.srcObject = event.streams[0];
            console.log("Remote video received");
        }
    };

    peerConnection.onicecandidate = (event) => {
        if (event.candidate) {
            sendSignal({ type: "candidate", candidate: event.candidate });
        }
    };
}

async function createOffer() {
    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);
    sendSignal({ type: "offer", sdp: offer });
}

async function createAnswer(offerSDP) {
    await peerConnection.setRemoteDescription(new RTCSessionDescription(offerSDP));
    const answer = await peerConnection.createAnswer();
    await peerConnection.setLocalDescription(answer);
    sendSignal({ type: "answer", sdp: answer });
}

async function handleSignal(payload) {
    if (!peerConnection) createPeerConnection();

    if (payload.type === "offer") {
        await createAnswer(payload.sdp);
    } else if (payload.type === "answer") {
        await peerConnection.setRemoteDescription(new RTCSessionDescription(payload.sdp));
    } else if (payload.type === "candidate") {
        await peerConnection.addIceCandidate(new RTCIceCandidate(payload.candidate));
    }
}

function sendSignal(payload) {
    if(ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            action: "signal",
            target: remotePeerId,
            payload: payload
        }));
    }
}

function closeConnection() {
    if (peerConnection) {
        peerConnection.close();
        peerConnection = null;
    }
    document.getElementById("remoteVideo").srcObject = null;
    remotePeerId = null;
}

// --- 7. UI & Interaction ---

function startSearch() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        toggleButtons('searching');
        const chatBox = document.getElementById("chatBox");
        if(chatBox) chatBox.innerHTML = '<div class="system-msg">Matches are random. Be kind! 👋</div>';
        
        ws.send(JSON.stringify({ action: "find_match" }));
    } else {
        showToast("Server disconnected. Reloading...", "error"); 
        setTimeout(() => location.reload(), 2000);
    }
}

function nextMatch() {
    closeConnection();
    toggleButtons('searching');
    updateStatus("Skipping...");
    const chatBox = document.getElementById("chatBox");
    if(chatBox) chatBox.innerHTML = '<div class="system-msg">Matches are random. Be kind! 👋</div>';
    ws.send(JSON.stringify({ action: "find_match" }));
}

function sendChat() {
    const input = document.getElementById("msgInput");
    const text = input.value.trim();
    if (!text) return;
    if (!remotePeerId) {
        showToast("Wait for a match first!", "info");
        return;
    }

    ws.send(JSON.stringify({ action: "chat", msg: text }));
    input.value = "";
    input.focus(); 
}

function addChatMessage(sender, text) {
    const chatBox = document.getElementById("chatBox");
    if(!chatBox) return;

    const div = document.createElement("div");
    
    if (sender === "me") div.className = "msg me";
    else if (sender === "peer") div.className = "msg peer";
    else div.className = "system-msg";
    
    div.innerText = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Helper to toggle Status Colors
function updateStatusUI(state) {
    const dot = document.getElementById("status-dot");
    if (!dot) return; 

    if (state === "ready") {
        dot.style.background = "#999";
        dot.style.boxShadow = "none";
    } else if (state === "searching") {
        dot.style.background = "#f1c40f"; 
        dot.style.boxShadow = "0 0 8px #f1c40f";
    } else if (state === "matched") {
        dot.style.background = "#2ecc71"; 
        dot.style.boxShadow = "0 0 8px #2ecc71";
    } else if (state === "disconnected") {
        dot.style.background = "#e74c3c"; 
    }
}

// Helper to toggle Buttons
function toggleButtons(state) {
    appState = state;
    const btn = document.getElementById("actionBtn");
    if(!btn) return;

    if (state === 'ready') {
        btn.innerText = "Find Match";
        btn.className = "btn btn-primary";
        btn.disabled = false;
        btn.style.opacity = "1";
    } 
    else if (state === 'searching') {
        btn.innerText = "Searching...";
        btn.className = "btn btn-primary";
        btn.disabled = true;
        btn.style.opacity = "0.7";
    } 
    else if (state === 'matched') {
        btn.innerText = "Skip ⏭";
        btn.className = "btn btn-danger";
        btn.disabled = false;
        btn.style.opacity = "1";
    }
}

function updateStatus(text) {
    const el = document.getElementById("status");
    if (el) el.innerText = text;
}

function toggleMic() {
    if (!localStream) return;
    
    const audioTrack = localStream.getAudioTracks()[0];
    
    if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        
        const btn = document.getElementById("micBtn");
        const iconUnmuted = document.getElementById("icon-unmuted");
        const iconMuted = document.getElementById("icon-muted");
        
        if (audioTrack.enabled) {
            btn.classList.remove("muted");
            iconUnmuted.style.display = "block";
            iconMuted.style.display = "none";
        } else {
            btn.classList.add("muted");
            iconUnmuted.style.display = "none";
            iconMuted.style.display = "block";
        }
    }
}

function toggleChatLayout() {
    document.body.classList.toggle("chat-hidden");
}

function handleAction() {
    if (appState === 'ready' || appState === 'searching') {
        startSearch();
    } else if (appState === 'matched') {
        nextMatch();
    }
}

function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if(!container) return;
    
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    
    let icon = "info";
    if (type === "error") icon = "error";
    if (type === "success") icon = "check_circle";
    
    toast.innerHTML = `
        <span class="material-symbols-rounded">${icon}</span>
        <span>${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("hide");
        toast.addEventListener("animationend", () => {
            toast.remove();
        });
    }, 3000);
}

// Start App
initApp();