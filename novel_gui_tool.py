import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk
import os
import sys
import threading
import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ========== 资源路径适配器 ==========
def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ========== 工具函数 ==========
def open_output_folder(folder_path=None):
    folder_path = folder_path or "./novel_texts"
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    if sys.platform == "win32":
        os.startfile(folder_path)
    elif sys.platform == "darwin":
        os.system(f"open '{folder_path}'")
    else:
        os.system(f"xdg-open '{folder_path}'")

def select_output_dir(var):
    path = filedialog.askdirectory()
    if path:
        var.set(path)

def clear_cache(output_dir_var):
    folder = output_dir_var.get()
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.endswith(".txt"):
                os.remove(os.path.join(folder, f))
        messagebox.showinfo("提示", "缓存清理完成！")
    else:
        messagebox.showwarning("警告", "目录不存在")

# ========== 合并TXT逻辑 ==========
def merge_txt_files(output_text, progress_label, input_dir, output_dir_entry, filename_entry):
    INPUT_DIR = input_dir.get()
    OUTPUT_DIR = output_dir_entry.get().strip()
    FILENAME = filename_entry.get().strip()

    if not FILENAME:
        messagebox.showerror("错误", "请输入输出文件名！")
        return

    OUTPUT_FILE = os.path.join(OUTPUT_DIR, FILENAME)

    def clean_content(content):
        cleaned = re.sub(r'（本页完）\s*\n链接：https?://\S+\s*', '', content)
        cleaned = re.sub(r'链接：https?://\S+\s*', '', cleaned)
        cleaned = re.sub(r'（本页完）\s*', '', cleaned)
        if cleaned.startswith('\ufeff'):
            cleaned = cleaned[1:]
        cleaned = re.sub(r'\r\n', '\n', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.strip()

    output_text.insert(tk.END, "=== 纯净版小说合并工具 ===\n")
    output_text.insert(tk.END, f"输入目录: {os.path.abspath(INPUT_DIR)}\n")
    output_text.insert(tk.END, f"输出文件: {os.path.abspath(OUTPUT_FILE)}\n")

    if not os.path.exists(INPUT_DIR):
        output_text.insert(tk.END, f"错误：目录不存在 - {INPUT_DIR}\n")
        return

    txt_files = sorted(
        [f for f in os.listdir(INPUT_DIR) if f.endswith('.txt')],
        key=lambda x: [int(s) if s.isdigit() else s.lower() for s in re.split('([0-9]+)', x)]
    )

    if not txt_files:
        output_text.insert(tk.END, "错误：目录中没有找到TXT文件\n")
        return

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
        for i, filename in enumerate(txt_files, 1):
            filepath = os.path.join(INPUT_DIR, filename)

            try:
                with open(filepath, 'r', encoding='utf-8') as infile:
                    content = infile.read()
                cleaned_content = clean_content(content)
                outfile.write(cleaned_content + '\n\n')
                output_text.insert(tk.END, f"[{i}/{len(txt_files)}] 已处理: {filename}\n")
                progress_label.config(text=f"进度：{i}/{len(txt_files)} 章节")
                progress_bar["value"] = (i / len(txt_files)) * 100
                root.update_idletasks()
            except Exception as e:
                output_text.insert(tk.END, f"处理失败: {filename} - {str(e)}\n")
                continue

    output_text.insert(tk.END, f"\n✅ 合并完成！共处理 {len(txt_files)} 个章节\n")
    output_text.insert(tk.END, f"输出文件大小: {os.path.getsize(OUTPUT_FILE)/1024:.2f} KB\n")
    progress_label.config(text="就绪")
    progress_bar["value"] = 0

# ========== 爬虫逻辑 ==========
class CrawlerThread(threading.Thread):
    def __init__(self, start_url, log_box, progress_label, stop_flag, max_pages, output_dir):
        super().__init__()
        self.start_url = start_url
        self.log_box = log_box
        self.progress_label = progress_label
        self.stop_flag = stop_flag
        self.max_pages = max_pages
        self.output_dir = output_dir

    def run(self):
        current_url = self.start_url
        visited_urls = set()
        chapter_pages = 1
        total_crawled = 0

        while current_url and current_url not in visited_urls and not self.stop_flag["stop"] and total_crawled < self.max_pages:
            self.log_box.insert(tk.END, f"\n正在抓取：{current_url}\n")
            self.log_box.see(tk.END)
            visited_urls.add(current_url)

            try:
                response = requests.get(current_url, headers={"User-Agent": "Edg/137.0.0.0"}, timeout=10)
                response.raise_for_status()
                response.encoding = 'utf-8'
                html = response.text
            except Exception as e:
                self.log_box.insert(tk.END, f"请求失败：{e}\n")
                break

            soup = BeautifulSoup(html, 'html.parser')
            chapter_title_tag = soup.find('h1') or soup.find('div', class_='title')
            chapter_title = chapter_title_tag.text.strip() if chapter_title_tag else "未知章节"

            cleaned_text = clean_content(html, current_url)
            save_chapter(cleaned_text, chapter_title, chapter_pages, self.output_dir)
            self.log_box.insert(tk.END, f"已保存章节：{chapter_title}_{chapter_pages:03d}.txt\n")
            self.progress_label.config(text=f"已爬取：{total_crawled+1} 页")
            progress_bar["value"] = (total_crawled / self.max_pages) * 100
            root.update_idletasks()
            chapter_pages += 1
            total_crawled += 1

            current_url = parse_pagination(html, current_url)
            time.sleep(0.3)

        if self.stop_flag["stop"]:
            self.log_box.insert(tk.END, "🛑 用户主动终止爬虫\n")
        else:
            self.log_box.insert(tk.END, "=== 爬取完成 ===\n")
        self.progress_label.config(text="就绪")
        progress_bar["value"] = 0

def clean_content(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    for element in soup.find_all(['script', 'style', 'img', 'noscript']):
        element.decompose()
    content_div = soup.find('div', id='content') or soup.find('pre', id='content')
    if not content_div:
        return "未找到有效内容"
    lines = []
    for line in content_div.stripped_strings:
        if line.startswith(('本书来自', '广告', '最新章节')) or len(line.strip()) < 4:
            continue
        lines.append('　　' + line.strip())
    lines.append(f"\n（本页完）链接：{base_url}")
    return '\n'.join(lines)

def parse_pagination(html, current_url):
    soup = BeautifulSoup(html, 'html.parser')
    next_links = soup.find_all('a', href=True)
    for link in next_links:
        if link.text.strip() == "下一页":
            return urljoin(current_url, link['href'])
    for link in next_links:
        if link.text.strip() in ["下一章", "下章"]:
            return urljoin(current_url, link['href'])
    return None

def save_chapter(text, chapter_title, page_num, output_dir):
    filename = f"{chapter_title}_{page_num:03d}.txt"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8-sig') as f:
        f.write(text)

# ========== GUI 主界面 ==========
root = tk.Tk()
root.title("小说工具合集 - GUI 版 v8.0")
root.geometry("800x600")

# 设置图标
try:
    icon_path = get_resource_path("favicon.ico")
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)
except Exception:
    pass

# 设置现代风格
style = ttk.Style()
style.theme_use('clam')  # 使用现代主题
style.configure("TButton", padding=6, relief="flat", background="#4CAF50", foreground="white")
style.map("TButton", background=[('active', '#45a049')])
style.configure("TLabel", font=("微软雅黑", 10))
style.configure("TEntry", padding=5)

# 主框架
main_frame = ttk.Frame(root, padding=10)
main_frame.pack(fill=tk.BOTH, expand=True)

# 输出目录
output_dir_var = tk.StringVar(value=get_resource_path("novel_texts"))
ttk.Label(main_frame, text="输出目录:").grid(row=0, column=0, sticky="w", pady=5)
ttk.Entry(main_frame, textvariable=output_dir_var, width=50).grid(row=0, column=1, padx=5, pady=5)
ttk.Button(main_frame, text="选择目录", command=lambda: select_output_dir(output_dir_var)).grid(row=0, column=2, pady=5)

# 起始URL
url_var = tk.StringVar(value="https://www.22biqu.com/biqu36903/40768959.html") 
ttk.Label(main_frame, text="起始地址:").grid(row=1, column=0, sticky="w", pady=5)
ttk.Entry(main_frame, textvariable=url_var, width=60).grid(row=1, column=1, columnspan=2, padx=5, pady=5)

# 页数限制
pages_var = tk.IntVar(value=10)
ttk.Label(main_frame, text="爬取页数:").grid(row=2, column=0, sticky="w", pady=5)
ttk.Spinbox(main_frame, from_=1, to=1000, textvariable=pages_var, width=10).grid(row=2, column=1, padx=5, pady=5)

# 输出文件路径 + 文件名
output_dir_entry = tk.StringVar(value=os.path.dirname(get_resource_path("novel_texts")))
filename_entry = tk.StringVar(value="全本小说.txt")
ttk.Label(main_frame, text="完整小说路径:").grid(row=3, column=0, sticky="w", pady=5)
ttk.Entry(main_frame, textvariable=output_dir_entry, width=40).grid(row=3, column=1, padx=5, pady=5)
ttk.Entry(main_frame, textvariable=filename_entry, width=20).grid(row=3, column=2, padx=5, pady=5)
ttk.Button(main_frame, text="选择目录", command=lambda: select_output_dir(output_dir_entry)).grid(row=3, column=3, pady=5)

# 控制按钮区
btn_frame = ttk.Frame(main_frame)
btn_frame.grid(row=4, column=0, columnspan=4, pady=10)

crawl_btn = ttk.Button(btn_frame, text="开始爬虫", width=15)
stop_flag = {"stop": False}
stop_btn = ttk.Button(btn_frame, text="终止任务", width=15, command=lambda: stop_flag.update(stop=True))
merge_btn = ttk.Button(btn_frame, text="导出完整小说", width=15)
open_dir_btn = ttk.Button(btn_frame, text="打开输出目录", width=15, command=lambda: open_output_folder(output_dir_var.get()))
clear_cache_btn = ttk.Button(btn_frame, text="清理缓存", width=15, command=lambda: clear_cache(output_dir_var))

crawl_btn.grid(row=0, column=0, padx=5)
stop_btn.grid(row=0, column=1, padx=5)
merge_btn.grid(row=0, column=2, padx=5)
open_dir_btn.grid(row=0, column=3, padx=5)
clear_cache_btn.grid(row=0, column=4, padx=5)

# 日志输出框
log_box = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, width=80, height=15)
log_box.grid(row=5, column=0, columnspan=4, padx=5, pady=10)

# 进度条
progress_bar = ttk.Progressbar(main_frame, orient="horizontal", length=600, mode="determinate")
progress_bar.grid(row=6, column=0, columnspan=4, pady=5)

# 进度标签
progress_label = ttk.Label(main_frame, text="就绪")
progress_label.grid(row=7, column=0, columnspan=4, pady=5)

# 绑定按钮点击事件
crawl_btn.config(command=lambda: CrawlerThread(
    url_var.get(), log_box, progress_label, stop_flag,
    pages_var.get(), output_dir_var.get()
).start())

merge_btn.config(command=lambda: threading.Thread(
    target=merge_txt_files, args=(log_box, progress_label, output_dir_var, output_dir_entry, filename_entry)
).start())

if __name__ == "__main__":
    root.mainloop()