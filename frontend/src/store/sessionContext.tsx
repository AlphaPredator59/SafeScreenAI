import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import type { SessionContextType, SessionVideoRecord } from '../types/session';

const SESSION_STORAGE_VIDEOS_KEY = 'safescreen_session_videos_v1';
const SESSION_STORAGE_ID_KEY = 'safescreen_session_id';

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export const SessionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Session ID for the active browser tab
  const [sessionId] = useState<string>(() => {
    let id = sessionStorage.getItem(SESSION_STORAGE_ID_KEY);
    if (!id) {
      id = `sess_${Math.random().toString(36).substring(2, 9)}_${Date.now()}`;
      sessionStorage.setItem(SESSION_STORAGE_ID_KEY, id);
    }
    return id;
  });

  // Track session video records in state and synchronize to sessionStorage
  const [sessionVideos, setSessionVideos] = useState<SessionVideoRecord[]>(() => {
    try {
      const stored = sessionStorage.getItem(SESSION_STORAGE_VIDEOS_KEY);
      if (stored) {
        return JSON.parse(stored) as SessionVideoRecord[];
      }
    } catch {
      // Fallback on corrupt JSON
    }
    return [];
  });

  // In-memory mapping of videoId -> Blob Object URL (active only during current tab session)
  const blobUrlMapRef = useRef<Map<string, string>>(new Map());

  // Keep sessionStorage in sync whenever sessionVideos change
  useEffect(() => {
    try {
      sessionStorage.setItem(SESSION_STORAGE_VIDEOS_KEY, JSON.stringify(sessionVideos));
    } catch {
      // Storage quota or disabled storage
    }
  }, [sessionVideos]);

  const addSessionVideo = (video: SessionVideoRecord, blobUrl?: string) => {
    if (blobUrl) {
      blobUrlMapRef.current.set(video.videoId, blobUrl);
    }
    setSessionVideos((prev) => {
      // Avoid duplicate videoIds
      const filtered = prev.filter((v) => v.videoId !== video.videoId);
      return [video, ...filtered];
    });
  };

  const updateSessionVideo = (videoId: string, partial: Partial<SessionVideoRecord>) => {
    setSessionVideos((prev) =>
      prev.map((v) => (v.videoId === videoId ? { ...v, ...partial } : v))
    );
  };

  const removeSessionVideo = (videoId: string) => {
    const existingUrl = blobUrlMapRef.current.get(videoId);
    if (existingUrl) {
      URL.revokeObjectURL(existingUrl);
      blobUrlMapRef.current.delete(videoId);
    }
    setSessionVideos((prev) => prev.filter((v) => v.videoId !== videoId));
  };

  const clearSession = () => {
    // Revoke all in-memory blob URLs
    blobUrlMapRef.current.forEach((url) => {
      try {
        URL.revokeObjectURL(url);
      } catch {
        // Ignore revocation errors
      }
    });
    blobUrlMapRef.current.clear();
    setSessionVideos([]);
    sessionStorage.removeItem(SESSION_STORAGE_VIDEOS_KEY);
  };

  const getBlobUrl = (videoId: string): string | undefined => {
    return blobUrlMapRef.current.get(videoId);
  };

  return (
    <SessionContext.Provider
      value={{
        sessionId,
        sessionVideos,
        addSessionVideo,
        updateSessionVideo,
        removeSessionVideo,
        clearSession,
        getBlobUrl,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
};

export const useSession = (): SessionContextType => {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
};
