"""录屏用例：编排 Recorder + 系统声音 + 麦克风 + FFmpeg 合成。"""
import shutil
import tempfile
import threading
import time
from pathlib import Path

from app.core.audio.microphone import MicrophoneRecorder
from app.core.audio.system_audio import SystemAudioRecorder
from app.core.encoding.encoder_config import EncoderConfig
from app.core.export.muxer import Muxer
from app.core.models import Rect
from app.core.recording.recorder import Recorder
from app.infra.events import Event, EventType
from app.infra.logger import get_logger

logger = get_logger("controller.record")


class RecordController:
    def __init__(self, event_bus, output_dir):
        self._event_bus = event_bus
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._state = "idle"

        self._recorder = None
        self._sys_audio = None
        self._mic_audio = None
        self._temp_dir = None
        self._silent_video = None
        self._sys_wav = None
        self._mic_wav = None
        self._record_system_audio = False
        self._record_microphone = False
        self._final_path = None
        self._stop_thread = None

    @property
    def state(self):
        with self._lock:
            return self._state

    def _set_state(self, new_state):
        with self._lock:
            old = self._state
            self._state = new_state
        if old != new_state:
            self._event_bus.post(Event(
                type=EventType.STATE_CHANGED,
                payload={"old": old, "new": new_state},
            ))

    def start(self, region, fps=30, record_system_audio=True, record_microphone=False, highlight_mouse=True):
        if not isinstance(region, Rect):
            raise TypeError("region 必须是 Rect")
        w = region.width if region.width % 2 == 0 else region.width - 1
        h = region.height if region.height % 2 == 0 else region.height - 1
        if w <= 0 or h <= 0:
            raise ValueError(f"区域尺寸过小: {region.width}x{region.height}")
        region = Rect(region.x, region.y, w, h)

        self._temp_dir = Path(tempfile.mkdtemp(prefix="screenkit_"))
        self._silent_video = self._temp_dir / "silent.mp4"
        self._sys_wav = self._temp_dir / "system.wav"
        self._mic_wav = self._temp_dir / "mic.wav"
        self._record_system_audio = record_system_audio
        self._record_microphone = record_microphone

        enc_cfg = EncoderConfig(
            width=region.width, height=region.height, fps=fps, crf=23, preset="fast",
        )

        started = []
        try:
            self._recorder = Recorder(region, self._silent_video, enc_cfg, highlight_mouse)
            self._recorder.start()
            started.append("video")

            if record_system_audio:
                self._sys_audio = SystemAudioRecorder()
                self._sys_audio.start(self._sys_wav, sample_rate=48000, channels=2)
                started.append("system_audio")

            if record_microphone:
                self._mic_audio = MicrophoneRecorder()
                self._mic_audio.start(self._mic_wav, sample_rate=48000, channels=1)
                started.append("mic_audio")
        except Exception as exc:
            logger.exception("录制启动失败，开始回滚")
            self._rollback(started)
            self._cleanup_temp()
            raise RuntimeError(f"录制启动失败: {exc}") from exc

        self._set_state("recording")
        self._event_bus.post(Event(
            type=EventType.RECORDING_STARTED,
            message=f"录制中 ({region.width}x{region.height}@{fps}fps)",
        ))
        logger.info("录制已启动: %s", region)

    def pause(self):
        if self.state != "recording":
            return
        self._set_state("paused")
        self._recorder.pause()
        if self._sys_audio: self._sys_audio.pause()
        if self._mic_audio: self._mic_audio.pause()

    def resume(self):
        if self.state != "paused":
            return
        self._set_state("recording")
        self._recorder.resume()
        if self._sys_audio: self._sys_audio.resume()
        if self._mic_audio: self._mic_audio.resume()

    def stop(self):
        if self.state not in ("recording", "paused"):
            raise RuntimeError(f"当前状态不可停止: {self.state}")
        self._set_state("finalizing")
        self._stop_thread = threading.Thread(
            target=self._finalize_worker, name="record-finalize", daemon=True,
        )
        self._stop_thread.start()

    def _rollback(self, started):
        for name in reversed(started):
            obj = {
                "video": self._recorder,
                "system_audio": self._sys_audio,
                "mic_audio": self._mic_audio,
            }.get(name)
            if obj is None:
                continue
            try:
                obj.stop()
            except Exception:
                logger.exception("回滚 %s 失败", name)

    def _cleanup_temp(self):
        if self._temp_dir and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    def _finalize_worker(self):
        try:
            self._stop_all_components()
            final = self._output_dir / f"record_{int(time.time())}.mp4"
            self._mux(final)
            self._final_path = final
            self._event_bus.post(Event(
                type=EventType.RECORDING_STOPPED,
                message=f"录制完成: {final.name}",
                payload={"path": str(final)},
            ))
            logger.info("录制完成: %s", final)
        except Exception as exc:
            logger.exception("录制停止/合成失败")
            self._event_bus.post(Event(
                type=EventType.RECORDING_FAILED,
                message=f"录制失败: {exc}",
            ))
        finally:
            self._cleanup_temp()
            self._recorder = None
            self._sys_audio = None
            self._mic_audio = None
            self._set_state("idle")

    def _stop_all_components(self):
        errors = []
        for name, obj in [
            ("mic_audio", self._mic_audio),
            ("system_audio", self._sys_audio),
            ("recorder", self._recorder),
        ]:
            if obj is None:
                continue
            try:
                obj.stop()
            except Exception as exc:
                logger.exception("停止 %s 失败", name)
                errors.append(f"{name}: {exc}")
        if errors:
            logger.warning("以下组件停止时出错: %s", "; ".join(errors))

    def _mux(self, final_path):
        use_system = (
            self._record_system_audio
            and self._sys_wav is not None
            and self._sys_wav.is_file()
        )
        use_mic = (
            self._record_microphone
            and self._mic_wav is not None
            and self._mic_wav.is_file()
        )
        muxer = Muxer()

        if use_system and use_mic:
            muxer.mux_mixed(self._silent_video, self._sys_wav, self._mic_wav, final_path)
        elif use_system:
            muxer.mux_single(self._silent_video, self._sys_wav, final_path)
        elif use_mic:
            muxer.mux_single(self._silent_video, self._mic_wav, final_path)
        else:
            shutil.move(str(self._silent_video), str(final_path))