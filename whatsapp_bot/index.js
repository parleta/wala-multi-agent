const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, Browsers, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const pino = require('pino');
const axios = require('axios');

const targetChatId = '120363424923387540@g.us'
const botBridgeUrl = process.env.BOT_BRIDGE_URL || 'http://bot_bridge:8000/chat';

function shortText(text, maxLen = 180) {
    if (!text) return "";
    if (text.length <= maxLen) return text;
    return text.slice(0, maxLen - 3) + "...";
}

async function startBot() {
    const { version } = await fetchLatestBaileysVersion();
    const { state, saveCreds } = await useMultiFileAuthState('auth_info');

    const sock = makeWASocket({
        version,
        auth: state,
        logger: pino({ level: 'silent' }),
        browser: Browsers.macOS('Desktop'),
    });

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;
        if (qr) qrcode.generate(qr, { small: true });
        if (connection === 'open') console.log('✅ WALA Bot is ONLINE');
        if (connection === 'close') {
            if (lastDisconnect.error?.output?.statusCode !== DisconnectReason.loggedOut) startBot();
        }
    });

    sock.ev.on('creds.update', saveCreds);

    // --- MESSAGE PROCESSING (SINGLE CHAT ONLY) ---
    sock.ev.on('messages.upsert', async (m) => {
        const msg = m.messages[0];
        if (!msg.message || msg.key.remoteJid === 'status@broadcast') return;

        if (msg.key.fromMe) return;

        const sender = msg.key.remoteJid;
        
        // --- THE LOCK ---
        // Log the ID so you can copy it from the Docker terminal
        console.log(`[DEBUG] Message from: ${sender}`);

        if (sender !== targetChatId) return; // Ignore everyone else!

        const text = msg.message.conversation || msg.message.extendedTextMessage?.text || "";

        if (text.length > 0) {
            console.log(`[AGENT] Processing: ${text}`);
            
            try {
                console.log(`[BOT] -> bridge: ${shortText(text)}`);
                const response = await axios.post(botBridgeUrl, {
                    text: text,
                    sender: sender
                });

                console.log(`[BOT] <- bridge reply: ${shortText(response?.data?.reply || "")}`);
                await sock.sendMessage(sender, { text: response.data.reply });
                console.log(`[BOT] -> WhatsApp message sent`);
            } catch (error) {
                console.error("❌ Agent Error:", error.message);
            }
        }
    });
}
startBot();
