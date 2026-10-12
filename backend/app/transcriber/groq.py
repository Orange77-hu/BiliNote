from abc import ABC
import glob
import os

from app.decorators.timeit import timeit
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services.provider import ProviderService
from app.transcriber.base import Transcriber
from app.utils.openai_client import build_openai_client
import ffmpeg
import tempfile
from dotenv import load_dotenv
load_dotenv()
MAX_SIZE_MB = 18
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024
def compress_audio(input_path: str, target_bitrate='64k') -> str:
    output_fd, output_path = tempfile.mkstemp(suffix=".mp3")  # 临时输出文件
    os.close(output_fd)  # 关闭文件描述符
    ffmpeg.input(input_path).output(output_path, audio_bitrate=target_bitrate).run(quiet=True, overwrite_output=True)
    return output_path
# 注：上面固定 64k 的版本被切片方案替代（超长音频单文件压不进 18MB 还
# 保住可懂度），保留备查。

CHUNK_TARGET_BYTES = 15 * 1024 * 1024  # 每片目标体积（Groq 上限 25MB，留余量）


def probe_duration(path: str) -> float:
    probe = ffmpeg.probe(path)
    return float(probe["format"]["duration"])


def split_audio_chunks(input_path: str, chunk_bytes: int = CHUNK_TARGET_BYTES) -> list:
    """超限音频：64k 单声道压缩 + 按 ~30 分钟切片，一次 ffmpeg 完成。

    超长合集（6-7h）单文件即使压到最低可懂码率也远超 Groq 的 25MB
    请求上限（387MB 压完仍 96MB → 413）。改为压缩+切片逐片转写，外层
    按每片实际时长累加时间戳偏移。64k 单声道对语音无损感（whisper
    输入 16kHz 采样）。
    """
    seg_time = max(60, int(chunk_bytes * 8 / (64 * 1000) * 0.95))
    out_dir = tempfile.mkdtemp(prefix="groq_chunks_")
    pattern = os.path.join(out_dir, "chunk_%03d.mp3")
    (ffmpeg
     .input(input_path)
     .output(pattern, ac=1, ar=16000, audio_bitrate="64k",
             format="segment", segment_time=seg_time, reset_timestamps=1)
     .run(quiet=True, overwrite_output=True))
    chunks = sorted(glob.glob(os.path.join(out_dir, "chunk_*.mp3")))
    if not chunks:
        raise RuntimeError(f"音频切片失败：{out_dir} 下无产物")
    return chunks


def compress_to_size(input_path: str, max_bytes: int) -> str:
    """把音频压到 max_bytes 以内（Groq API 请求体上限 ~25MB，本模块留 18MB 余量）。

    固定 bitrate 压缩对长音频不可靠（2h 课 64k 压完仍 57MB）。改为按
    「原始大小 → 目标大小」比例估算 bitrate，转写场景压成单声道（ac=1），
    语音 16kHz 采样足够，32k 单声道已很清晰；压完校验，仍超限（元数据/
    时长估算误差）则 bitrate 减半重压，最多 4 轮。
    """
    src_size = os.path.getsize(input_path)
    if src_size <= max_bytes:
        return input_path
    try:
        probe = ffmpeg.probe(input_path)
        bitrate = int(probe["format"].get("bit_rate") or 128000)
    except Exception:
        bitrate = 128000
    ratio = max_bytes / src_size
    target_k = max(24, int(bitrate * ratio * 0.9) // 1000)
    current = input_path
    output_path = input_path
    for _ in range(4):
        output_fd, output_path = tempfile.mkstemp(suffix=".mp3")
        os.close(output_fd)
        (ffmpeg
         .input(current)
         .output(output_path, audio_bitrate=f"{target_k}k", ac=1)
         .run(quiet=True, overwrite_output=True))
        if os.path.getsize(output_path) <= max_bytes:
            return output_path
        target_k = max(16, target_k // 2)
        current = output_path
    # 4 轮后仍超限：返回最后一次结果，交给 API 报错（并有日志可查）
    return output_path

class GroqTranscriber(Transcriber, ABC):


    @timeit
    def transcript(self, file_path: str) -> TranscriptResult:
        file_size = os.path.getsize(file_path)
        if file_size > MAX_SIZE_BYTES:
            # 超长音频（如 6-7h 合集）单文件压不进 18MB 还保住可懂度
            # （387MB 压完仍 96MB → 413），改为压缩+切片逐片转写。
            print(f"文件超过 {MAX_SIZE_MB}MB（当前 {round(file_size / (1024 * 1024), 2)}MB），切片转写...")
            chunks = split_audio_chunks(file_path)
            print(f"切片完成：共 {len(chunks)} 片")
        else:
            chunks = [file_path]
        provider = ProviderService.get_provider_by_id('groq')

        if not provider:
            raise Exception("Groq 供应商未配置,请配置以后使用。")
        # build_openai_client 会校验 api_key 非空（空 key 会抛天书般的
        # `Illegal header value b'Bearer '`），并自动注入全局代理
        client = build_openai_client(
            api_key=provider.get('api_key'),
            base_url=provider.get('base_url'),
            key_label="Groq 转写引擎的 API Key",
        )

        segments = []
        full_text = ""
        language = None
        raw_chunks = []
        offset = 0.0
        for i, chunk in enumerate(chunks):
            with open(chunk, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=(chunk, file.read()),
                    model=os.getenv('GROQ_TRANSCRIBER_MODEL'),
                    response_format="verbose_json",
                )
            if len(chunks) > 1:
                print(f"第 {i + 1}/{len(chunks)} 片转写完成：{transcription.text[:40]}...")
            language = language or transcription.language
            for seg in transcription.segments:
                text = seg.text.strip()
                full_text += text + " "
                segments.append(TranscriptSegment(
                    start=seg.start + offset,
                    end=seg.end + offset,
                    text=text
                ))
            raw_chunks.append(transcription.to_dict())
            offset += probe_duration(chunk)

        result = TranscriptResult(
            language=language,
            full_text=full_text.strip(),
            segments=segments,
            raw={"chunks": raw_chunks} if len(raw_chunks) > 1 else raw_chunks[0]
        )
        return result
