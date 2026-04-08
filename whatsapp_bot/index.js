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

function logFlow({ sender, destination, transport }) {
    const parts = [
        '[FLOW]',
        `sender=${sender}`,
        `destination=${destination}`,
        `transport=${transport}`,
    ];

    console.log(parts.join(' '));
}

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

async function enqueueBridge(text, sender) {
    logFlow({
        sender: 'whatsapp_bot',
        destination: 'bot_bridge',
        transport: 'http',
    });

    const response = await axios.post(
        botBridgeUrl,
        { text, sender },
        { timeout: bridgeSubmitTimeoutMs }
    );

    const requestId = response?.data?.request_id;
    if (!requestId) {
        throw new Error('Bridge did not return request_id');
    }

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
                logFlow({
                    sender: 'bot_bridge',
                    destination: 'whatsapp_bot',
                    transport: 'http',
                });
                return response?.data?.reply || '';
            }

            if (status === 'error') {
                throw new Error(response?.data?.error || 'Bridge processing failed');
            }

        } catch (error) {
            if (error.response?.status === 404) {
                throw new Error(`Bridge request_id not found: ${requestId}`);
            }
        }

        await sleep(bridgePollIntervalMs);
    }

    throw new Error(`Bridge poll timed out after ${bridgePollTimeoutMs}ms`);
}

async function processIncomingText(sock, sender, text, key) {
    try {
        const requestId = await enqueueBridge(text, sender);

        try {
            await sock.sendMessage(sender, { react: { text: processingReaction, key } });
        } catch (reactionError) {}

        const reply = await waitForBridgeReply(requestId);

        await sock.sendMessage(sender, { text: reply || 'I finished processing but got an empty response.' });
        logFlow({
            sender: 'whatsapp_bot',
            destination: sender,
            transport: 'whatsapp',
        });
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

    sock.ev.on('messages.upsert', async (m) => {
        const msg = m.messages[0];
        if (!msg?.message || msg.key.remoteJid === 'status@broadcast') return;
        if (msg.key.fromMe) return;

        const sender = msg.key.remoteJid;
        logFlow({
            sender,
            destination: 'whatsapp_bot',
            transport: 'whatsapp',
        });

        if (sender !== targetChatId) return;

        const text = msg.message.conversation || msg.message.extendedTextMessage?.text || '';
        if (!text) return;

        processIncomingText(sock, sender, text, msg.key).catch((error) => {
            console.error('❌ Unexpected message processing error:', error.message);
        });
    });
}

startBot();
