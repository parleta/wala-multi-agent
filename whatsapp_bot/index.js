const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, Browsers, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const pino = require('pino');
const axios = require('axios');

const targetChatId = '120363424923387540@g.us';
const botBridgeUrl = process.env.BOT_BRIDGE_URL || 'http://bot_bridge:8000/chat';
const botBridgeResultBaseUrl = process.env.BOT_BRIDGE_RESULT_URL || `${botBridgeUrl.replace(/\/chat\/?$/, '')}/chat/result`;

const bridgeSubmitTimeoutMs = Number(process.env.BRIDGE_SUBMIT_TIMEOUT_MS || '5000');
const bridgePollIntervalMs = Number(process.env.BRIDGE_POLL_INTERVAL_MS || '1500');
const bridgePollTimeoutMs = Number(process.env.BRIDGE_POLL_TIMEOUT_MS || '90000');
const processingReaction = process.env.BRIDGE_PROCESSING_REACTION || '👍';

function shortText(text, maxLen = 180) {
    if (!text) return '';
    if (text.length <= maxLen) return text;
    return text.slice(0, maxLen - 3) + '...';
}

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

async function enqueueBridge(text, sender) {
    console.log(`[BOT] -> bridge(queue): ${shortText(text)}`);
    const response = await axios.post(
        botBridgeUrl,
        { text, sender },
        { timeout: bridgeSubmitTimeoutMs }
    );

    const requestId = response?.data?.request_id;
    if (!requestId) {
        throw new Error('Bridge did not return request_id');
    }

    console.log(`[BOT] <- bridge queued request_id=${requestId}`);
    return requestId;
}

async function waitForBridgeReply(requestId) {
    const deadline = Date.now() + bridgePollTimeoutMs;

    while (Date.now() < deadline) {
        const resultUrl = `${botBridgeResultBaseUrl}/${encodeURIComponent(requestId)}`;

        try {
            const response = await axios.get(resultUrl, { timeout: bridgeSubmitTimeoutMs });
            const status = response?.data?.status;

            if (status === 'done') {
                return response?.data?.reply || '';
            }

            if (status === 'error') {
                throw new Error(response?.data?.error || 'Bridge processing failed');
            }

            console.log(`[BOT] poll request_id=${requestId} status=${status || 'unknown'}`);
        } catch (error) {
            if (error.response?.status === 404) {
                throw new Error(`Bridge request_id not found: ${requestId}`);
            }

            // Transient polling errors should not instantly fail the user flow.
            console.log(`[BOT] poll transient error request_id=${requestId}: ${error.message}`);
        }

        await sleep(bridgePollIntervalMs);
    }

    throw new Error(`Bridge poll timed out after ${bridgePollTimeoutMs}ms`);
}

async function processIncomingText(sock, sender, text, key) {
    console.log(`[AGENT] Processing: ${text}`);

    try {
        const requestId = await enqueueBridge(text, sender);

        try {
            await sock.sendMessage(sender, { react: { text: processingReaction, key } });
            console.log(`[BOT] -> WhatsApp reaction sent request_id=${requestId}`);
        } catch (reactionError) {
            console.log(`[BOT] reaction failed request_id=${requestId}: ${reactionError.message}`);
        }

        const reply = await waitForBridgeReply(requestId);
        console.log(`[BOT] <- bridge final reply: ${shortText(reply)}`);

        await sock.sendMessage(sender, { text: reply || 'I finished processing but got an empty response.' });
        console.log('[BOT] -> WhatsApp final message sent');
    } catch (error) {
        console.error('❌ Agent Error:', error.message);
        await sock.sendMessage(sender, {
            text: 'I am having trouble completing this request right now. Please try again in a moment.',
        });
    }
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
        if (!msg?.message || msg.key.remoteJid === 'status@broadcast') return;
        if (msg.key.fromMe) return;

        const sender = msg.key.remoteJid;
        console.log(`[DEBUG] Message from: ${sender}`);

        if (sender !== targetChatId) return;

        const text = msg.message.conversation || msg.message.extendedTextMessage?.text || '';
        if (!text) return;

        // Run per-message flow asynchronously so incoming events remain responsive.
        processIncomingText(sock, sender, text, msg.key).catch((error) => {
            console.error('❌ Unexpected message processing error:', error.message);
        });
    });
}

startBot();
