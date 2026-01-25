import os
import time
import json
import glob
from flask import Flask, request, jsonify, send_file, render_template
from apscheduler.schedulers.background import BackgroundScheduler
import yt_dlp

# --- Config ---
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# --- Flask App ---
# template_folder='.' means index.html is in the root directory
server = Flask(__name__, template_folder='.', static_folder=DOWNLOAD_FOLDER)

# --- Auto Delete Logic (7 Minutes) ---
def delete_old_files():
    now = time.time()
    cutoff = 7 * 60  # 7 minutes in seconds
    
    files = glob.glob(os.path.join(DOWNLOAD_FOLDER, '*'))
    for f in files:
        if os.path.isfile(f):
            file_creation_time = os.path.getmtime(f)
            if now - file_creation_time > cutoff:
                try:
                    os.remove(f)
                    print(f"[🗑] Deleted old file: {f}")
                except Exception as e:
                    print(f"Error deleting {f}: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(delete_old_files, 'interval', minutes=1)
scheduler.start()

# --- Helpers ---
def get_video_info(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'cookiefile': 'cookies.txt',  # <--- ADDED: Uses your uploaded cookies.txt
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        print(f"Error fetching info: {e}")
        return None

# --- Routes ---
@server.route('/')
def index():
    return render_template('index.html')

@server.route('/get-info', methods=['POST'])
def get_info():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    
    info = get_video_info(url)
    if not info:
        return jsonify({"error": "Failed to fetch video info"}), 500

    formats = info.get('formats', [])
    
    # Filter Video Only (high quality) and Audio Only
    video_options = []
    audio_options = []
    
    seen_res = set()

    for f in formats:
        # Get Videos
        if f.get('vcodec') != 'none' and f.get('acodec') == 'none':
            res = f.get('height')
            if res and res not in seen_res:
                video_options.append({
                    'format_id': f['format_id'],
                    'resolution': f'{res}p',
                    'ext': f['ext']
                })
                seen_res.add(res)
        
        # Get Audios
        if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
            audio_options.append({
                'format_id': f['format_id'],
                'ext': f['ext'],
                'note': f.get('format_note', 'audio')
            })

    # Sort videos by resolution (high to low)
    video_options.sort(key=lambda x: int(x['resolution'][:-1]), reverse=True)

    return jsonify({
        "title": info.get('title'),
        "thumbnail": info.get('thumbnail'),
        "duration": info.get('duration_string'),
        "videos": video_options[:6], # Top 6 resolutions
        "audios": audio_options[:3]  # Top 3 audio options
    })

@server.route('/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url')
    video_id = data.get('video_id')
    audio_id = data.get('audio_id')
    
    timestamp = int(time.time())
    # Generate a safe filename
    filename = f"video_{timestamp}.mp4"
    output_path = os.path.join(DOWNLOAD_FOLDER, filename)

    # yt-dlp options to merge video and audio
    ydl_opts = {
        'format': f'{video_id}+{audio_id}', # Merge specific video + specific audio
        'outtmpl': output_path,
        'merge_output_format': 'mp4',
        'quiet': True,
        'cookiefile': 'cookies.txt',  # <--- ADDED: Uses your uploaded cookies.txt here too
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        return jsonify({
            "status": "success",
            "file_url": f"/files/{filename}",
            "filename": filename
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@server.route('/files/<path:filename>')
def serve_file(filename):
    return send_file(os.path.join(DOWNLOAD_FOLDER, filename))

@server.route('/history')
def get_history():
    # List all files currently in downloads folder
    files = []
    for f in os.listdir(DOWNLOAD_FOLDER):
        if f.endswith('.mp4'):
             files.append({"filename": f, "url": f"/files/{f}"})
    return jsonify(files)

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
