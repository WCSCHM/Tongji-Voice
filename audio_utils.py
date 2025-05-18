from pydub import AudioSegment
import librosa
import os

def standardize_audio(input_path, target_sample_rate=16000):
    """
    转换为16kHz单声道WAV格式
    """
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(target_sample_rate).set_channels(1)
    filename = os.path.basename(input_path)
    output_path = os.path.join("uploads", "processed_" + filename.rsplit('.', 1)[0] + ".wav")
    audio.export(output_path, format="wav")
    return output_path

def check_audio_duration(path, min_sec=5, max_sec=30):
    """
    使用librosa检查音频时长是否在5-30秒之间
    """
    duration = librosa.get_duration(path=path)
    if duration < min_sec or duration > max_sec:
        raise ValueError(f"音频时长为 {duration:.2f} 秒，不在 {min_sec}-{max_sec} 秒之间")
    return duration
