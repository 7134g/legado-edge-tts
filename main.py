#!/usr/bin/env python3
import asyncio
from aiohttp import web
import edge_tts
import re
import os
from urllib.parse import unquote
import base64
import requests
import hashlib
import struct
import time

def remove_special_characters(text):
    text = unquote(text)
    return re.sub(r'[^\w\s\u4e00-\u9fff，。！？；：、（）《》【】“”‘’]', '', text)

async def generate_audio(request):
    startTime = time.perf_counter()
    try:
        # 解析表单数据
        form = await request.post()
        text = form.get('text', '')
        voice = form.get('voice', 'zh-CN-XiaoxiaoNeural')
        rate = form.get('rate', '0')
        
        # 处理文本
        cleaned_text = remove_special_characters(text)
        
        # 处理语速
        try:
            rate_value = max(0, min(100, int(rate)))
        except ValueError:
            rate_value = 25
            
        rate_offset = rate_value - 25
        custom_rate = f"+{rate_offset}%" if rate_offset > 0 else f"{rate_offset}%"
        
        uid = hashlib.md5(cleaned_text.encode("utf-8")).hexdigest()[:12]
        # 创建流式响应
        response = web.StreamResponse(
            status=200,
            headers={
                'Content-Type': 'audio/mpeg',
                'Content-Disposition':  f'attachment; filename="audio_{uid}.mp3"',
            }
        )
        await response.prepare(request)
        
        # 流式生成音频并发送
        communicate = edge_tts.Communicate(cleaned_text, voice, rate=custom_rate)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                await response.write(chunk["data"])
                
        await response.write_eof()
        return response
        
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

    finally:
        endTime = time.perf_counter()
        print(f"{time.strftime("%Y年%m月%d日 %H:%M:%S")} 执行时间: {endTime - startTime:.4f} 秒")




def generate_wav(stream):
    pcm_chunks = []
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if not getattr(delta, "audio", None):
            continue
        pcm_bytes = base64.b64decode(delta.audio["data"])
        pcm_chunks.append(pcm_bytes)

    if not pcm_chunks:
        return

     # ── 拼接 PCM + 加 WAV 头 ─────────────────────────────────
    pcm_data = b"".join(pcm_chunks)
    sample_rate  = 24000
    channels     = 1
    bits         = 16
    data_size    = len(pcm_data)
    byte_rate    = sample_rate * channels * bits // 8
    block_align  = channels * bits // 8
    wav_header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        36 + data_size,
        b'WAVE',
        b'fmt ',
        16,
        1,
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits,
        b'data',
        data_size,
    )

    wav_data = wav_header + pcm_data

    return wav_data


async def home(request):
     print("hearbeat", time.strftime("%Y年%m月%d日 %H:%M:%S"))
     return web.json_response({"status": "ok"}, status=200)


app = web.Application()
app.router.add_get('/', home)
app.router.add_post('/api/rap', generate_audio)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 1233))
    print("service port===>",port)
    web.run_app(app, host='0.0.0.0', port=port)
