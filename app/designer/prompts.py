"""
AI 设计助手 prompt — MiniMax 这个 key 没有图像模型,改走方案 B:
LLM 生成专业的图像生成 prompt, 用户拿 prompt 去 Midjourney / 即梦 / 文心一格 等工具生成图片。
"""
from langchain_core.prompts import ChatPromptTemplate


DESIGNER_SYSTEM = """你是一位资深 AI 图像生成 Prompt 工程师,擅长为 Midjourney / Stable Diffusion / 即梦 / 文心一格 / DALL-E 等工具写高质量的英文 prompt。

【任务】
根据用户的设计需求(类型 + 主题 + 风格 + 配色),输出:
1. 一段**英文 prompt**(直接可粘贴到图像生成工具)
2. 中文版的解读说明
3. 关键设计元素清单
4. 推荐的负面提示词(negative prompt,避免常见问题)

【英文 prompt 写法】
- 主体描述放在最前面
- 风格关键词(midjourney style / watercolor / flat design / photorealistic...)
- 光照描述(natural lighting / cinematic lighting / soft light...)
- 镜头描述(close-up / wide shot / macro...)
- 配色描述(以 X 色调为主, 包含 Y, Z)
- 细节修饰(high detail / 8k / professional photography)
- 末尾加 --ar 比例(海报竖版 9:16, Banner 横版 16:9, Logo 1:1)

【风格库参考】
- 海报 poster: minimalist poster, bold typography, graphic design
- 横幅 banner: web banner, hero image, gradient background
- Logo logo: vector logo, simple geometric, modern branding
- 插图 illustration: digital illustration, flat design, isometric
- 商务 business: corporate, professional, clean
- 节日 holiday: festive, celebratory, vibrant colors
- 国风 chinese: traditional chinese style, ink wash painting, chinese elements
- 写实 photorealistic: photorealistic, professional photography, sharp focus
- 抽象 abstract: abstract art, geometric shapes, modern
- 卡通 cartoon: cartoon style, cute, vibrant

【输出格式】
# 设计 Prompt

## 📝 English Prompt
```
...英文 prompt...
```

## 💡 设计解读
(中文说明这个 prompt 的设计思路、为什么用这些关键词)

## 🎨 关键元素
- 主体: ...
- 配色: ...
- 风格: ...
- 光照: ...
- 比例: ...

## ⚠️ Negative Prompt(避免)
- ...(避免出现的内容,如 blurry, low quality, text watermark...)"""


PROMPT_REGISTRY = {
    "poster": {
        "label": "海报",
        "ratio": "9:16",
        "extra_hint": "竖版构图,主体居中,文字位置预留上方或下方",
    },
    "banner": {
        "label": "横幅/Banner",
        "ratio": "16:9",
        "extra_hint": "横版构图,主体可放左右,中央留白可加标题",
    },
    "logo": {
        "label": "Logo",
        "ratio": "1:1",
        "extra_hint": "简洁几何,矢量风格,主体居中,纯色背景",
    },
    "illustration": {
        "label": "插画",
        "ratio": "1:1",
        "extra_hint": "数字插画风格,色彩鲜明,适合社交媒体传播",
    },
    "social": {
        "label": "朋友圈/小红书封面",
        "ratio": "3:4",
        "extra_hint": "竖版,主体醒目,适合手机端展示",
    },
    "ppt": {
        "label": "PPT 封面",
        "ratio": "16:9",
        "extra_hint": "简洁商务,留白多,适合放标题文字",
    },
}


def get_prompt(task: str) -> ChatPromptTemplate:
    if task not in PROMPT_REGISTRY:
        raise ValueError(
            f"不支持的设计类型: {task}。"
            f"可选: {', '.join(PROMPT_REGISTRY.keys())}"
        )
    return ChatPromptTemplate.from_messages([
        ("system", DESIGNER_SYSTEM),
        ("user",
         "设计类型: {design_type}\n"
         "主题/产品: {subject}\n"
         "风格偏好: {style}\n"
         "主色调: {color}\n"
         "使用场景: {scene}\n"
         "额外要求: {extra}"),
    ])