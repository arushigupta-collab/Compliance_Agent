"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, RefreshCw, Video } from "lucide-react";

/**
 * Live device-camera capture. Streams the webcam via getUserMedia, snapshots a
 * frame to a canvas, and hands the parent a JPEG File (the "selfie") plus a
 * preview URL. Used on the KYC page to match against the uploaded passport.
 */
export function CameraCapture({ onCapture }: { onCapture: (file: File, previewUrl: string) => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [live, setLive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shot, setShot] = useState<string | null>(null);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setLive(false);
  }, []);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setLive(true);
      setShot(null);
    } catch (e: any) {
      setError(e?.message || "Camera unavailable. Grant permission or upload a selfie image instead.");
    }
  }, []);

  useEffect(() => () => stop(), [stop]);

  const capture = () => {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 480;
    canvas.height = video.videoHeight || 360;
    canvas.getContext("2d")!.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!blob) return;
      const file = new File([blob], "selfie.jpg", { type: "image/jpeg" });
      const url = URL.createObjectURL(blob);
      setShot(url);
      onCapture(file, url);
      stop();
    }, "image/jpeg", 0.9);
  };

  return (
    <div className="rounded-lg border border-[var(--border)] p-2">
      <div className="relative aspect-[4/3] w-full overflow-hidden rounded-md bg-black/80">
        {shot ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={shot} alt="Captured selfie" className="h-full w-full object-cover" />
        ) : (
          <video ref={videoRef} playsInline muted className="h-full w-full object-cover" />
        )}
        {!live && !shot && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-white/70">
            <Video size={28} />
            <span className="text-xs">Camera off</span>
          </div>
        )}
      </div>
      {error && <div className="mt-2 text-xs text-red-500">{error}</div>}
      <div className="mt-2 flex gap-2">
        {!live && !shot && (
          <Btn onClick={start} icon={Video} label="Start camera" primary />
        )}
        {live && <Btn onClick={capture} icon={Camera} label="Capture photo" primary />}
        {shot && <Btn onClick={start} icon={RefreshCw} label="Retake" />}
      </div>
    </div>
  );
}

function Btn({ onClick, icon: Icon, label, primary }: { onClick: () => void; icon: any; label: string; primary?: boolean }) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium ${
        primary ? "bg-[var(--accent)] text-white hover:opacity-90"
                 : "border border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)]"
      }`}
    >
      <Icon size={14} /> {label}
    </button>
  );
}
