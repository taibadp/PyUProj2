import os
import io
import uuid
import logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
#from urllib.parse import parse_header
from email.message import Message
from PIL import Image

# postgresql
import psycopg2
from urllib.parse import parse_qs

# ----------------------------------------------------------------------
# Налаштування шляхів та логування
# ----------------------------------------------------------------------
UPLOAD_DIR = '/app/images'
LOG_DIR = '/app/logs'

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

log_file_path = os.path.join(LOG_DIR, 'app.log')


# db
DB_HOST = os.environ.get('DB_HOST', 'db')
DB_NAME = os.environ.get('DB_NAME', 'images_db')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'password')

def get_db_connection():
    return psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port="5432"
    )

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id SERIAL PRIMARY KEY,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                size INTEGER NOT NULL,
                upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_type TEXT NOT NULL
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("Успіх: таблиця images ініціалізована в БД.")
    except Exception as e:
        logger.info(f"Помилка ініціалізації БД: {e}")

init_db()


def parse_header(header_string):
    # Create a temporary message object
    msg = Message()
    # Add the header string to it
    msg['Content-Type'] = header_string

    # Get the main value (e.g., 'text/html')
    main_value = msg.get_content_type()

    # Get all parameters as a dictionary (e.g., {'charset': 'utf-8'})
    params = dict(msg.get_params()[1:])  # Skip the first item since it's the main value

    return main_value, params


# Кастомний форматер для вимоги ТЗ: [2025-01-24 14:00:00] Успіх: ...
class CustomFormatter(logging.Formatter):
    def format(self, record):
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f"[{now_str}] {record.getMessage()}"

logger = logging.getLogger("ImageServer")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
file_handler.setFormatter(CustomFormatter())
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(CustomFormatter())
logger.addHandler(stream_handler)


# ----------------------------------------------------------------------
# Обробник HTTP-запитів
# ----------------------------------------------------------------------
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif'}
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):

    def send_json_response(self, status_code, data):
        import json
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # 1. Нормалізуємо шлях (видаляємо зайві ./ та / в кінці)
        clean_path = self.path.split('?')[0]  # ігноруємо query-параметри (?v=1.0)
        
        # 2. Головна сторінка
        if clean_path in ('/', '/index.html', './'):
            # Віддаємо HTML-шаблон із папки static
            template_path = os.path.join('/app/static', 'index.html')
            
            # Якщо запустили локально без Docker:
            if not os.path.exists(template_path):
                template_path = os.path.join(os.path.dirname(__file__), 'static', 'index.html')

            try:
                with open(template_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_json_response(404, {"error": "HTML-шаблон не знайдено"})
            return

        # --- ДОДАТИ: Сторінка завантаження (/upload) ---
        if clean_path in ('/upload', '/upload.html', '/upload/', '/static/form/upload.html'):
            template_path = os.path.join('/app/static/form', 'upload.html')
            if not os.path.exists(template_path):
                template_path = os.path.join(os.path.dirname(__file__), 'static', 'form', 'upload.html')
            try:
                with open(template_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_json_response(404, {"error": "HTML-шаблон не знайдено"})
            return

            # Збереження метаданих в PostgreSQL
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO images (filename, original_name, size, file_type) VALUES (%s, %s, %s, %s)",
                    (unique_filename, original_filename, len(file_data), ext.lstrip('.'))
                )
                conn.commit()
                cursor.close()
                conn.close()
            except Exception as db_err:
                logger.info(f"Помилка збереження в БД: {db_err}")

        # --- ДОДАТИ: Сторінка галереї (/images) ---
        if clean_path in ('/images', '/images.html', '/images/', '/static/form/images.html'):
            template_path = os.path.join('/app/static/form', 'images.html')
            if not os.path.exists(template_path):
                template_path = os.path.join(os.path.dirname(__file__), 'static', 'form', 'images.html')
            try:
                with open(template_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_json_response(404, {"error": "HTML-шаблон не знайдено"})
            return

        # 3. Обробка статичних файлів з папки /static/
        if clean_path.startswith('/static/'):
            # Відсікаємо префікс /static/ для отримання відносного шляху файлу
            relative_filepath = clean_path[8:] 
            file_path = os.path.join('/app/static', relative_filepath)
            
            if os.path.exists(file_path) and os.path.isfile(file_path):
                import mimetypes
                mime_type, _ = mimetypes.guess_type(file_path)
                
                with open(file_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', mime_type or 'application/octet-stream')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
        
        # 3.5. Обробка зображень з папки /images/
        if clean_path.startswith('/images/'):
            relative_filepath = clean_path[8:] 
            file_path = os.path.join(UPLOAD_DIR, relative_filepath)
            
            if os.path.exists(file_path) and os.path.isfile(file_path):
                import mimetypes
                mime_type, _ = mimetypes.guess_type(file_path)
                
                with open(file_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', mime_type or 'application/octet-stream')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        # Сторінка зі списком зображень (з пагінацією)
        if clean_path == '/images-list':
            query_string = self.path.split('?')[1] if '?' in self.path else ''
            query_params = parse_qs(query_string)
            try:
                page = int(query_params.get('page', [1])[0])
            except ValueError:
                page = 1
            
            limit = 10
            offset = (page - 1) * limit
            images_data = []
            total_pages = 1

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM images;")
                total_count = cursor.fetchone()[0]
                total_pages = max(1, (total_count + limit - 1) // limit)

                cursor.execute(
                    "SELECT id, filename, original_name, size, upload_time, file_type FROM images ORDER BY upload_time DESC LIMIT %s OFFSET %s;",
                    (limit, offset)
                )
                for row in cursor.fetchall():
                    images_data.append({
                        "id": row[0], "filename": row[1], "original_name": row[2],
                        "size_kb": round(row[3] / 1024, 1), "upload_time": str(row[4]), "file_type": row[5]
                    })
                cursor.close()
                conn.close()
            except Exception as e:
                logger.info(f"Помилка читання з БД: {e}")

            html_rows = ""
            for img in images_data:
                html_rows += f"""
                <tr>
                    <td><a href="/images/{img['filename']}" target="_blank">{img['filename']}</a></td>
                    <td>{img['original_name']}</td>
                    <td>{img['size_kb']} КБ</td>
                    <td>{img['upload_time']}</td>
                    <td>{img['file_type']}</td>
                    <td><a href="/delete/{img['id']}" onclick="return confirm('Видалити зображення?');" style="color: #ff4d4d; text-decoration: none; font-weight: bold;">Видалити</a></td>
                </tr>
                """
            if not html_rows:
                html_rows = "<tr><td colspan='6' style='text-align: center;'>Немає завантажених зображень</td></tr>"

            prev_disabled = "pointer-events: none; opacity: 0.5;" if page <= 1 else ""
            next_disabled = "pointer-events: none; opacity: 0.5;" if page >= total_pages else ""

            html_content = f"""<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <title>Список зображень</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #151515; color: #fff; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; background: #222; }}
        th, td {{ border: 1px solid #444; padding: 12px; text-align: left; }}
        th {{ background: #333; }}
        a {{ color: #4da6ff; text-decoration: none; }}
        .pagination {{ margin-top: 20px; display: flex; gap: 15px; align-items: center; }}
        .btn {{ background: #007bff; color: white; padding: 8px 15px; border-radius: 4px; display: inline-block; }}
    </style>
</head>
<body>
    <h1>Список завантажених зображень 📸</h1>
    <p><a href="/" class="btn">← На головну / Завантаження</a></p>
    <table>
        <tr>
            <th>Назва файлу</th><th>Оригінальна назва</th><th>Розмір (КБ)</th><th>Дата завантаження</th><th>Тип файлу</th><th>Дії</th>
        </tr>
        {html_rows}
    </table>
    <div class="pagination">
        <a class="btn" href="/images-list?page={page - 1}" style="{prev_disabled}">Попередня</a>
        <span>Сторінка {page} з {total_pages}</span>
        <a class="btn" href="/images-list?page={page + 1}" style="{next_disabled}">Наступна</a>
    </div>
</body>
</html>"""
            body = html_content.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # Видалення зображення за ID
        if clean_path.startswith('/delete/'):
            try:
                img_id = clean_path.split('/')[2]
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT filename FROM images WHERE id = %s;", (img_id,))
                row = cursor.fetchone()
                if row:
                    filename = row[0]
                    file_path = os.path.join(UPLOAD_DIR, filename)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    cursor.execute("DELETE FROM images WHERE id = %s;", (img_id,))
                    conn.commit()
                    logger.info(f"Успіх: зображення з ID {img_id} видалено.")
                cursor.close()
                conn.close()
            except Exception as e:
                logger.info(f"Помилка видалення: {e}")

            self.send_response(303)
            self.send_header('Location', '/images-list')
            self.end_headers()
            return
        
        # 4. Якщо нічого не підійшло
        self.send_json_response(404, {"error": "Файл або маршрут не знайдено"})
    
    def do_POST(self):
        if self.path == '/upload':
            try:
                content_type = self.headers.get('Content-Type')
                if not content_type or not content_type.startswith('multipart/form-data'):
                    msg = "Некоректний тип запиту. Очікується multipart/form-data."
                    logger.info(f"Помилка: {msg}")
                    self.send_json_response(400, {"error": msg})
                    return

                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > MAX_FILE_SIZE + 1024 * 10:  # Запас на заголовки multipart
                    msg = "Розмір файлу перевищує ліміт 5 МБ."
                    logger.info(f"Помилка: {msg}")
                    self.send_json_response(400, {"error": msg})
                    return

                # Зчитування тіла запиту
                body = self.rfile.read(content_length)

                # Парсинг multipart/form-data
                _, pdict = parse_header(content_type)
                boundary = pdict.get('boundary')
                if not boundary:
                    msg = "Не знайдено boundary у multipart запиті."
                    logger.info(f"Помилка: {msg}")
                    self.send_json_response(400, {"error": msg})
                    return

                boundary_bytes = boundary.encode('ascii')
                parts = body.split(b'--' + boundary_bytes)

                file_data = None
                original_filename = "unknown"

                for part in parts:
                    if b'Content-Disposition' in part:
                        headers_part, data_part = part.split(b'\r\n\r\n', 1)
                        headers_text = headers_part.decode('iso-8859-1')
                        
                        if 'filename="' in headers_text:
                            original_filename = headers_text.split('filename="')[1].split('"')[0]
                            # Видаляємо кінцевий boundary tail (\r\n)
                            if data_part.endswith(b'\r\n'):
                                data_part = data_part[:-2]
                            file_data = data_part
                            break

                if not file_data:
                    msg = "Файл не знайдено у запиті."
                    logger.info(f"Помилка: {msg}")
                    self.send_json_response(400, {"error": msg})
                    return

                # Перевірка розміру байтів самого файлу
                if len(file_data) > MAX_FILE_SIZE:
                    msg = f"Розмір файлу ({original_filename}) перевищує 5 МБ."
                    logger.info(f"Помилка: {msg}")
                    self.send_json_response(400, {"error": msg})
                    return

                # Перевірка розширення файлу
                ext = os.path.splitext(original_filename)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    msg = f"Непідтримуваний формат файлу ({original_filename})."
                    logger.info(f"Помилка: {msg}")
                    self.send_json_response(400, {"error": msg})
                    return

                # Додаткова валідація вмісту через Pillow
                try:
                    img = Image.open(io.BytesIO(file_data))
                    img.verify()
                except Exception:
                    msg = f"Файл {original_filename} не є валідним зображенням."
                    logger.info(f"Помилка: {msg}")
                    self.send_json_response(400, {"error": msg})
                    return

                # Генерація унікального імені
                unique_filename = f"{uuid.uuid4().hex}{ext}"
                save_path = os.path.join(UPLOAD_DIR, unique_filename)

                # Збереження на диск
                with open(save_path, 'wb') as f:
                    f.write(file_data)

                logger.info(f"Успіх: зображення {unique_filename} (оригінал: {original_filename}) завантажено.")

                image_url = f"/images/{unique_filename}"
                self.send_json_response(200, {
                    "message": "Зображення успішно завантажено",
                    "id": unique_filename,
                    "url": image_url
                })

            except Exception as e:
                msg = f"Внутрішня помилка сервера: {str(e)}"
                logger.info(f"Помилка: {msg}")
                self.send_json_response(500, {"error": "Внутрішня помилка сервера"})
        else:
            self.send_json_response(404, {"error": "Маршрут не знайдено"})


def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Сервер запущено на порту {port}...")
    httpd.serve_forever()


if __name__ == '__main__':
    run()