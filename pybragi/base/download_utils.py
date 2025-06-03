
import requests
import logging
import os
from typing import Optional, Tuple
import hashlib
import tempfile
import shutil

from tqdm import tqdm

def url_content_length(url: str):
    try:
        with requests.head(url, allow_redirects=True) as head_response:
            head_response.raise_for_status()  # 检查 HTTP 状态码
            remote_size_str = head_response.headers.get('Content-Length')
            if not remote_size_str:
                remote_size = None
                logging.warning(f"Content-Length not found in {url}")
                return 0
            
            remote_size = int(remote_size_str)
            logging.info(f"{url} remote size: {remote_size} bytes")
            return remote_size
    except requests.exceptions.RequestException as e:
        logging.error(f"获取远程文件信息失败: {e}")
        return 0

def check_file_integrity(
    path: str,
    remote_size: int,
    remote_sha256: Optional[str] = None,
    remote_md5: Optional[str] = None,
):
    if not os.path.exists(path):
        return False

    local_size = os.path.getsize(path)

    if remote_size and local_size != remote_size:
        logging.warning(f"local file size: {local_size} != remote file size: {remote_size}")
        return False
    
    if not remote_sha256 and not remote_md5:
        return True
    
    local_sha256 = hashlib.sha256()
    local_md5 = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                local_sha256.update(chunk)
                local_md5.update(chunk)
    except Exception as e:
        logging.error(f"read local file or calculate hash failed: {e}")
        return False

    local_sha256_hex = local_sha256.hexdigest()
    local_md5_hex = local_md5.hexdigest()
    # logging.info(f"local md5: {local_md5_hex}")

    if remote_sha256 and local_sha256_hex != remote_sha256:
        logging.warning(f"local sha256: {local_sha256_hex} != remote sha256: {remote_sha256}")
        return False
    if remote_md5 and local_md5_hex != remote_md5:
        logging.warning(f"local md5: {local_md5_hex} != remote md5: {remote_md5}")
        return False
    
    return True

def download_file(
    url: str,
    path: str,
    remote_size: int,
    remote_sha256: Optional[str] = None,
    remote_md5: Optional[str] = None,
    chunk_size: int = 128*1024,
) -> Tuple[bool, Optional[str], Optional[Tuple[str, str]]]:
    if check_file_integrity(path, remote_size, remote_sha256, remote_md5):
        return True, None, None
    
    logging.info(f"download file from {url} to {path}")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(path))
        os.close(fd)
        
        with requests.get(url, stream=True) as response:
            response.raise_for_status()

            total_size_in_bytes= int(response.headers.get('content-length', 0))
            progress_bar = tqdm(desc=f"downloading model", total=total_size_in_bytes, unit='iB', unit_scale=True)

            downloaded_size = 0
            sha256_hash = hashlib.sha256()
            md5_hash = hashlib.md5()

            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        sha256_hash.update(chunk)
                        md5_hash.update(chunk)
                        downloaded_size += len(chunk)
                        progress_bar.update(len(chunk))

            progress_bar.close()

            downloaded_sha256 = sha256_hash.hexdigest()
            downloaded_md5 = md5_hash.hexdigest()
            logging.info(f"downloaded sha256: {downloaded_sha256}")
            logging.info(f"downloaded md5: {downloaded_md5}")

            integrity_ok = check_file_integrity(temp_path, remote_size, downloaded_sha256, downloaded_md5)
            if integrity_ok:
                shutil.move(temp_path, path)
                return True, None, (downloaded_sha256, downloaded_md5)
            else:
                os.remove(temp_path)
                return False, "file integrity check failed", None
    except Exception as e:
        logging.error(f"{url} to {path} failed, {e}")
        return False, str(e), None

