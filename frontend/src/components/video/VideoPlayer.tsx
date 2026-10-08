import React, { forwardRef, useImperativeHandle, useRef, useState } from 'react';
import { Film, Play, Pause, Volume2, VolumeX, Maximize2, AlertCircle, Clock, Monitor } from 'lucide-react';
import type { VideoResponse } from '../../types/api';
import { Card } from '../common/Card';

export interface VideoPlayerRef {
  seekTo: (seconds: number) => void;
  play: () => void;
  pause: () => void;
  getCurrentTime: () => number;
}

interface VideoPlayerProps {
  src?: string; // Local Object URL if available in memory
  video?: VideoResponse | null;
  onTimeUpdate?: (currentTime: number) => void;
}

export const VideoPlayer = forwardRef<VideoPlayerRef, VideoPlayerProps>(
  ({ src, video, onTimeUpdate }, ref) => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const [isPlaying, setIsPlaying] = useState<boolean>(false);
    const [currentTime, setCurrentTime] = useState<number>(0);
    const [duration, setDuration] = useState<number>(video?.duration || 0);
    const [isMuted, setIsMuted] = useState<boolean>(false);

    useImperativeHandle(ref, () => ({
      seekTo: (seconds: number) => {
        if (videoRef.current) {
          videoRef.current.currentTime = Math.max(0, Math.min(seconds, videoRef.current.duration || seconds));
        } else {
          setCurrentTime(seconds);
          onTimeUpdate?.(seconds);
        }
      },
      play: () => videoRef.current?.play(),
      pause: () => videoRef.current?.pause(),
      getCurrentTime: () => videoRef.current?.currentTime || currentTime,
    }));

    const formatTime = (seconds: number) => {
      const mins = Math.floor(seconds / 60);
      const secs = Math.floor(seconds % 60);
      return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
    };

    const handleTimeUpdate = () => {
      if (videoRef.current) {
        const time = videoRef.current.currentTime;
        setCurrentTime(time);
        onTimeUpdate?.(time);
      }
    };

    const handleLoadedMetadata = () => {
      if (videoRef.current) {
        setDuration(videoRef.current.duration);
      }
    };

    const togglePlay = () => {
      if (!videoRef.current) return;
      if (videoRef.current.paused) {
        videoRef.current.play();
        setIsPlaying(true);
      } else {
        videoRef.current.pause();
        setIsPlaying(false);
      }
    };

    const toggleMute = () => {
      if (!videoRef.current) return;
      videoRef.current.muted = !videoRef.current.muted;
      setIsMuted(videoRef.current.muted);
    };

    const handleFullscreen = () => {
      if (videoRef.current) {
        if (videoRef.current.requestFullscreen) {
          videoRef.current.requestFullscreen();
        }
      }
    };

    const handleScrub = (e: React.ChangeEvent<HTMLInputElement>) => {
      const targetTime = parseFloat(e.target.value);
      if (videoRef.current) {
        videoRef.current.currentTime = targetTime;
      }
      setCurrentTime(targetTime);
      onTimeUpdate?.(targetTime);
    };

    // If local object URL is available, render real HTML5 video player
    if (src) {
      return (
        <Card elevated className="overflow-hidden bg-slate-950 border-slate-800">
          <div className="relative aspect-video w-full bg-slate-950 flex items-center justify-center">
            <video
              ref={videoRef}
              src={src}
              className="w-full h-full object-contain"
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              playsInline
            />
          </div>

          {/* Custom Controls Bar */}
          <div className="p-3 bg-slate-900 border-t border-slate-800 text-white flex flex-col gap-2">
            {/* Scrubber slider */}
            <input
              type="range"
              min={0}
              max={duration || 100}
              step={0.1}
              value={currentTime}
              onChange={handleScrub}
              className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
              aria-label="Video scrubber"
            />

            <div className="flex items-center justify-between text-xs text-slate-300">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={togglePlay}
                  className="p-1.5 rounded-lg hover:bg-slate-800 text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                  aria-label={isPlaying ? 'Pause' : 'Play'}
                >
                  {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </button>

                <button
                  type="button"
                  onClick={toggleMute}
                  className="p-1.5 rounded-lg hover:bg-slate-800 text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                  aria-label={isMuted ? 'Unmute' : 'Mute'}
                >
                  {isMuted ? <VolumeX className="w-4 h-4 text-red-400" /> : <Volume2 className="w-4 h-4" />}
                </button>

                <span className="font-mono text-slate-400">
                  {formatTime(currentTime)} / {formatTime(duration)}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleFullscreen}
                  className="p-1.5 rounded-lg hover:bg-slate-800 text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                  aria-label="Fullscreen"
                >
                  <Maximize2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </Card>
      );
    }

    // Honest Fallback: When video was uploaded in a previous tab or page reloaded
    return (
      <Card elevated className="overflow-hidden p-6 bg-slate-900 text-slate-100 border-slate-800">
        <div className="aspect-video w-full rounded-xl bg-slate-950 border border-slate-800 flex flex-col items-center justify-center p-6 text-center">
          <div className="w-14 h-14 rounded-2xl bg-slate-800/80 text-slate-400 flex items-center justify-center mb-3">
            <Film className="w-7 h-7" />
          </div>

          <h4 className="text-base font-semibold text-slate-200">
            {video?.filename || 'Video Source Record'}
          </h4>

          <div className="mt-2 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/70 border border-slate-700/60 text-xs text-amber-300">
            <AlertCircle className="w-4 h-4 shrink-0 text-amber-400" />
            <span>Local playback unavailable (Page reloaded). Streaming is not exposed by backend.</span>
          </div>

          {video && (
            <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs text-slate-400 w-full max-w-md">
              <div className="p-2 rounded bg-slate-900 border border-slate-800">
                <span className="text-slate-500 block">Resolution</span>
                <span className="font-semibold text-slate-300">
                  {video.width > 0 ? `${video.width} × ${video.height}` : 'N/A'}
                </span>
              </div>
              <div className="p-2 rounded bg-slate-900 border border-slate-800">
                <span className="text-slate-500 block">FPS</span>
                <span className="font-semibold text-slate-300">
                  {video.fps > 0 ? `${video.fps.toFixed(1)} fps` : 'N/A'}
                </span>
              </div>
              <div className="p-2 rounded bg-slate-900 border border-slate-800 col-span-2 sm:col-span-1">
                <span className="text-slate-500 block">Duration</span>
                <span className="font-semibold text-slate-300">
                  {formatTime(video.duration)}
                </span>
              </div>
            </div>
          )}
        </div>

        <div className="mt-4 flex items-center justify-between text-xs text-slate-400">
          <span className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" />
            Interactive moderation timeline and evidence below remain fully active.
          </span>
          <span className="flex items-center gap-1.5 font-mono">
            <Monitor className="w-3.5 h-3.5" />
            Timestamp navigation supported
          </span>
        </div>
      </Card>
    );
  }
);

VideoPlayer.displayName = 'VideoPlayer';
