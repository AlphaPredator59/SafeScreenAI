import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './store/themeContext';
import { SessionProvider } from './store/sessionContext';
import { DashboardPage } from './pages/DashboardPage';
import { UploadPage } from './pages/UploadPage';
import { ProcessingPage } from './pages/ProcessingPage';
import { VideoDetailPage } from './pages/VideoDetailPage';
import { SessionVideosPage } from './pages/SessionVideosPage';
import { ReportPage } from './pages/ReportPage';
import { NotFoundPage } from './pages/NotFoundPage';

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <SessionProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/processing/:videoId" element={<ProcessingPage />} />
            <Route path="/videos" element={<SessionVideosPage />} />
            <Route path="/videos/:videoId" element={<VideoDetailPage />} />
            <Route path="/videos/:videoId/report" element={<ReportPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </BrowserRouter>
      </SessionProvider>
    </ThemeProvider>
  );
};

export default App;
