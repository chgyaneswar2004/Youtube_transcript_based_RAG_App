'use client';

import { Copy, Check } from 'lucide-react';
import { useState } from 'react';
import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  isLoading?: boolean;
}

export function ChatMessage({
  role,
  content,
  isLoading = false,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isUser = role === 'user';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}
    >
      <div
        className={`max-w-md lg:max-w-2xl rounded-xl px-4 py-3 ${
          isUser
            ? 'bg-primary text-primary-foreground rounded-br-none'
            : 'bg-muted text-foreground rounded-bl-none border border-border'
        }`}
      >
        <div className={isLoading ? 'space-y-2' : ''}>
          {isLoading ? (
            <div className="flex gap-1">
              <motion.div
                animate={{ y: [0, -4, 0] }}
                transition={{ duration: 1, repeat: Infinity }}
                className="w-2 h-2 bg-current rounded-full"
              />
              <motion.div
                animate={{ y: [0, -4, 0] }}
                transition={{ duration: 1, repeat: Infinity, delay: 0.1 }}
                className="w-2 h-2 bg-current rounded-full"
              />
              <motion.div
                animate={{ y: [0, -4, 0] }}
                transition={{ duration: 1, repeat: Infinity, delay: 0.2 }}
                className="w-2 h-2 bg-current rounded-full"
              />
            </div>
          ) : (
            <>
              <div className="text-sm leading-relaxed prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                  components={{
                    p: ({ node, ...props }) => (
                      <p className="mb-2" {...props} />
                    ),
                    // Fix: destructure `ordered` out so it never reaches the DOM <li>
                    li: ({ node, ordered, ...props }) => (
                      <li className="ml-4 mb-1" {...props} />
                    ),
                    code: ({ node, inline, ...props }: any) =>
                      inline ? (
                        <code
                          className="bg-black/20 px-1.5 py-0.5 rounded text-sm"
                          {...props}
                        />
                      ) : (
                        <code
                          className="block bg-black/20 p-2 rounded text-sm overflow-x-auto mb-2"
                          {...props}
                        />
                      ),
                  }}
                >
                  {content}
                </ReactMarkdown>
              </div>

              {!isUser && (
                <button
                  onClick={handleCopy}
                  className="mt-2 flex items-center gap-1 text-xs opacity-60 hover:opacity-100 transition-opacity"
                >
                  {copied ? (
                    <>
                      <Check size={14} />
                      Copied!
                    </>
                  ) : (
                    <>
                      <Copy size={14} />
                      Copy
                    </>
                  )}
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </motion.div>
  );
}
