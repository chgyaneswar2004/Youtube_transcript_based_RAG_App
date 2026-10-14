'use client';

import { Plus, MessageSquare, Moon, Sun, Trash2 } from 'lucide-react';
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { ChatState } from '../app/page';

interface SidebarProps {
  onNewChat: () => void;
  currentChatId: string | null;
  onSelectChat: (id: string) => void;
  chatStates: ChatState[];
  onDeleteChat?: (id: string) => void;
}

export function Sidebar({
  onNewChat,
  currentChatId,
  onSelectChat,
  chatStates,
  onDeleteChat,
}: SidebarProps) {
  const [isDark, setIsDark]     = useState(false);

  useEffect(() => {
  setIsDark(document.documentElement.classList.contains('dark'));
  }, []);

  const toggleTheme = () => {
    const root     = document.documentElement;
    const newDark  = !isDark;
    root.classList.toggle('dark', newDark);
    localStorage.setItem('theme', newDark ? 'dark' : 'light');
    setIsDark(newDark);
  };

  // Derive a display title from the chat state:
  //   - Use the video title if a video is loaded
  //   - Use the first user message if no video title
  //   - Fall back to "New Chat"
  const getChatTitle = (chat: ChatState): string => {
    if (chat.videoTitle) return chat.videoTitle;
    const firstUserMsg = chat.messages.find((m) => m.role === 'user');
    if (firstUserMsg) return firstUserMsg.content.slice(0, 40);
    return 'New Chat';
  };

  // Most-recent first
  const sortedChats = [...chatStates].sort((a, b) => Number(b.id) - Number(a.id));

  

  return (
    <motion.aside
      initial={{ x: -320 }}
      animate={{ x: 0 }}
      className="w-64 bg-background border-r border-border flex flex-col h-screen"
    >
      {/* Header */}
      <div className="p-6 border-b border-border">
        <div className="flex items-center gap-2 mb-8">
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center text-primary-foreground font-bold">
            ▶
          </div>
          <div>
            <h1 className="text-lg font-bold text-foreground">YouTube Q&A</h1>
            <p className="text-xs text-muted-foreground">Chat Interface</p>
          </div>
        </div>

        <button
          onClick={onNewChat}
          className="w-full px-4 py-2 bg-primary text-primary-foreground rounded-xl font-medium hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
        >
          <Plus size={18} />
          New Chat
        </button>
      </div>

      {/* Chat List */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="text-xs uppercase text-muted-foreground font-semibold mb-3 px-2">
          Chats
        </div>

        {sortedChats.length === 0 ? (
          <p className="text-xs text-muted-foreground px-2">No chats yet.</p>
        ) : (
          <div className="space-y-1">
            {sortedChats.map((chat) => (
              <motion.div
                key={chat.id}
                whileHover={{ x: 2 }}
                className={`group flex items-center gap-1 rounded-lg transition-colors ${
                  currentChatId === chat.id
                    ? 'bg-primary/10 text-primary'
                    : 'text-foreground hover:bg-muted'
                }`}
              >
                {/* Select button */}
                <button
                  onClick={() => onSelectChat(chat.id)}
                  className="flex-1 text-left px-3 py-2 text-sm min-w-0"
                >
                  <div className="flex items-center gap-2">
                    {chat.thumbnail ? (
                      <img
                        src={chat.thumbnail}
                        alt=""
                        className="w-5 h-5 rounded object-cover flex-shrink-0"
                      />
                    ) : (
                      <MessageSquare size={14} className="flex-shrink-0" />
                    )}
                    <span className="truncate">{getChatTitle(chat)}</span>
                  </div>
                  {chat.channel_name && (
                    <p className="text-xs text-muted-foreground truncate mt-0.5 pl-7">
                      {chat.channel_name}
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground mt-0.5 pl-7">
                    {chat.messages.length} message{chat.messages.length !== 1 ? 's' : ''}
                  </p>
                </button>

                {/* Delete button — visible on hover */}
                {onDeleteChat && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (window.confirm('Delete this chat?')) onDeleteChat(chat.id);
                    }}
                    className="pr-2 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Theme Toggle */}
      <div className="p-4 border-t border-border">
        <button
          onClick={toggleTheme}
          className="w-full px-4 py-2 flex items-center justify-center gap-2 text-foreground hover:bg-muted rounded-lg transition-colors"
        >
          {isDark ? <Sun size={18} /> : <Moon size={18} />}
          <span className="text-sm font-medium">{isDark ? 'Light' : 'Dark'} Mode</span>
        </button>
      </div>
    </motion.aside>
  );
}