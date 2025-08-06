
console.log("✅ JavaScript is connected and running!");

const inputArea = document.getElementById("message");
const sendButton = document.getElementById('sendBtn');
const micButton = document.getElementById('micBtn');
const chatbox = document.querySelector('.chat-messages');
const recordedDiv = document.getElementById('recorded');

let recorder = null;
let chunks = [];
let recording = false;
let can_record = false;
let audio_reply = false;

let complaintData = {
  name: '',
  phone: '',
  cnic: '',
  email: '',
  bank: '',
  complaintType: '',
  complaintDescription: ''
};
let lastStep = '';

let originalReviewData = null;

const qrCodeContainer = document.createElement('div');
qrCodeContainer.id = 'qr-code-container';
qrCodeContainer.style.display = 'none';
document.body.appendChild(qrCodeContainer);

function loadQRCodeLibrary() {
  return new Promise((resolve, reject) => {
    if (typeof QRCode !== 'undefined') {
      resolve();
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/qrcode@1.5.1/build/qrcode.min.js';
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

function isUrdu(text) {
  // Urdu characters are mostly in the Unicode range 0600–06FF
  return /[\u0600-\u06FF]/.test(text);
}
function addMessage(role, text) {
  const row = document.createElement('div');
  row.className = `bubble-row ${role}`;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  if (isUrdu(text)) {
    bubble.classList.add('rtl');
  }

  bubble.innerHTML = text;

  row.appendChild(bubble);
  chatbox.appendChild(row);
  chatbox.scrollTop = chatbox.scrollHeight;

  if (role === 'bot' & audio_reply === true) {
    audio_reply = false;
    document.getElementById("interruptBtn").style.display = "block";
    speakText(text);
  }
}

async function sendMessage(text) {
  if (!text.trim()) return;

  // Store the field to update before sending
  const fieldToUpdate = lastStep;

  addMessage("user", text);  // ✅ Show user message
  inputArea.value = "";
  if (text == "1" || text == "2") {
    if (text == "1") {
      document.getElementById("language-selection").dataset.language = "en";
      console.log(document.getElementById("language-selection").dataset.language)
    }
    else if (text == "2") {
      document.getElementById("language-selection").dataset.language = "ur";
    }
  }

  try {
    const res = await fetch("http://127.0.0.1/backend/backend.php", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded"
      },
      body: "message=" + encodeURIComponent(text),
      credentials: "include"
    });

    const reply = await res.text();

    if (!reply.startsWith("Review")) {
      addMessage("bot", reply);

    } else {
      try {
        const jsonStart = reply.indexOf("{");
        const reviewJson = JSON.parse(reply.slice(jsonStart));
        complaintData = reviewJson;
        console.log("📋 Review Data:", complaintData);
        showReviewForm(); // display the form
        return;
      } catch (err) {
        console.error("Failed to parse review JSON:", err);
        addMessage("bot", "⚠️ Review data could not be loaded.");
        return;
      }
    }


  } catch (err) {
    console.error(err);
    addMessage("bot", "⚠️ Error contacting server.");
  }
}

// TTS for bot
function speakText(text) {
  if ('speechSynthesis' in window) {
    document.getElementById("language-selection").display = "block";
    const utter = new SpeechSynthesisUtterance(text);
    const langElement = document.getElementById("language-selection");
    if (langElement) {
      utter.lang = langElement.dataset.language;
    }
    utter.lang = 'en-US';
    window.speechSynthesis.speak(utter);
  }
}

// Event: Send Button
sendButton.addEventListener('click', (e) => {
  e.preventDefault();
  const message = inputArea.value.trim();
  if (message) sendMessage(message);
});

// Optional: Enter Key to Send
inputArea.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendButton.click();
  }
});

function SetupAudio() {
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => SetupStream(stream))
      .catch(err => console.error('Mic access denied:', err));
  }
}

SetupAudio();

function SetupStream(stream) {
  recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });

  recorder.ondataavailable = e => {
    chunks.push(e.data);
  };

  recorder.onstop = () => {
    const blob = new Blob(chunks, { type: 'audio/webm' });
    chunks = [];

    // Reset UI
    micButton.style.backgroundColor = "";
    micButton.style.color = "";
    inputArea.disabled = false;
    inputArea.placeholder = "processing...";

    // Display player
    const audioURL = URL.createObjectURL(blob);
    const audio = document.createElement('audio');
    audio.controls = true;
    audio.src = audioURL;

    recordedDiv.innerHTML = '';
    const audioWrapper = document.createElement('div');
    audioWrapper.style.display = 'flex';
    audioWrapper.style.alignItems = 'center';
    audioWrapper.style.gap = '8px';

    const deleteButton = document.createElement('button');
    deleteButton.className = 'circle-button mic-btn';
    deleteButton.innerHTML = `
      <svg viewBox="0 0 24 24" width="20" height="20" fill="white">
        <path d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
      </svg>
    `;
    deleteButton.title = 'Delete recording';
    deleteButton.onclick = () => {
      recordedDiv.innerHTML = '';
      inputArea.placeholder = "type your message here...";
      resetSendBtnToMessage();
    };

    audioWrapper.appendChild(audio);
    audioWrapper.appendChild(deleteButton);
    recordedDiv.appendChild(audioWrapper);

    // Send for transcription
    const formData = new FormData();
    formData.append("file", blob, "audio.webm");

    fetch("http://127.0.0.1/backend/backend.php", {
      method: "GET",
      credentials: "include"
    })
      .then(response => response.text())
      .then(lang => {
        const selectedLang = lang || "en";
        console.log("🌐 Language:", selectedLang);
        return fetch(`http://127.0.0.1:8000/transcribe?audio=${selectedLang}`, {
          method: "POST",
          body: formData
        });
      })
      .then(response => response.text())
      .then(text => {
        const cleanedText = JSON.parse(text);
        console.log("📩 Transcription:", cleanedText);
        inputArea.value += cleanedText + " ";
        recordedDiv.innerHTML = '';


      })
      .catch(error => {
        console.error("❌ Error during transcription:", error);
      });


  };

  can_record = true;
}

function resetSendBtnToMessage() {
  sendBtn.onclick = async () => {
    const message = inputArea.value.trim();
    if (!message) return;

    // Show user message
    chatbox.innerHTML += `<div class="bubble-row user"><div class="bubble">${message}</div></div>`;
    chatbox.scrollTop = chatbox.scrollHeight;
    inputArea.value = "";

    // Reset sendBtn *immediately* after sending message
    resetSendBtnToMessage();  // So user can send again

    try {
      const replyHTML = await fetch("http://127.0.0.1/backend/backend.php", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded"
        },
        body: "message=" + encodeURIComponent(msg),
        credentials: "include"
      });

      const text = await replyHTML.text();


      // Show bot reply
      chatbox.innerHTML += `<div class="bubble-row bot"><div class="bubble">${text}</div></div>`;
      chatbox.scrollTop = chatbox.scrollHeight;
    } catch (error) {
      console.warn("Fetch failed (likely no PHP):", error);
      // Optional: show fallback bot response
      chatbox.innerHTML += `<div class="bubble-row bot"><div class="bubble">⚠️ Bot not available. Message sent.</div></div>`;
    }
  };

  sendBtn.title = 'Send Message';
}

// Mic button click
micButton.onclick = () => {
  if (!can_record) return;

  recording = !recording;

  if (recording) {
    micButton.style.backgroundColor = "#EBD598";
    recorder.start();
    audio_reply = true;
    // Disable message input + send


    inputArea.placeholder = "Recording...";
  } else {
    micButton.style.backgroundColor = "";
    recorder.stop();
  }
};

// Send message function (standard)
if (sendButton) {
  sendButton.addEventListener('click', () => {
    const messageElement = document.getElementById("message");
    if (messageElement) {
      const message = messageElement.value.trim();
      if (message) {
        sendMessage();
        messageElement.value = "";
      }
    }
  });
} else {
  console.error("❌ Send button not found!");
}

document.getElementById("interruptBtn").addEventListener("click", () => {
  if (speechSynthesis.speaking) {
    speechSynthesis.cancel();
    document.getElementById("interruptBtn").style.display = "none";
    console.log("⛔ Bot speech interrupted by user.");
  }
});


async function generateComplaintQR(userData) {
  try {
    await loadQRCodeLibrary();

    const complaintData = {
      name: userData.name || 'Not provided',
      bank: userData.bank || 'Not provided',
      cnic: userData.cnic ? maskCNIC(userData.cnic) : 'Not provided',
      complaintType: userData.complaintType || 'Not specified',
      complaintDescription: userData.complaintDescription || 'No description',
      timestamp: new Date().toISOString(),
      reference: 'REF-' + Math.random().toString(36).substr(2, 8).toUpperCase()
    };

    const dataString = JSON.stringify(complaintData, null, 2);

    qrCodeContainer.innerHTML = '';
    qrCodeContainer.style.display = 'block';

    new QRCode(qrCodeContainer, {
      text: dataString,
      width: 200,
      height: 200,
      colorDark: "#194224",
      colorLight: "#ffffff",
      correctLevel: QRCode.CorrectLevel.H
    });

    const downloadBtn = document.createElement('button');
    downloadBtn.textContent = 'Download QR Code';
    downloadBtn.className = 'qr-download-btn';
    downloadBtn.onclick = () => downloadQRCode();
    qrCodeContainer.appendChild(downloadBtn);

    addMessage('bot', `Here's your complaint QR code containing all details. Reference: ${complaintData.reference}`);

    const qrRow = document.createElement('div');
    qrRow.className = 'bubble-row bot';
    const qrBubble = document.createElement('div');
    qrBubble.className = 'bubble';
    qrBubble.appendChild(qrCodeContainer.cloneNode(true));
    qrRow.appendChild(qrBubble);
    chatbox.appendChild(qrRow);
    chatbox.scrollTop = chatbox.scrollHeight;

  } catch (error) {
    console.error('Error generating QR code:', error);
    addMessage('bot', 'Failed to generate QR code. Please try again.');
  }
}

function maskCNIC(cnic) {
  if (!cnic) return 'Not provided';
  const parts = cnic.split('-');
  if (parts.length !== 3) return cnic;
  return `${parts[0].substr(0, 2)}XX-XXXXXXX-${parts[2]}`;
}

function downloadQRCode() {
  const canvas = qrCodeContainer.querySelector('canvas');
  if (!canvas) return;

  const link = document.createElement('a');
  link.download = 'complaint_details.png';
  link.href = canvas.toDataURL('image/png');
  link.click();
}

function completeComplaintProcess() {
  const userData = {
    name: "John Doe",
    bank: "SBP",
    cnic: "12345-6789012-3",
    complaintType: "Account Access",
    complaintDescription: "Unable to login to online banking portal since Monday"
  };

  generateComplaintQR(userData);
}

// Validation functions
function validateName(name) {
  return /^[a-zA-Z\s]{2,}$/.test(name);
}
function validatePhone(phone) {
  return /^(03[0-9]{9}|00923[0-9]{9}|\+923[0-9]{9})$/.test(phone);
}
function validateCNIC(cnic) {
  return /^(\d{5}-\d{7}-\d{1}|\d{13})$/.test(cnic);
}

function validateEmail(email) {
  return /^\S+@\S+\.\S+$/.test(email);
}

// Add these arrays for dropdown options
const bankOptions = [
  'Habib Bank Limited',
  'United Bank Limited',
  'Allied Bank Limited',
  'Meezan Bank',
  'Bank Alfalah',
  'MCB Bank',
  'Askari Bank',
  'Faysal Bank',
  'Standard Chartered'
];
const complaintTypeOptions = [
  'Delay in receiving remittance',
  'Remittance not credited',
  'Wrong amount received',
  'Wrong beneficiary details',
  'Exchange rate issue',
  'Deduction without reason',
  'No alert received',
  'Remittance held/blockage',
  'Remittance rejected',
  'Other'
];

function showReviewForm() {
  // Remove any previous review form
  const oldForm = document.getElementById('review-form');
  if (oldForm) oldForm.remove();

  // Map numbers to names if needed before showing the form
  if (/^\d+$/.test(complaintData.bank)) {
    const idx = parseInt(complaintData.bank, 10) - 1;
    if (bankOptions[idx]) complaintData.bank = bankOptions[idx];
  }
  if (/^\d+$/.test(complaintData.complaintType)) {
    const idx = parseInt(complaintData.complaintType, 10) - 1;
    if (complaintTypeOptions[idx]) complaintData.complaintType = complaintTypeOptions[idx];
  }
  // Store a snapshot of the original data for change detection
  originalReviewData = { ...complaintData };


  const formRow = document.createElement('div');
  formRow.className = 'bubble-row bot';
  formRow.id = 'review-form';
  const formBubble = document.createElement('div');
  formBubble.className = 'bubble';
  formBubble.style.width = '100%';

  // Build dropdowns for bank and complaint type
  let bankOptionsHtml = bankOptions.map(opt => `<option value="${opt}"${complaintData.bank === opt ? ' selected' : ''}>${opt}</option>`).join('');
  let complaintTypeMatched = complaintTypeOptions.includes(complaintData.complaintType);
  let complaintTypeOptionsHtml = complaintTypeOptions.map(opt => {
    let selected = complaintData.complaintType === opt ? ' selected' : '';
    return `<option value="${opt}"${selected}>${opt}</option>`;
  }).join('');
  complaintTypeOptionsHtml += `<option value="Other"${!complaintTypeMatched ? ' selected' : ''}>Other</option>`;

  console.log("Complaint Data:", complaintData);
  formBubble.innerHTML = `
  <div style="position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); display:flex; justify-content:center; align-items:center; z-index:1000;">
    <div style="background:white; border-radius:16px; box-shadow:0 4px 20px rgba(0,0,0,0.15); max-width:90%; width:400px; max-height:90vh; overflow-y:auto;">
      <div style="padding:18px; position:relative;">
        <h3 style="margin-top:0; margin-bottom:16px; color:#194224;">Review Your Complaint</h3>
        <form id="complaintReviewForm" style="display:flex; flex-direction:column; gap:14px;">
          <div style="display:flex; flex-direction:column; gap:8px;">
            <label style="font-weight:600; margin-bottom:2px;">Name:
              <input type="text" name="name" value="${complaintData.name}" required style="width:100%; padding:7px 10px; border-radius:6px; border:1px solid #ccc; margin-top:2px;">
            </label>
            <label style="font-weight:600; margin-bottom:2px;">Phone:
              <input type="text" name="phone" value="${complaintData.phone}" required style="width:100%; padding:7px 10px; border-radius:6px; border:1px solid #ccc; margin-top:2px;">
            </label>
            <label style="font-weight:600; margin-bottom:2px;">CNIC:
              <input type="text" name="cnic" value="${complaintData.cnic}" required style="width:100%; padding:7px 10px; border-radius:6px; border:1px solid #ccc; margin-top:2px;">
            </label>
            <label style="font-weight:600; margin-bottom:2px;">Email:
              <input type="email" name="email" value="${complaintData.email}" required style="width:100%; padding:7px 10px; border-radius:6px; border:1px solid #ccc; margin-top:2px;">
            </label>
            <label style="font-weight:600; margin-bottom:2px;">Bank:
              <select name="bank" required style="width:100%; padding:7px 10px; border-radius:6px; border:1px solid #ccc; margin-top:2px;">${bankOptionsHtml}</select>
            </label>
            <label style="font-weight:600; margin-bottom:2px;">Complaint Type:
              <select name="complaintType" id="complaintTypeSelect" required style="width:100%; padding:7px 10px; border-radius:6px; border:1px solid #ccc; margin-top:2px;">${complaintTypeOptionsHtml}</select>
            </label>
            <input type="text" name="customComplaintType" id="customComplaintTypeInput"
       placeholder="Enter complaint type"
       value="${!complaintTypeMatched ? complaintData.complaintType : ''}"
       style="width:100%; padding:7px 10px; border-radius:6px; border:1px solid #ccc; margin-top:8px; display:${!complaintTypeMatched ? 'block' : 'none'};">

            <label style="font-weight:600; margin-bottom:2px;">Description:
              <textarea name="complaintDescription" required style="width:100%; padding:7px 10px; border-radius:6px; border:1px solid #ccc; margin-top:2px; min-height:60px; resize:vertical;">${complaintData.complaintDescription}</textarea>
            </label>
          </div>
          <div id="reviewFormError" style="color:#b00020; font-weight:500; min-height:18px;"></div>
          <button type="submit" style="margin-top:8px; background:#194224; color:#fff; border:none; border-radius:6px; padding:10px 0; font-size:1rem; font-weight:600; cursor:pointer; transition:background 0.2s;">Confirm & Submit</button>
        </form>
      </div>
    </div>
  </div>
`;


  formRow.appendChild(formBubble);
  chatbox.appendChild(formRow);
  chatbox.scrollTop = chatbox.scrollHeight;

  document.getElementById('complaintTypeSelect').addEventListener('change', function () {
  const input = document.getElementById('customComplaintTypeInput');
  if (this.value === 'Other') {
    input.style.display = 'block';
  } else {
    input.style.display = 'none';
    input.value = '';
  }
});
  document.getElementById('complaintReviewForm').onsubmit = async function (e) {
    e.preventDefault();
    // Get values
    const fd = new FormData(this);
    const name = fd.get('name').trim();
    const phone = fd.get('phone').trim();
    const cnic = fd.get('cnic').trim();
    const email = fd.get('email').trim();
    const bank = fd.get('bank').trim();
    let complaintType = fd.get('complaintType').trim();
    if (complaintType === 'Other') {
      const customComplaintType = fd.get('customComplaintType')?.trim();
      if (customComplaintType) complaintType = customComplaintType;
    }

    const complaintDescription = fd.get('complaintDescription').trim();
    // Validate
    let error = '';
    if (!validateName(name)) error = 'Invalid name.';
    else if (!validatePhone(phone)) error = 'Invalid phone.';
    else if (!validateCNIC(cnic)) error = 'Invalid CNIC.';
    else if (!validateEmail(email)) error = 'Invalid email.';
    else if (!bank) error = 'Bank required.';
    else if (!complaintType) error = 'Complaint type required.';
    else if (!complaintDescription) error = 'Description required.';
    if (error) {
      document.getElementById('reviewFormError').textContent = error;
      return;
    }
    // Check if any changes were made
    const isChanged =
      name !== originalReviewData.name ||
      phone !== originalReviewData.phone ||
      cnic !== originalReviewData.cnic ||
      email !== originalReviewData.email ||
      bank !== originalReviewData.bank ||
      complaintType !== originalReviewData.complaintType ||
      complaintDescription !== originalReviewData.complaintDescription;
    // Update complaintData
    complaintData = { name, phone, cnic, email, bank, complaintType, complaintDescription };
    // Send all data to PHP for registration and QR code
    console.log(complaintType);
    try {
      const res = await fetch('http://127.0.0.1/backend/backend.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          name, phone, cnic, email, bank, complaintType, complaintDescription
        }),
        credentials: "include"
      });
      const reply = await res.text();
      // Remove previous QR code bubble if it exists
      const chatRows = chatbox.querySelectorAll('.bubble-row.bot');
      for (let i = chatRows.length - 1; i >= 0; i--) {
        if (chatRows[i].innerHTML.includes('qrcodes/') && chatRows[i].innerHTML.includes('<img')) {
          chatRows[i].remove();
          break;
        }
      }
      addMessage('bot', reply);
      formRow.remove();
      complaintData = { name: '', phone: '', cnic: '', email: '', bank: '', complaintType: '', complaintDescription: '' };
      lastStep = '';
    } catch (err) {
      document.getElementById('reviewFormError').textContent = 'Submission failed. Try again.';
    }
  };
}
