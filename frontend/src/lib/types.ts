export interface Video {
  id: string;
  filename: string;
  original_filename: string;
  file_size: number;
  mime_type: string;
  duration: number;
  width: number;
  height: number;
  fps: number;
  video_codec: string;
  audio_codec: string;
  status: string;
  progress: number;
  stage_message: string;
  error_message: string;
  thumbnail_url: string;
  num_clips: number;
  created_at: string | null;
}

export interface VideoStatus {
  id: string;
  status: string;
  progress: number;
  stage_message: string;
  error_message: string;
  num_clips: number;
}

export interface Clip {
  id: string;
  video_id: string;
  rank: number;
  start_time: number;
  end_time: number;
  duration: number;
  score: number;
  reasons: string[];
  signals: Record<string, number>;
  title: string;
  thumbnail_url: string;
  status: string;
}

export interface ClipList {
  video_id: string;
  count: number;
  clips: Clip[];
}

export interface ExportJob {
  id: string;
  clip_id: string;
  video_id: string;
  aspect_ratio: string;
  output_format: string;
  quality: string;
  width: number;
  height: number;
  status: string;
  progress: number;
  file_size: number;
  error_message: string;
  download_url: string;
  created_at: string | null;
}

export interface ExportList {
  video_id: string;
  count: number;
  exports: ExportJob[];
}

export interface Health {
  status: string;
  app: string;
  ffmpeg: boolean;
  database: boolean;
  queue: boolean;
  transcript_engine: string;
}

export type AspectRatio = "16:9" | "9:16" | "1:1";
export type OutputFormat = "mp4" | "webm";
export type Quality = "fast" | "balanced" | "high";
