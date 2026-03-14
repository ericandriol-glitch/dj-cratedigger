import { createContext, useContext, useState, useRef, useCallback, useEffect } from "react";
import { API } from "./useApi";

const PlayerCtx = createContext(null);

export function PlayerProvider({ children }) {
  const [track, setTrack] = useState(null);      // { filepath, title, artist, bpm, key, genre }
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.8);
  const [error, setError] = useState(null);
  const audioRef = useRef(null);

  // Lazy-create audio element with proper event listeners
  const getAudio = useCallback(() => {
    if (!audioRef.current) {
      const a = new Audio();
      a.addEventListener("timeupdate", () => setCurrentTime(a.currentTime));
      a.addEventListener("loadedmetadata", () => {
        if (isFinite(a.duration)) setDuration(a.duration);
      });
      a.addEventListener("ended", () => setPlaying(false));
      a.addEventListener("error", () => {
        setError("Failed to load audio");
        setPlaying(false);
      });
      audioRef.current = a;
    }
    return audioRef.current;
  }, []);

  // Cleanup audio element on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = "";
        audioRef.current = null;
      }
    };
  }, []);

  const play = useCallback((t) => {
    const a = getAudio();
    setError(null);
    const src = `${API}/api/audio/stream?filepath=${encodeURIComponent(t.filepath)}`;
    if (track?.filepath !== t.filepath) {
      a.src = src;
      setTrack(t);
      setCurrentTime(0);
      setDuration(0);
    }
    a.volume = volume;
    a.play().catch((err) => {
      // Handle autoplay policy or load errors
      if (err.name === "NotAllowedError") {
        setError("Click to enable audio playback");
      } else {
        setError("Playback failed");
      }
      setPlaying(false);
    });
    setPlaying(true);
  }, [getAudio, track, volume]);

  const pause = useCallback(() => {
    audioRef.current?.pause();
    setPlaying(false);
  }, []);

  const togglePlay = useCallback(() => {
    if (!track) return;
    if (playing) {
      pause();
    } else {
      const a = audioRef.current;
      if (a) {
        a.play().catch(() => setPlaying(false));
        setPlaying(true);
      }
    }
  }, [track, playing, pause]);

  const seek = useCallback((time) => {
    const a = audioRef.current;
    if (a && isFinite(time)) {
      a.currentTime = time;
      setCurrentTime(time);
    }
  }, []);

  const setVol = useCallback((v) => {
    setVolume(v);
    if (audioRef.current) audioRef.current.volume = v;
  }, []);

  // Keyboard: space = toggle
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.isContentEditable) return;
      if (e.code === "Space" && track) { e.preventDefault(); togglePlay(); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [track, togglePlay]);

  return (
    <PlayerCtx.Provider value={{ track, playing, currentTime, duration, volume, error, play, pause, togglePlay, seek, setVol }}>
      {children}
    </PlayerCtx.Provider>
  );
}

export const usePlayer = () => useContext(PlayerCtx);
