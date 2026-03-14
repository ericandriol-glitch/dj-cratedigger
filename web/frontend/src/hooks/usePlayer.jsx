import { createContext, useContext, useState, useRef, useCallback, useEffect } from "react";
import { API } from "./useApi";

const PlayerCtx = createContext(null);

export function PlayerProvider({ children }) {
  const [track, setTrack] = useState(null);      // { filepath, title, artist, bpm, key, genre }
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.8);
  const audioRef = useRef(null);

  // Lazy-create audio element
  const getAudio = useCallback(() => {
    if (!audioRef.current) {
      const a = new Audio();
      a.addEventListener("timeupdate", () => setCurrentTime(a.currentTime));
      a.addEventListener("loadedmetadata", () => setDuration(a.duration));
      a.addEventListener("ended", () => setPlaying(false));
      audioRef.current = a;
    }
    return audioRef.current;
  }, []);

  const play = useCallback((t) => {
    const a = getAudio();
    const src = `${API}/api/audio/stream?filepath=${encodeURIComponent(t.filepath)}`;
    if (track?.filepath !== t.filepath) {
      a.src = src;
      setTrack(t);
    }
    a.volume = volume;
    a.play();
    setPlaying(true);
  }, [getAudio, track, volume]);

  const pause = useCallback(() => {
    audioRef.current?.pause();
    setPlaying(false);
  }, []);

  const togglePlay = useCallback(() => {
    if (!track) return;
    if (playing) pause();
    else { audioRef.current?.play(); setPlaying(true); }
  }, [track, playing, pause]);

  const seek = useCallback((time) => {
    const a = audioRef.current;
    if (a) { a.currentTime = time; setCurrentTime(time); }
  }, []);

  const setVol = useCallback((v) => {
    setVolume(v);
    if (audioRef.current) audioRef.current.volume = v;
  }, []);

  // Keyboard: space = toggle
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      if (e.code === "Space" && track) { e.preventDefault(); togglePlay(); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [track, togglePlay]);

  return (
    <PlayerCtx.Provider value={{ track, playing, currentTime, duration, volume, play, pause, togglePlay, seek, setVol }}>
      {children}
    </PlayerCtx.Provider>
  );
}

export const usePlayer = () => useContext(PlayerCtx);
