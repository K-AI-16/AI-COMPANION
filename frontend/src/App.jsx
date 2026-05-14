import { useState, useRef, useEffect } from "react";

const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY || "";

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

const isPushSupported = "serviceWorker" in navigator && "PushManager" in window;

const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);

const NUDGE_DELAY_MS = {
  playful:    2 * 60 * 1000,
  engaged:    3 * 60 * 1000,
  neutral:    3 * 60 * 1000,
  practical:  4 * 60 * 1000,
  vulnerable: 5 * 60 * 1000,
};

function App() {
  const [userId] = useState(() => {
    let id = localStorage.getItem("ari_user_id");
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem("ari_user_id", id);
    }
    return id;
  });

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [shouldAskNotifications, setShouldAskNotifications] = useState(false);
  const shouldAskNotificationsRef = useRef(false);

  const bottomRef = useRef(null);
  const notificationAskInjectedRef = useRef(false);

  // Type 2: mid-session nudge
  const conversationStateRef = useRef("neutral");
  const nudgeTimerRef = useRef(null);
  const nudgeSentRef = useRef(false);

  // Type 3: boredom pivot
  const boredCountRef = useRef(0);
  const pivotSentRef = useRef(false);
  const pivotTimerRef = useRef(null);

  // ---------------------------
  // Helpers
  // ---------------------------

  const wait = (ms) => new Promise((res) => setTimeout(res, ms));

  const getDelay = (text) => Math.min(1400, 300 + text.length * 18);

  const formatTime = (date) =>
    date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  const handleBotReply = async (reply, isFirst = true) => {
    await wait(isFirst ? 400 + Math.random() * 600 : 150 + Math.random() * 150);
    setIsTyping(true);
    await wait(getDelay(reply));
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: reply, time: formatTime(new Date()) },
    ]);
    setIsTyping(false);
  };

  // ---------------------------
  // Push Subscription
  // ---------------------------

  const subscribeToNotifications = async () => {
    setShouldAskNotifications(false);
    shouldAskNotificationsRef.current = false;

    if (isIOS) {
      // iOS only supports push in Safari PWAs — show a one-time instruction bubble
      await wait(400);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "on iPhone you'll need to open this in Safari, tap Share → Add to Home Screen, then reopen from there to enable notifications.",
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
      return;
    }

    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") return;
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
      });
      await fetch("/v1/push/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, subscription: sub.toJSON() }),
      });
    } catch (e) {
      console.error("Push subscribe failed:", e);
    }
  };

  const dismissNotificationAsk = () => {
    setShouldAskNotifications(false);
    shouldAskNotificationsRef.current = false;
  };

  // ---------------------------
  // Send Message
  // ---------------------------

  const sendMessage = async () => {
    if (!input.trim()) return;

    const currentInput = input;
    setMessages((prev) => [
      ...prev,
      { role: "user", content: currentInput, time: formatTime(new Date()) },
    ]);
    setInput("");

    // User replied — reset nudge and pivot cycles
    nudgeSentRef.current = false;
    if (nudgeTimerRef.current) clearTimeout(nudgeTimerRef.current);
    if (pivotTimerRef.current) {
      clearTimeout(pivotTimerRef.current);
      pivotSentRef.current = false;  // user is still talking, allow pivot to re-arm
    }

    try {
      await wait(800 + Math.random() * 600);

      const res = await fetch("/v1/chat/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, message: currentInput }),
      });

      const data = await res.json();
      const state = data.conversation_state || "neutral";
      conversationStateRef.current = state;

      const replies = data.replies || [data.reply];
      for (let i = 0; i < replies.length; i++) {
        await handleBotReply(replies[i], i === 0);
      }

      // Re-check push status if we haven't asked yet (handles new users who gain 6+ messages mid-session)
      if (isPushSupported && !shouldAskNotificationsRef.current && !notificationAskInjectedRef.current) {
        try {
          const statusRes = await fetch(`/v1/push/status/${userId}`);
          const statusData = await statusRes.json();
          if (statusData.should_ask) {
            shouldAskNotificationsRef.current = true;
            setShouldAskNotifications(true);
          }
        } catch (_) {}
      }

      // Inject notification ask after first Ari reply this session
      if (shouldAskNotificationsRef.current && !notificationAskInjectedRef.current) {
        notificationAskInjectedRef.current = true;
        await wait(1200 + Math.random() * 800);
        setMessages((prev) => [
          ...prev,
          {
            role: "notification_ask",
            content: "hey — I can send you a nudge even when you're not here. want me to set that up?",
            time: formatTime(new Date()),
          },
        ]);
      }

      // Boredom tracking for pivot (type 3)
      // disengaged counts double — it's a stronger signal than just neutral
      if (state === "disengaged") {
        boredCountRef.current += 2;
      } else if (state === "neutral") {
        boredCountRef.current += 1;
      } else {
        boredCountRef.current = 0;
        pivotSentRef.current = false;
      }

      if (boredCountRef.current >= 3 && !pivotSentRef.current) {
        pivotSentRef.current = true;
        pivotTimerRef.current = setTimeout(async () => {
          try {
            const pivotRes = await fetch("/v1/chat/pivot", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ user_id: userId }),
            });
            const pivotData = await pivotRes.json();
            if (!pivotData.skip && pivotData.message) {
              await wait(800 + Math.random() * 1200);
              await handleBotReply(pivotData.message);
              boredCountRef.current = 0;
            }
          } catch (err) {
            console.error("Pivot error:", err);
          }
        }, 6000 + Math.random() * 4000);
      }
    } catch (error) {
      console.error("Error:", error);
      setIsTyping(false);
    }
  };

  // ---------------------------
  // Auto Scroll
  // ---------------------------

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  // ---------------------------
  // Load Chat History on Mount
  // ---------------------------

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const res = await fetch(`/v1/chat/history/${userId}?limit=30`);
        const data = await res.json();
        if (data && data.length > 0) {
          setMessages(
            data.map((m) => ({
              role: m.role,
              content: m.content,
              time: m.created_at
                ? formatTime(new Date(m.created_at))
                : "",
            }))
          );
        }
      } catch (err) {
        console.error("History load error", err);
      }
    };
    loadHistory();
  }, [userId]);

  // ---------------------------
  // Service Worker + Push Status
  // ---------------------------

  useEffect(() => {
    if (!isPushSupported) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {});

    fetch(`/v1/push/status/${userId}`)
      .then((r) => r.json())
      .then((d) => { if (d.should_ask) { setShouldAskNotifications(true); shouldAskNotificationsRef.current = true; } })
      .catch(() => {});
  }, [userId]);

  // ---------------------------
  // Proactive Polling (type 1 — out-of-session triggers)
  // ---------------------------

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/v1/triggers/${userId}`);
        const data = await res.json();
        if (!data || data.length === 0) return;
        // A proactive trigger arrived — suppress nudge so they don't stack
        nudgeSentRef.current = true;
        if (nudgeTimerRef.current) clearTimeout(nudgeTimerRef.current);
        for (let t of data) {
          await wait(800 + Math.random() * 800);
          await handleBotReply(t.message);
        }
      } catch (err) {
        console.error("Polling error", err);
      }
    }, 7000);

    return () => clearInterval(interval);
  }, []);

  // ---------------------------
  // Nudge Timer (type 2 — mid-session quiet)
  // ---------------------------

  useEffect(() => {
    const lastMsg = messages[messages.length - 1];
    if (!lastMsg || lastMsg.role !== "assistant") return;
    if (nudgeSentRef.current) return;

    const state = conversationStateRef.current;
    if (state === "disengaged" || state === "rude") return;

    if (nudgeTimerRef.current) clearTimeout(nudgeTimerRef.current);

    const delay = NUDGE_DELAY_MS[state] ?? 3 * 60 * 1000;

    nudgeTimerRef.current = setTimeout(async () => {
      if (nudgeSentRef.current) return;
      nudgeSentRef.current = true;
      try {
        const res = await fetch("/v1/chat/nudge", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: userId,
            conversation_state: conversationStateRef.current,
          }),
        });
        const data = await res.json();
        if (!data.skip && data.message) {
          await wait(600 + Math.random() * 600);
          await handleBotReply(data.message);
        }
      } catch (err) {
        console.error("Nudge error:", err);
      }
    }, delay);

    return () => clearTimeout(nudgeTimerRef.current);
  }, [messages]);

  // ---------------------------
  // Render
  // ---------------------------

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.avatar} />
        <div>
          <div style={styles.headerName}>Ari</div>
          <div style={styles.headerSub}>always here</div>
        </div>
      </div>

      {/* Chat */}
      <div style={styles.chatBox}>
        {messages.map((msg, idx) => {
          if (msg.role === "notification_ask") {
            return (
              <div key={idx} style={{ alignSelf: "flex-start", maxWidth: "80%" }}>
                <div style={{ ...styles.message, background: "#e8e7f0", color: "#1a1a2e" }}>
                  {msg.content}
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 6, marginLeft: 4 }}>
                  <button onClick={subscribeToNotifications} style={styles.notifBtn}>
                    yes please
                  </button>
                  <button onClick={dismissNotificationAsk} style={{ ...styles.notifBtn, background: "transparent", color: "#9b98b0", border: "1px solid #dddce8" }}>
                    maybe later
                  </button>
                </div>
                {msg.time && <div style={styles.timestamp}>{msg.time}</div>}
              </div>
            );
          }
          return (
          <div
            key={idx}
            style={{
              alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
              display: "flex",
              flexDirection: "column",
              alignItems: msg.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "80%",
            }}
          >
            <div
              style={{
                ...styles.message,
                background: msg.role === "user" ? "#007bff" : "#e8e7f0",
                color: msg.role === "user" ? "white" : "#1a1a2e",
              }}
            >
              {msg.content}
            </div>
            {msg.time && (
              <div style={styles.timestamp}>{msg.time}</div>
            )}
          </div>
          );
        })}

        {isTyping && (
          <div style={styles.typingBubble}>
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={styles.inputContainer}>
        <input
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            if (nudgeTimerRef.current) clearTimeout(nudgeTimerRef.current);
          }}
          placeholder="Type a message..."
          style={styles.input}
          onKeyDown={(e) => {
            if (e.key === "Enter") sendMessage();
          }}
        />
        <button onClick={sendMessage} style={styles.button}>
          Send
        </button>
      </div>
    </div>
  );
}

// ---------------------------
// Styles
// ---------------------------

const styles = {
  container: {
    height: "100dvh",
    display: "flex",
    flexDirection: "column",
    background: "#f0eff5",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "12px 16px",
    background: "white",
    borderBottom: "1px solid #e0dff0",
    flexShrink: 0,
  },
  avatar: {
    width: 38,
    height: 38,
    borderRadius: "50%",
    background: "#aa3bff",
    flexShrink: 0,
  },
  headerName: {
    fontWeight: "600",
    fontSize: "16px",
    color: "#1a1a2e",
    lineHeight: 1.2,
  },
  headerSub: {
    fontSize: "12px",
    color: "#9b98b0",
    marginTop: 1,
  },
  chatBox: {
    padding: "16px 12px",
    display: "flex",
    flexDirection: "column",
    gap: 6,
    overflowY: "auto",
    flex: 1,
  },
  message: {
    padding: "10px 14px",
    borderRadius: "18px",
    fontSize: "15px",
    wordWrap: "break-word",
    lineHeight: "1.45",
  },
  timestamp: {
    fontSize: "11px",
    color: "#9b98b0",
    marginTop: 3,
    marginLeft: 4,
    marginRight: 4,
  },
  typingBubble: {
    alignSelf: "flex-start",
    background: "#e8e7f0",
    padding: "12px 16px",
    borderRadius: "18px",
    display: "flex",
    alignItems: "center",
    gap: 2,
  },
  inputContainer: {
    display: "flex",
    padding: "10px 12px",
    paddingBottom: "calc(10px + env(safe-area-inset-bottom, 0px))",
    borderTop: "1px solid #e0dff0",
    background: "white",
  },
  input: {
    flex: 1,
    padding: "10px 14px",
    borderRadius: 22,
    border: "1px solid #dddce8",
    outline: "none",
    fontSize: "16px",
    background: "#f7f6fc",
    color: "#1a1a2e",
  },
  button: {
    marginLeft: 10,
    padding: "10px 18px",
    borderRadius: 22,
    border: "none",
    background: "#aa3bff",
    color: "white",
    cursor: "pointer",
    fontSize: "15px",
    fontWeight: "500",
  },
  notifBtn: {
    padding: "6px 14px",
    borderRadius: 16,
    border: "none",
    background: "#aa3bff",
    color: "white",
    cursor: "pointer",
    fontSize: "13px",
    fontWeight: "500",
  },
};

export default App;
