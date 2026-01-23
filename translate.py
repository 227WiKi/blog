import os
import re
import sys
import time
from google import genai
from google.genai import types
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from dotenv import load_dotenv
load_dotenv()

# ================= Config =================
API_KEY = os.getenv("GEMINI_API_KEY")

POSTS_DIR = "source/_posts"

MAX_WORKERS = 1

MODEL_NAME = "gemini-2.5-pro"
# ===========================================

if not API_KEY:
    print("[ERROR] GEMINI_API_KEY environment variable not set.")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)

SYSTEM_PROMPT = """
你是一位 22/7 (ナナニジ) 的资深粉丝兼字幕组翻译。
任务：将 HTML/Markdown 博客从日语翻译成中文。

**输出限制（至关重要）**：
1.  **只输出翻译后的中文内容**。
2.  **绝对不要**输出日语原文！(原文由外部程序保留)
3.  **不要**包含 Markdown 代码块标记 (如 ```html)。

**图片处理规则**：
- 当你在文中遇到 `<img>` 标签或 `![alt](url)` 时：
- **不要**保留原图片链接（链接已在原文中保存）。
- **必须**在对应位置输出一个占位符：
  `<div class="nananiji-img-placeholder"></div>`

**【成员关系与称呼规范】**
1. **前辈**：
   - **サリー** -> **莎莉** (无小姐，无 English)。
   - 如果出现了さん就加上前辈
   - 无法判断是前辈还是后辈就去掉 `さん`，直呼其名或加酱。
2. **同期/后辈**：
   - 去掉 `さん`，直呼其名或加酱。
   - **望月りの** -> **りの** (保留原名)。
3. **外部人员**：
   - 假名名字**保留原文**。
4. **昵称**：
    - 无法确定的昵称请保留原文或使用原名代替。
    - れいにゃん -> 玲喵
    - まにゃん　-> 茉喵

**语气风格**：
   - 保持“偶像语气”：元气、可爱、亲切、带一点少女的碎碎念感。
   - 拒绝“机翻味”：不要用公文写作的语气，要像是在写粉丝信。
   - 第一人称：如果原文自称“私(watashi)”或“名字”，通顺情况下译为“我”。如果原文是为了卖萌故意用第三人称（如“樱月觉得...”），则保留第三人称。
   - アニラ -> 周年 Live
   - リリイベ -> 发售纪念活动
   - 特典会 -> 特典会 
   
**【红线规则】**
1. **严禁注音/英文** (如: 樱月(Satsuki) -> ❌)。
2. 对于成员之间的称呼**严禁“小姐/女士”**，对于团外的嘉宾等出现的人物，出于尊重需要使用此类尊称，但是成员之间严禁使用。
3. **颜文字/Emoji 保护**：
   - 绝对不要删除或“翻译”颜文字（如 `( ˙꒳​˙ )`、`(*>_<*)ﾉ`）。
   - 绝对保留所有 Emoji（✨、🥺、🍊）。
   - 不要试图修复颜文字中的标点符号。

📄 **【输出格式】**
- 绝对保留 `<br>` 换行符。
- 只输出翻译后的内容，不要输出 Markdown 代码块标记。
"""

def split_frontmatter(content):
    match = re.match(r'^\s*(-{3,}\s*\n.*?\n-{3,}\s*\n)(.*)$', content, re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    return "", content

def check_is_translated(fm_content):
    if re.search(r'^translated:\s*true', fm_content, re.MULTILINE):
        return True
    return False

def add_translated_tag(fm_content):
    if re.search(r'^translated:', fm_content, re.MULTILINE):
        return re.sub(r'^translated:.*$', 'translated: true', fm_content, flags=re.MULTILINE)
    pattern = r'(-{3,}\s*)$'
    if re.search(pattern, fm_content.strip()):
        return re.sub(pattern, r'translated: true\n\1', fm_content.strip())
    else:
        return fm_content.strip() + "\ntranslated: true\n"

def process_single_file(filepath):
    filename = os.path.basename(filepath)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            full_content = f.read()

        fm_chunk, body_chunk = split_frontmatter(full_content)
        
        if check_is_translated(fm_chunk):
            return None 

        if 'article-translated-cn' in body_chunk:
             new_fm = add_translated_tag(fm_chunk)
             with open(filepath, 'w', encoding='utf-8') as f:
                 f.write(new_fm + "\n" + body_chunk)
             return f"[FIX] Added missing metadata tag: {filename}"

        if len(body_chunk) < 10:
             return f"[SKIP] Too short: {filename}"

        # === AI 翻译 ===
        max_retries = 5 
        content_cn = ""
        
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=MODEL_NAME, 
                    contents=f"{SYSTEM_PROMPT}\n\n=== 待翻译原文 ===\n{body_chunk}",
                    config=types.GenerateContentConfig(
                        safety_settings=[
                            types.SafetySetting(
                                category="HARM_CATEGORY_HATE_SPEECH",
                                threshold="BLOCK_NONE"
                            ),
                            types.SafetySetting(
                                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                                threshold="BLOCK_NONE"
                            ),
                            types.SafetySetting(
                                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                                threshold="BLOCK_NONE"
                            ),
                            types.SafetySetting(
                                category="HARM_CATEGORY_HARASSMENT",
                                threshold="BLOCK_NONE"
                            ),
                        ]
                    )
                )
                if response.text:
                    content_cn = response.text.strip()
                    break # 成功拿到内容，跳出循环
            except Exception as api_error:
                error_str = str(api_error)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    wait_time = 30 
                    print(f"⏳ [RATE LIMIT] Sleeping 30s for {filename}...")
                    time.sleep(wait_time)
                else:
                    if attempt == max_retries - 1:
                        print(f" API Error on {filename}: {api_error}")
                    time.sleep(2)

        if not content_cn:

            return f"[ABORT] Blocked or Failed. Leaving unchanged: {filename}"

        # === 只有成功翻译后，才执行下面的代码 ===
        
        content_cn = re.sub(r'^```(html|markdown)?\s*', '', content_cn)
        content_cn = re.sub(r'\s*```$', '', content_cn)

        # 组装
        new_fm = add_translated_tag(fm_chunk)
        
        final_output = f"""{new_fm}
<div class="article-content-container">
    <div class="article-original-jp">
{body_chunk}
    </div>
    <div class="article-translated-cn" style="display:none;">
{{% raw %}}
{content_cn}
{{% endraw %}}
    </div>
</div>
"""

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(final_output)
            
        time.sleep(2) 

        return None

    except Exception as e:
        return f"[ERROR] {filename}: {str(e)}"

def main():
    if not os.path.exists(POSTS_DIR):
        print(f"[ERROR] Path not found: {POSTS_DIR}")
        sys.exit(1)

    all_files = [os.path.join(POSTS_DIR, f) for f in os.listdir(POSTS_DIR) if f.endswith('.md')]
    all_files.sort(reverse=True) 

    print(f"[INFO] Scanning {len(all_files)} files...")

    pending_files = []
    
    for filepath in all_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                head_sample = f.read(1000) 
            
            match = re.match(r'^\s*(-{3,}\s*\n.*?\n-{3,}\s*\n)', head_sample, re.DOTALL)
            if match:
                fm_only = match.group(1)
                if check_is_translated(fm_only):
                    continue 
            
            pending_files.append(filepath)

        except Exception as e:
            print(f"[WARN] Cannot read {filepath}, skipping.")

    if not pending_files:
        print("[INFO] No new files to translate.")
        return

    print(f"[INFO] Processing {len(pending_files)} files...")
    print(f"[INFO] Running safely with {MAX_WORKERS} thread(s).")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(tqdm(executor.map(process_single_file, pending_files), total=len(pending_files), unit="files"))

    logs = [r for r in results if r is not None]
    if logs:
        print("\n" + "="*30)
        for log in logs:
            print(log)
        print("="*30)
    else:
        print("\n🎉 All Done!")

if __name__ == "__main__":
    main()