'use client';

import { Play, Loader, AlertCircle } from 'lucide-react';
import { useState } from 'react';
import { motion } from 'framer-motion';

interface VideoInputProps {
  onLoad: (videoId: string) => Promise<void>;
  isLoading?: boolean;
  error?: string;
  onClearError?: () => void;
}

export function VideoInput({
  onLoad,
  isLoading = false,
  error,
  onClearError,
}: VideoInputProps) {
  const [url, setUrl] = useState('');

  /** Accepts full YouTube URLs or bare 11-char video IDs */
  const extractVideoId = (input: string): string | null => {
    const patterns = [
      /(?:youtube\.com\/watch\?v=|youtu\.be\/)([A-Za-z0-9_-]{11})/,
      /youtube\.com\/embed\/([A-Za-z0-9_-]{11})/,
      /youtube\.com\/shorts\/([A-Za-z0-9_-]{11})/,
    ];
    for (const pattern of patterns) {
      const match = input.match(pattern);
      if (match) return match[1];
    }
    // bare ID
    if (/^[A-Za-z0-9_-]{11}$/.test(input.trim())) return input.trim();
    return null;
  };

  const handleLoad = async () => {
    const videoId = extractVideoId(url.trim());
    if (!videoId) {
      alert('Please enter a valid YouTube URL or video ID');
      return;
    }

    try {
      await onLoad(videoId);
      setUrl('');
    } catch (err) {
      console.error('Error loading video:', err);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleLoad();
    }
  };

  return (
    <div className="space-y-3">
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/50 rounded-xl text-red-700 dark:text-red-400 text-sm"
        >
          <AlertCircle size={16} className="flex-shrink-0" />
          <span>{error}</span>
        </motion.div>
      )}

      <div className="flex gap-3">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Paste YouTube URL (e.g., https://youtube.com/watch?v=...)"
          disabled={isLoading}
          className="flex-1 px-4 py-3 bg-input border border-border rounded-xl text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-0 transition-all disabled:opacity-50"
        />
        <motion.button
          onClick={handleLoad}
          disabled={isLoading || !url.trim()}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="px-6 py-3 bg-primary text-primary-foreground rounded-xl hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center justify-center gap-2 font-medium"
        >
          {isLoading ? (
            <>
              <Loader size={18} className="animate-spin" />
              <span className="hidden sm:inline">Loading...</span>
            </>
          ) : (
            <>
              <Play size={18} />
              <span className="hidden sm:inline">Load</span>
            </>
          )}
        </motion.button>
      </div>
    </div>
  );
}