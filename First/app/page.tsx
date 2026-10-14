'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sidebar } from '@/components/sidebar';
import { ChatMessage } from '@/components/chat-message';
import { ChatInput } from '@/components/chat-input';
import { VideoInput } from '@/components/video-input';
import { Trash2 } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatState {
  id: string;
  video_id:     string | null;
  videoTitle:   string | null;
  channel_name: string | null;
  thumbnail:    string | null;
  messages: Message[];
}

export default function Page() {
  const [chatStates, setChatStates] = useState<Record<string, ChatState>>(() => {
    if (typeof window === 'undefined') return {};
    try {
      const saved = localStorage.getItem('yt-rag-chats');
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });
  const [currentChatId, setCurrentChatId] = useState<string | null>(() => {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('yt-rag-current-chat') || null;
});
  const [isLoadingVideo, setIsLoadingVideo]         = useState(false);
  const [isLoadingResponse, setIsLoadingResponse]   = useState(false);
  const [videoError, setVideoError]                 = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const messagesEndRef     = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
  setMounted(true);
}, []);
  // ── Persist chatStates to localStorage on every change ───────────────────
  useEffect(() => {
    localStorage.setItem('yt-rag-chats', JSON.stringify(chatStates));
  }, [chatStates]);

  // ── Bootstrap: select most recent chat or create a new one ───────────────
  useEffect(() => {
    if (!currentChatId) {
      const existingIds = Object.keys(chatStates);
      if (existingIds.length > 0) {
        // Resume the most recent chat
        const latest = existingIds.sort((a, b) => Number(b) - Number(a))[0];
        setCurrentChatId(latest);
      } else {
        // First ever launch — create a blank chat
        const id = Date.now().toString();
        setChatStates((prev) => ({
          ...prev,
          [id]: { id, video_id: null, videoTitle: null, channel_name: null, thumbnail: null, messages: [] },
        }));
        setCurrentChatId(id);
      }
    }
  }, [currentChatId]);

  useEffect(() => {
  if (currentChatId) {
    localStorage.setItem('yt-rag-current-chat', currentChatId);
  }
  }, [currentChatId]);

  // ── Smart auto-scroll: only when already near the bottom ─────────────────
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const isNearBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight < 150;
    if (isNearBottom) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatStates, currentChatId]);

  const currentChat = currentChatId ? chatStates[currentChatId] : null;

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleNewChat = () => {
    const id = Date.now().toString();
    setChatStates((prev) => ({
      ...prev,
      [id]: { id, video_id: null, videoTitle: null, channel_name: null, thumbnail: null, messages: [] },
    }));
    setCurrentChatId(id);
    setVideoError(null);
  };

  const handleSelectChat = (id: string) => {
    setCurrentChatId(id);
    setVideoError(null);
  };

  const handleDeleteChat = (id: string) => {
    setChatStates((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    if (currentChatId === id) {
      const remaining = Object.keys(chatStates).filter((k) => k !== id);
      if (remaining.length > 0) {
        setCurrentChatId(remaining.sort((a, b) => Number(b) - Number(a))[0]);
      } else {
        setCurrentChatId(null); // triggers bootstrap to create a new chat
      }
    }
  };

  const handleLoadVideo = async (videoId: string) => {
    if (!currentChatId) return;
    setIsLoadingVideo(true);
    setVideoError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/youtube/info?video_id=${videoId}`
      );

      if (!response.ok) {
        let errMsg = `Server error: ${response.status}`;
        try {
          const errData = await response.json();
          if (errData && typeof errData === 'object' && 'detail' in errData) {
            errMsg = String(errData.detail);
          }
        } catch {
          // ignore parsing error
        }
        throw new Error(errMsg);
      }

      const data = (await response.json()) as {
        video_id: string;
        title: string;
        channel_name: string;
        thumbnail: string;
      };

      setChatStates((prev) => ({
        ...prev,
        [currentChatId]: {
          ...prev[currentChatId],
          video_id: data.video_id,
          videoTitle: data.title,
          channel_name: data.channel_name,
          thumbnail: data.thumbnail,
        },
      }));
    } catch (error: any) {
      const errMsg = error.message || 'Failed to load video. Please try again.';
      setVideoError(errMsg);
      console.error('Error loading video:', error);
      throw error;
    } finally {
      setIsLoadingVideo(false);
    }
  };

  const handleSendMessage = async (message: string) => {
    if (!currentChatId || !currentChat?.video_id) return;

    const userMessage: Message = { id: Date.now().toString(), role: 'user', content: message };
    setChatStates((prev) => ({
      ...prev,
      [currentChatId]: { ...prev[currentChatId], messages: [...prev[currentChatId].messages, userMessage] },
    }));

    setIsLoadingResponse(true);

    try {
      const response = await fetch(`${API_BASE_URL}/ask`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ video_id: currentChat.video_id, query: message }),
      });

      if (!response.ok) throw new Error(`Server error: ${response.status}`);

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const assistantMessage: Message = { id: (Date.now() + 1).toString(), role: 'assistant', content: '' };
      setChatStates((prev) => ({
        ...prev,
        [currentChatId]: { ...prev[currentChatId], messages: [...prev[currentChatId].messages, assistantMessage] },
      }));

      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const lines = decoder.decode(value).split('\n');

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr) continue;

          try {
            const data = JSON.parse(jsonStr);
            if (data.done) break;

            for (const char of data.chunk as string) {
              await new Promise((r) => setTimeout(r, 15));
              setChatStates((prev) => {
                const chat     = prev[currentChatId];
                const messages = [...chat.messages];
                const last     = messages[messages.length - 1];
                if (last?.role === 'assistant') {
                  messages[messages.length - 1] = { ...last, content: last.content + char };
                }
                return { ...prev, [currentChatId]: { ...chat, messages } };
              });
            }
          } catch {
            // skip malformed SSE lines
          }
        }
      }
    } catch (error) {
      console.error('Error sending message:', error);
      const errMsg: Message = {
        id:      (Date.now() + 2).toString(),
        role:    'assistant',
        content: 'Sorry, I encountered an error processing your question. Please try again.',
      };
      setChatStates((prev) => ({
        ...prev,
        [currentChatId]: { ...prev[currentChatId], messages: [...prev[currentChatId].messages, errMsg] },
      }));
    } finally {
      setIsLoadingResponse(false);
    }
  };

  const handleClearChat = () => {
    if (!currentChatId) return;
    if (window.confirm('Clear this chat? This action cannot be undone.')) {
      setChatStates((prev) => ({
        ...prev,
        [currentChatId]: {
          ...prev[currentChatId],
          messages: [],
          video_id: null, videoTitle: null, channel_name: null, thumbnail: null,
        },
      }));
      setVideoError(null);
    }
  };
  if (!mounted) return null;
  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      <Sidebar
        onNewChat={handleNewChat}
        currentChatId={currentChatId}
        onSelectChat={handleSelectChat}
        chatStates={Object.values(chatStates)}
        onDeleteChat={handleDeleteChat}
      />

      <div className="flex-1 flex flex-col">

        {/* Header – Video Input */}
        <motion.div
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="px-6 py-4 border-b border-border bg-background"
        >
          <div className="max-w-4xl mx-auto space-y-4">
            <VideoInput
              onLoad={handleLoadVideo}
              isLoading={isLoadingVideo}
              error={videoError || undefined}
              onClearError={() => setVideoError(null)}
            />

            {currentChat?.videoTitle && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-4 p-3 bg-primary/10 border border-primary/20 rounded-xl"
              >
                {currentChat.thumbnail && (
                  <div className="flex-shrink-0 w-24 h-14 rounded-lg overflow-hidden">
                    <img
                      src={currentChat.thumbnail}
                      alt={currentChat.videoTitle}
                      className="w-full h-full object-cover"
                    />
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-muted-foreground uppercase font-semibold tracking-wide">
                    Loaded Video
                  </p>
                  <p className="text-sm font-medium text-foreground truncate">
                    {currentChat.videoTitle}
                  </p>
                  <p className="text-xs text-muted-foreground truncate">
                    {currentChat.channel_name}
                  </p>
                </div>
              </motion.div>
            )}
          </div>
        </motion.div>

        {/* Messages */}
        <div ref={scrollContainerRef} className="flex-1 overflow-y-auto px-6 py-4">
          <div className="max-w-4xl mx-auto">
            <AnimatePresence mode="wait">
              {currentChat?.messages.length === 0 && !currentChat?.videoTitle ? (
                <motion.div
                  key="empty-state"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="h-full flex flex-col items-center justify-center text-center py-12"
                >
                  <div className="w-16 h-16 bg-primary/10 rounded-2xl flex items-center justify-center mb-4">
                    <span className="text-2xl">▶</span>
                  </div>
                  <h2 className="text-2xl font-bold text-foreground mb-2">YouTube Q&A Chat</h2>
                  <p className="text-muted-foreground max-w-md">
                    Paste a YouTube URL above and start asking questions about the video.
                    I'll provide instant answers powered by AI.
                  </p>
                </motion.div>
              ) : (
                <motion.div key="messages" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  {currentChat?.messages.map((msg) => (
                    <ChatMessage key={msg.id} role={msg.role} content={msg.content} />
                  ))}
                  {isLoadingResponse && <ChatMessage role="assistant" content="" isLoading={true} />}
                  <div ref={messagesEndRef} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Input Bar */}
        {currentChat?.videoTitle ? (
          <div className="px-6 py-4 border-t border-border bg-background">
            <div className="max-w-4xl mx-auto space-y-3">
              <ChatInput
                onSend={handleSendMessage}
                isLoading={isLoadingResponse}
                placeholder="Ask a question about the video..."
              />
              <div className="flex justify-end">
                <button
                  onClick={handleClearChat}
                  disabled={currentChat.messages.length === 0}
                  className="text-xs text-muted-foreground hover:text-foreground disabled:opacity-50 transition-colors flex items-center gap-1"
                >
                  <Trash2 size={14} />
                  Clear Chat
                </button>
              </div>
            </div>
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="px-6 py-4 border-t border-border bg-muted text-center text-muted-foreground text-sm"
          >
            Load a YouTube video to start chatting
          </motion.div>
        )}
      </div>
    </div>
  );
}
