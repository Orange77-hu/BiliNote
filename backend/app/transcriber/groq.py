from abc import ABC
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
# 注：上面固定 64k 的版本被 compress_to_size 替代（64k 压 2h 课仍约 57MB，
# 超出 Groq API 的 25MB 请求上限），保留备查。


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
            print(f"文件超过 {MAX_SIZE_MB}MB，开始压缩（当前 {round(file_size / (1024 * 1024), 2)}MB）...")
            file_path = compress_to_size(file_path, MAX_SIZE_BYTES)
            print(f"压缩完成：{round(os.path.getsize(file_path) / (1024 * 1024), 2)}MB，临时路径：{file_path}")
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
        filename = file_path

        with open(filename, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(filename, file.read()),
                model=os.getenv('GROQ_TRANSCRIBER_MODEL'),
                response_format="verbose_json",
            )
            print(transcription.text)
        print(transcription)
        segments = []
        full_text = ""

        for seg in transcription.segments:
            text = seg.text.strip()
            full_text += text + " "
            segments.append(TranscriptSegment(
                start=seg.start,
                end=seg.end,
                text=text
            ))

        result = TranscriptResult(
            language=transcription.language,
            full_text=full_text.strip(),
            segments=segments,
            raw=transcription.to_dict()
        )
        return result
