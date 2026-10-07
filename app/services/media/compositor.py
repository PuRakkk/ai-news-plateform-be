import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence

from app.core.log import logger


class VideoCompositorError(Exception):
    """Raised when FFmpeg video compositing fails."""
    pass


class VideoCompositor:
    """Composites visual cards, speech audio, subtitles, watermarks, and bumpers into vertical MP4 video."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg") -> None:
        self.ffmpeg_bin = ffmpeg_bin

    def _has_audio_stream(self, video_path: Path) -> bool:
        """Check if video file contains an audio stream."""
        try:
            proc = subprocess.run(
                [self.ffmpeg_bin, "-i", str(video_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            return "Audio:" in proc.stderr
        except Exception:
            return False

    def _normalize_clip(self, src: Path, dst: Path) -> None:
        """Ensure video clip has uniform 1080x1920 resolution, 30fps, SAR 1:1, and stereo AAC audio."""
        has_audio = self._has_audio_stream(src)
        dst.parent.mkdir(parents=True, exist_ok=True)

        filter_v = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"

        if has_audio:
            cmd = [
                self.ffmpeg_bin,
                "-y",
                "-i", str(src),
                "-vf", filter_v,
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-ar", "44100",
                "-ac", "2",
                "-b:a", "128k",
                str(dst),
            ]
        else:
            # Generate silent audio to keep audio stream present for concatenation
            cmd = [
                self.ffmpeg_bin,
                "-y",
                "-i", str(src),
                "-f", "lavfi",
                "-i", "anullsrc=r=44100:cl=stereo",
                "-vf", filter_v,
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                str(dst),
            ]

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if proc.returncode != 0:
            logger.error(f"Clip normalization failed: {proc.stderr[-400:]}")
            raise VideoCompositorError(f"Failed to normalize clip {src.name}: {proc.stderr[-300:]}")

    def _stitch_segments(self, clips: list[Path], output_path: Path) -> None:
        """Concatenate normalized video segments into single MP4."""
        if not clips:
            raise VideoCompositorError("No clips provided for stitching.")
        if len(clips) == 1:
            shutil.copy2(clips[0], output_path)
            return

        cmd = [self.ffmpeg_bin, "-y"]
        filter_inputs = []
        for idx, clip in enumerate(clips):
            cmd.extend(["-i", str(clip)])
            filter_inputs.append(f"[{idx}:v][{idx}:a]")

        concat_filter = f"{''.join(filter_inputs)}concat=n={len(clips)}:v=1:a=1[v][a]"
        cmd.extend([
            "-filter_complex", concat_filter,
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            str(output_path),
        ])

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if proc.returncode != 0:
            logger.error(f"Concat stitching failed: {proc.stderr[-400:]}")
            raise VideoCompositorError(f"Failed to stitch video segments: {proc.stderr[-300:]}")

    def composite_video(
        self,
        slides_with_durations: Sequence[tuple[Path, float]],
        audio_path: Path,
        output_path: Path,
        subtitles_ass_path: Path | None = None,
        watermark_path: Path | None = None,
        intro_bumper_path: Path | None = None,
        outro_bumper_path: Path | None = None,
        background_music_path: Path | None = None,
        bgm_volume: float = 0.08,
        enable_camera_motion: bool = True,
    ) -> Path:
        """Stitch slides, audio, subtitles, watermark, and optional bumpers into an animated 1080x1920 MP4 file."""
        if not slides_with_durations:
            raise VideoCompositorError("No slides provided for video compositing.")
        if not audio_path.exists():
            raise VideoCompositorError(f"Audio file not found: {audio_path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Fallback to default ambient bed if no specific bgm provided
        if not background_music_path:
            default_bed = Path("assets/audio/ambient_bed.mp3")
            if default_bed.exists():
                background_music_path = default_bed

        with tempfile.TemporaryDirectory() as temp_dir:
            td = Path(temp_dir)

            # Copy audio into temp workdir
            work_audio = td / "voice_audio.mp3"
            shutil.copy2(audio_path, work_audio)

            # Check if animated camera push-in is enabled
            use_motion_clips = False
            animated_clips: list[Path] = []

            if enable_camera_motion:
                logger.info(f"Rendering {len(slides_with_durations)} animated camera zoom clips...")
                try:
                    for idx, (slide_file, duration) in enumerate(slides_with_durations):
                        dur = max(0.6, float(duration))
                        total_frames = max(18, int(dur * 30))
                        clip_file = td / f"slide_zoom_{idx:02d}.mp4"
                        # Smooth camera drift push-in (zoom 1.00 -> 1.035) with 30fps
                        cmd_zoom = [
                            self.ffmpeg_bin, "-y",
                            "-loop", "1",
                            "-i", str(slide_file),
                            "-t", f"{dur:.2f}",
                            "-vf", f"zoompan=z='min(zoom+0.0006,1.035)':d={total_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30",
                            "-c:v", "libx264",
                            "-preset", "ultrafast",
                            "-pix_fmt", "yuv420p",
                            "-r", "30",
                            str(clip_file),
                        ]
                        p = subprocess.run(cmd_zoom, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                        if p.returncode == 0 and clip_file.exists():
                            animated_clips.append(clip_file)
                        else:
                            animated_clips = []
                            break
                    if len(animated_clips) == len(slides_with_durations):
                        use_motion_clips = True
                except Exception as exc:
                    logger.warning(f"Animated zoom clips failed ({exc}); falling back to static concat.")
                    use_motion_clips = False

            concat_txt = td / "concat.txt"
            if use_motion_clips:
                lines = [f"file '{c.name}'" for c in animated_clips]
                concat_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
            else:
                work_slides = []
                concat_lines = []
                for idx, (slide_file, duration) in enumerate(slides_with_durations):
                    work_slide = td / f"slide_{idx:02d}.png"
                    shutil.copy2(slide_file, work_slide)
                    work_slides.append(work_slide)
                    concat_lines.append(f"file '{work_slide.name}'")
                    concat_lines.append(f"duration {max(0.5, float(duration)):.2f}")
                # Repeat last slide
                concat_lines.append(f"file '{work_slides[-1].name}'")
                concat_txt.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")

            # Setup FFmpeg inputs and filter complex for the main scene
            cmd = [
                self.ffmpeg_bin,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", "concat.txt",
                "-i", "voice_audio.mp3",
            ]

            input_idx = 2
            watermark_input_idx: int | None = None
            bgm_input_idx: int | None = None

            if watermark_path and watermark_path.exists():
                work_wm = td / f"watermark{watermark_path.suffix}"
                shutil.copy2(watermark_path, work_wm)
                cmd.extend(["-i", work_wm.name])
                watermark_input_idx = input_idx
                input_idx += 1

            if background_music_path and background_music_path.exists():
                work_bgm = td / "bgm.mp3"
                shutil.copy2(background_music_path, work_bgm)
                cmd.extend(["-i", work_bgm.name])
                bgm_input_idx = input_idx
                input_idx += 1

            # Build video filter chain
            video_chain = "[0:v]"
            filter_parts: list[str] = []

            # 1. Live audio-reactive speaking visualizer underneath presenter frame
            filter_parts.append(
                f"[1:a]showwaves=s=380x36:mode=line:colors=0x10B981@0.9:scale=cbrt:rate=30,format=rgba[wave]; "
                f"{video_chain}[wave]overlay=350:1080:eval=frame[v_wave]"
            )
            video_chain = "[v_wave]"

            # 2. Watermark overlay filter (if present)
            if watermark_input_idx is not None:
                filter_parts.append(
                    f"[{watermark_input_idx}:v]scale=160:-1[scaled_wm]; "
                    f"{video_chain}[scaled_wm]overlay=main_w-overlay_w-50:80[v_wm]"
                )
                video_chain = "[v_wm]"

            # 3. Kinetic subtitles filter
            if subtitles_ass_path and subtitles_ass_path.exists():
                work_subs = td / "subs.ass"
                shutil.copy2(subtitles_ass_path, work_subs)
                filter_parts.append(f"{video_chain}ass=subs.ass[v_sub]")
                video_chain = "[v_sub]"

            # Build audio filter chain
            audio_map = "1:a"
            if bgm_input_idx is not None:
                filter_parts.append(
                    f"[1:a]volume=1.0[voice]; "
                    f"[{bgm_input_idx}:a]volume={bgm_volume:.2f},aloop=loop=-1:size=2e+09[bg_ducked]; "
                    f"[voice][bg_ducked]amix=inputs=2:duration=first[amixed]"
                )
                audio_map = "[amixed]"

            if filter_parts:
                cmd.extend(["-filter_complex", "; ".join(filter_parts)])
                cmd.extend(["-map", video_chain, "-map", audio_map])
            else:
                cmd.extend(["-map", "0:v", "-map", "1:a"])

            cmd.extend([
                "-c:v", "libx264",
                "-preset", "faster",
                "-pix_fmt", "yuv420p",
                "-r", "30",
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                "main_scene.mp4",
            ])

            logger.info(f"Rendering main scene with {len(slides_with_durations)} slides...")
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(td),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
            except FileNotFoundError as exc:
                raise VideoCompositorError(
                    f"FFmpeg binary '{self.ffmpeg_bin}' not found in system PATH."
                ) from exc

            if proc.returncode != 0:
                logger.error(f"FFmpeg main scene render failed: {proc.stderr[-1000:]}")
                raise VideoCompositorError(f"FFmpeg render failed (code {proc.returncode}): {proc.stderr[-500:]}")

            main_scene_path = td / "main_scene.mp4"
            if not main_scene_path.exists() or main_scene_path.stat().st_size == 0:
                raise VideoCompositorError("FFmpeg produced an empty or missing main_scene file.")

            # Check if bumper stitching is required
            has_intro = intro_bumper_path and intro_bumper_path.exists()
            has_outro = outro_bumper_path and outro_bumper_path.exists()

            if not has_intro and not has_outro:
                shutil.copy2(main_scene_path, output_path)
            else:
                clips_to_stitch: list[Path] = []
                if has_intro:
                    norm_intro = td / "norm_intro.mp4"
                    self._normalize_clip(intro_bumper_path, norm_intro)
                    clips_to_stitch.append(norm_intro)

                norm_main = td / "norm_main.mp4"
                self._normalize_clip(main_scene_path, norm_main)
                clips_to_stitch.append(norm_main)

                if has_outro:
                    norm_outro = td / "norm_outro.mp4"
                    self._normalize_clip(outro_bumper_path, norm_outro)
                    clips_to_stitch.append(norm_outro)

                self._stitch_segments(clips_to_stitch, output_path)

            logger.info(
                f"Video successfully composited: {output_path} ({output_path.stat().st_size} bytes)"
            )
            return output_path

    async def composite_video_async(
        self,
        slides_with_durations: Sequence[tuple[Path, float]],
        audio_path: Path,
        output_path: Path,
        subtitles_ass_path: Path | None = None,
        watermark_path: Path | None = None,
        intro_bumper_path: Path | None = None,
        outro_bumper_path: Path | None = None,
        background_music_path: Path | None = None,
        bgm_volume: float = 0.08,
        enable_camera_motion: bool = True,
    ) -> Path:
        """Asynchronously composite video in a worker thread to prevent blocking the event loop."""
        return await asyncio.to_thread(
            self.composite_video,
            slides_with_durations=slides_with_durations,
            audio_path=audio_path,
            output_path=output_path,
            subtitles_ass_path=subtitles_ass_path,
            watermark_path=watermark_path,
            intro_bumper_path=intro_bumper_path,
            outro_bumper_path=outro_bumper_path,
            background_music_path=background_music_path,
            bgm_volume=bgm_volume,
            enable_camera_motion=enable_camera_motion,
        )
