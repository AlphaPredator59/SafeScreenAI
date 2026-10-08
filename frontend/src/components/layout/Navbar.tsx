import React from 'react';
import { NavLink, Link } from 'react-router-dom';
import { Shield, Sun, Moon, UploadCloud, Film, LayoutDashboard } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';
import { useSession } from '../../store/sessionContext';

export const Navbar: React.FC = () => {
  const { theme, toggleTheme } = useTheme();
  const { sessionVideos } = useSession();

  const navLinkClasses = ({ isActive }: { isActive: boolean }) =>
    `inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
      isActive
        ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-400'
        : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
    }`;

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-200 dark:border-slate-800 bg-white/85 dark:bg-slate-900/85 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand / Logo */}
        <Link to="/dashboard" className="flex items-center gap-3 group focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-lg p-1">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-700 to-blue-500 flex items-center justify-center text-white shadow-sm shadow-blue-500/20 group-hover:scale-105 transition-transform">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-lg tracking-tight text-slate-900 dark:text-slate-100">
                SafeScreen
              </span>
              <span className="text-[10px] font-semibold tracking-wider uppercase px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-400 border border-blue-200 dark:border-blue-800">
                AI
              </span>
            </div>
            <p className="text-[11px] text-slate-400 dark:text-slate-500 hidden sm:block -mt-1">
              Video Moderation & Trust Platform
            </p>
          </div>
        </Link>

        {/* Center Nav Links */}
        <nav className="hidden md:flex items-center gap-1">
          <NavLink to="/dashboard" className={navLinkClasses}>
            <LayoutDashboard className="w-4 h-4" />
            Dashboard
          </NavLink>
          <NavLink to="/upload" className={navLinkClasses}>
            <UploadCloud className="w-4 h-4" />
            Upload Video
          </NavLink>
          <NavLink to="/videos" className={navLinkClasses}>
            <Film className="w-4 h-4" />
            Session Videos
            {sessionVideos.length > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[11px] font-semibold bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                {sessionVideos.length}
              </span>
            )}
          </NavLink>
        </nav>

        {/* Right side controls */}
        <div className="flex items-center gap-2.5">
          {/* Active Session badge */}
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>Session: {sessionVideos.length} {sessionVideos.length === 1 ? 'Video' : 'Videos'}</span>
          </div>

          {/* Upload CTA for quick access */}
          <Link
            to="/upload"
            className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-sm transition-colors"
          >
            <UploadCloud className="w-3.5 h-3.5" />
            Upload
          </Link>

          {/* Theme Toggle (Light / Dark Mode) */}
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            className="p-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 hover:bg-slate-100 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {theme === 'dark' ? (
              <Sun className="w-4 h-4 text-amber-400" />
            ) : (
              <Moon className="w-4 h-4 text-slate-700" />
            )}
          </button>
        </div>
      </div>

      {/* Mobile nav bar below header */}
      <div className="md:hidden flex items-center justify-around border-t border-slate-200 dark:border-slate-800 px-2 py-1.5 bg-slate-50/50 dark:bg-slate-900/50">
        <NavLink to="/dashboard" className={navLinkClasses}>
          <LayoutDashboard className="w-4 h-4" />
          <span className="text-xs">Dashboard</span>
        </NavLink>
        <NavLink to="/upload" className={navLinkClasses}>
          <UploadCloud className="w-4 h-4" />
          <span className="text-xs">Upload</span>
        </NavLink>
        <NavLink to="/videos" className={navLinkClasses}>
          <Film className="w-4 h-4" />
          <span className="text-xs">Session ({sessionVideos.length})</span>
        </NavLink>
      </div>
    </header>
  );
};
