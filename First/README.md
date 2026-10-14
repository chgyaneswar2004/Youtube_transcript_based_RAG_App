# YouTube Q&A Chat

A modern, minimal web app where users can paste a YouTube URL and ask questions about the video. The system fetches transcripts via API and provides AI-powered answers through a sleek chat interface.

## Features

- 🎥 **YouTube Integration**: Paste any YouTube URL to load video metadata
- 💬 **Smart Chat Interface**: Ask questions about video content with streaming responses
- 🌙 **Dark/Light Mode**: Toggle between themes with persistent preferences
- ⚡ **Real-time Streaming**: See AI responses appear naturally with a typing effect
- 📱 **Responsive Design**: Works seamlessly on desktop, tablet, and mobile
- ✨ **Smooth Animations**: Built with Framer Motion for delightful interactions
- 📚 **Markdown Support**: Responses support rich formatting with code blocks
- 💾 **Chat History**: Keep track of previous conversations in the sidebar

## Tech Stack

- **Framework**: Next.js 14+ (App Router)
- **Styling**: Tailwind CSS 3.3+
- **Language**: TypeScript
- **Animations**: Framer Motion
- **UI Icons**: Lucide React
- **Markdown**: React Markdown

## Quick Start

### Prerequisites

- Node.js 18+ installed
- npm, yarn, or pnpm package manager

### Installation

1. **Clone the repository** (if applicable)
   ```bash
   git clone <repository-url>
   cd youtube-qa-chat
   ```

2. **Install dependencies**
   ```bash
   npm install
   # or
   yarn install
   # or
   pnpm install
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env.local
   ```

4. **Run the development server**
   ```bash
   npm run dev
   # or
   yarn dev
   # or
   pnpm dev
   ```

5. **Open your browser**
   Navigate to [http://localhost:3000](http://localhost:3000)

## How to Use

1. **Load a Video**: Paste a YouTube URL in the input field and click "Load"
2. **Ask Questions**: Once a video is loaded, type your questions in the chat
3. **Get Answers**: Receive AI-powered responses about the video content
4. **Copy Answers**: Click the copy button on any AI response to copy it
5. **Manage Chats**: Create new chats or view previous conversations in the sidebar
6. **Toggle Theme**: Use the theme button in the sidebar to switch between light and dark modes

## API Routes

### `POST /api/load-video`

Loads and validates a YouTube video.

**Request Body:**
```json
{
  "url": "https://youtube.com/watch?v=VIDEO_ID"
}
```

**Response:**
```json
{
  "videoId": "VIDEO_ID",
  "title": "Video Title"
}
```

### `POST /api/chat`

Streams AI responses about the loaded video.

**Request Body:**
```json
{
  "question": "What is the main topic?",
  "videoId": "VIDEO_ID"
}
```

**Response:** Server-Sent Events (SSE) stream with chunks of the response.

## Project Structure

```
app/
├── api/
│   ├── chat/
│   │   └── route.ts          # Chat streaming endpoint
│   └── load-video/
│       └── route.ts          # Video loading endpoint
├── layout.tsx                 # Root layout with theme provider
├── page.tsx                   # Main chat page
└── globals.css               # Global styles & CSS variables

components/
├── providers/
│   └── theme-provider.tsx    # Dark/light mode provider
├── sidebar.tsx               # Sidebar navigation
├── chat-message.tsx          # Message display component
├── chat-input.tsx            # Message input field
└── video-input.tsx           # YouTube URL input

Configuration Files:
├── tailwind.config.ts        # Tailwind CSS configuration
├── tsconfig.json             # TypeScript configuration
├── next.config.js            # Next.js configuration
├── postcss.config.js         # PostCSS configuration
└── .env.example              # Environment variables template
```

## Backend Architecture (Ready for Implementation)

The application is structured to support production-ready backend services:

### Transcript Extraction
```typescript
// app/api/transcript/route.ts (to be implemented)
// Fetch captions from YouTube or third-party API
// Support multiple languages
// Cache results for repeated queries
```

### Embedding Generation
```typescript
// app/api/embeddings/route.ts (to be implemented)
// Use OpenAI or Gemini API to generate embeddings
// Process video transcripts into chunks
// Store embeddings for vector search
```

### Vector Search
```typescript
// app/api/search/route.ts (to be implemented)
// Query Pinecone or Chroma vector database
// Find relevant transcript segments based on question
// Provide context for LLM response generation
```

### LLM Response Generation
```typescript
// Enhanced app/api/chat/route.ts
// Use vector search results as context
// Call OpenAI or Gemini API for response
// Stream tokens as they arrive
```

## Environment Variables

Create a `.env.local` file with the following (optional) variables:

```env
NEXT_PUBLIC_API_URL=http://localhost:3000
YOUTUBE_API_KEY=your_youtube_api_key
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX=your_index_name
```

## Development

### Build for production
```bash
npm run build
npm start
```

### Lint code
```bash
npm run lint
```

## Future Enhancements

- [ ] YouTube API integration for real video validation
- [ ] Database integration for persistent chat storage
- [ ] User authentication and accounts
- [ ] Multiple LLM provider support (OpenAI, Gemini, etc.)
- [ ] Vector database integration (Pinecone, Chroma)
- [ ] Transcript caching and indexing
- [ ] Export chat history (PDF, JSON)
- [ ] Sharing conversations
- [ ] Multi-language support

## Architecture Notes

This application is designed with a clear separation between frontend and backend:

- **Frontend**: Fully functional UI with mock API responses
- **Backend Ready**: API routes have placeholder logic ready for real service integration
- **Streaming**: Implemented using Server-Sent Events (SSE) for real-time response display
- **State Management**: React hooks (useState, useRef, useEffect) for chat state
- **Styling**: Utility-first CSS with Tailwind, supporting light/dark themes

## License

MIT

## Support

For issues, questions, or feature requests, please reach out through the Builder.io documentation or support channels.
