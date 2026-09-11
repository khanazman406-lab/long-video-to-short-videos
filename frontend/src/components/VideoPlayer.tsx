import { useEffect, useRef, useState } from "react";
import { formatTime } from "../lib/utils";

interface Props {
  src: string;
  startTime?: number; // optional segment constraint
  endTime?: number;
  loopSegment?: boolean;
  autoPlay?: boolean;
  onTimeUpdate?: (t: number) => void;
}

/** Robust HTML5 player with full custom controls (seek, volume, speed, fullscreen). */
export default function VideoPlayer({
  src,
  startTime,
  endTime,
  loopSegment,
  autoPlay,
  onTimeUpdate,
}: Props) {
  const ref = useRef<HTMLVideoElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [rate, setRate] = useState(1);
  const [muted, setMuted] = useState(false);

  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    v.playbackRate = rate;
  }, [rate]);

  useEffect(() => {
    setTime(0);
    setPlaying(false);
  }, [src]);

  function onTime() {
    const v = ref.current;
    if (!v) return;
    let t = v.currentTime;
    if (endTime !== undefined && t >= endTime) {
      if (loopSegment && startTime !== undefined) {
        v.currentTime = startTime;
        t = startTime;
      } else {
        v.pause();
      }
    }
    setTime(t);
    onTimeUpdate?.(t);
  }

  function toggle() {
    const v = ref.current;
    if (!v) return;
    if (v.paused) {
      if (startTime !== undefined && (v.currentTime < startTime || (endTime !== undefined && v.currentTime >= endTime))) {
        v.currentTime = startTime;
      }
      v.play();
    } else v.pause();
  }

  function seek(delta: number) {
    const v = ref.current;
    if (!v) return;
    v.currentTime = Math.min(Math.max(0, v.currentTime + delta), v.duration || 0);
  }

  function onSeekBar(e: React.ChangeEvent<HTMLInputElement>) {
    const v = ref.current;
    if (!v || !duration) return;
    v.currentTime = (Number(e.target.value) / 100) * duration;
  }

  function toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen();
    else wrapRef.current?.requestFullscreen();
  }

  const lo = startTime ?? 0;
  const hi = endTime ?? duration;
  const pct = duration ? (time / duration) * 100 : 0;

  return (
    <div ref={wrapRef} className="overflow-hidden rounded-2xl bg-black">
      <video
        ref={ref}
        src={src}
        className="max-h-[60vh] w-full"
        playsInline
        preload="metadata"
        autoPlay={autoPlay}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onTimeUpdate={onTime}
        onLoadedMetadata={(e) => setDuration(e.currentTarget.duration || 0)}
        onClick={toggle}
      />
      {/* Segment range bar */}
      {duration > 0 && endTime !== undefined && (
        <div className="relative h-1.5 bg-slate-800">
          <div
            className="absolute h-full bg-brand-500/70"
            style={{ left: `${(lo / duration) * 100}%`, width: `${Math.max(0, ((hi - lo) / duration) * 100)}%` }}
          />
        </div>
      )}
      <div className="flex items-center gap-2 bg-slate-900 px-3 py-2 text-white">
        <button onClick={() => seek(-5)} className="rounded px-1.5 py-1 hover:bg-white/10" title="Back 5s">⏮</button>
        <button onClick={toggle} className="rounded px-2 py-1 text-lg hover:bg-white/10" title={playing ? "Pause" : "Play"}>
          {playing ? "⏸" : "▶"}
        </button>
        <button onClick={() => seek(5)} className="rounded px-1.5 py-1 hover:bg-white/10" title="Forward 5s">⏭</button>
        <span className="whitespace-nowrap font-mono text-xs text-slate-300">
          {formatTime(time)} / {formatTime(duration)}
        </span>
        <input
          type="range"
          min={0}
          max={100}
          step={0.1}
          value={pct}
          onChange={onSeekBar}
          className="h-1 w-full cursor-pointer accent-indigo-500"
          aria-label="Seek"
        />
        <button onClick={() => setMuted((m) => { const v = ref.current; if (v) v.muted = !m; return !m; })} className="rounded px-1.5 py-1 hover:bg-white/10" title="Mute">
          {muted ? "🔇" : "🔊"}
        </button>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={volume}
          onChange={(e) => {
            const v = Number(e.target.value);
            setVolume(v);
            if (ref.current) {
              ref.current.volume = v;
              ref.current.muted = false;
              setMuted(false);
            }
          }}
          className="hidden h-1 w-16 cursor-pointer accent-indigo-500 sm:block"
          aria-label="Volume"
        />
        <select
          value={rate}
          onChange={(e) => setRate(Number(e.target.value))}
          className="rounded bg-slate-800 px-1 py-1 text-xs"
          title="Playback speed"
        >
          {[0.5, 0.75, 1, 1.25, 1.5, 2].map((r) => (
            <option key={r} value={r}>{r}x</option>
          ))}
        </select>
        <button onClick={toggleFullscreen} className="rounded px-1.5 py-1 hover:bg-white/10" title="Fullscreen">⛶</button>
      </div>
    </div>
  );
}
