import requests
import json
import logging
import os
import sys
from PIL import Image
from io import BytesIO
from pydrive2.auth import GoogleAuth # Uncomment for Google Drive
from pydrive2.drive import GoogleDrive # Uncomment for Google Drive

# --- Configuration ---
API_URL = 'https://unofficial-pinterest-api.p.rapidapi.com/pinterest/boards/relevance'
RAPIDAPI_HOST = 'unofficial-pinterest-api.p.rapidapi.com'
RAPIDAPI_KEY = '54accdd8bbmshaeeb82c1f1a89ccp1c58f1jsn313941a2a55c' # Your key
KEYWORD = 'hanuman art'
NUM_PINS = 5
MIN_SIZE = 400
OUTPUT_DIR = f'downloaded_images_{KEYWORD}'

# --- Logging Setup ---

# 1. Create and configure the StreamHandler separately
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
stream_handler.encoding = 'utf-8' # <-- THIS IS THE FIX

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler(f'downloader_{KEYWORD}.log', mode='w'),
                        stream_handler # Use the configured handler
                    ])
logger = logging.getLogger(__name__)

# --- Core Functions ---

def fetch_pinterest_data(keyword, num):
    """Fetches data from the Pinterest API."""
    logger.info(f"--- Starting API fetch for keyword: '{keyword}' (Pins: {num}) ---")
    headers = {
        'x-rapidapi-host': RAPIDAPI_HOST,
        'x-rapidapi-key': RAPIDAPI_KEY
    }
    params = {
        'keyword': keyword,
        'num': num
    }
    
    try:
        response = requests.get(API_URL, headers=headers, params=params, timeout=30)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        logger.info("Successfully fetched data from API.")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API Request Failed: {e}")
        return None

def find_image_urls(data):
    """
    Recursively traverses the API response object to find all URLs
    starting with 'https://i.pinimg.com'.
    """
    urls = set() # Use a set to automatically handle duplicates

    def traverse(obj):
        if isinstance(obj, dict):
            for value in obj.values():
                traverse(value)
        elif isinstance(obj, list):
            for item in obj:
                traverse(item)
        elif isinstance(obj, str) and obj.startswith('https://i.pinimg.com'):
            urls.add(obj)

    traverse(data)
    logger.info(f"Found {len(urls)} potential image URLs to process.")
    return list(urls)

def process_and_save_images(urls, output_dir, min_size):
    """Downloads, validates, and locally saves images."""
    os.makedirs(output_dir, exist_ok=True)
    
    saved_count = 0
    total_urls = len(urls)
    logger.info(f"Starting image download and validation process (Min size: {min_size}x{min_size}).")

    for i, url in enumerate(urls):
        try:
            # 1. Download Image
            logger.info(f"[{i+1}/{total_urls}] Downloading: {url}")
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            # 2. Open and Validate Size
            image_data = BytesIO(response.content)
            img = Image.open(image_data)
            width, height = img.size

            if width >= min_size and height >= min_size:
                # 3. Save Image Locally
                # Create a unique filename (e.g., from the URL's path)
                filename = os.path.join(output_dir, f"{url.split('/')[-1].split('?')[0]}")
                img.save(filename)
                saved_count += 1
                logger.info(f"Saved (Size: {width}x{height}) as: {filename}")
            else:
                logger.warning(f"Skipped (Too small: {width}x{height}). URL: {url}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading image from {url}: {e}")
        except IOError as e:
            logger.error(f"Error processing image data from {url}: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred for {url}: {e}")

    logger.info(f"--- Execution Complete ---")
    logger.info(f"Total URLs processed: {total_urls}")
    logger.info(f"Total images saved locally: {saved_count}")
    return saved_count

# Function to be added/integrated

def upload_to_drive(local_folder_path, drive_folder_name=f"Pinterest_{KEYWORD}_Images"):
    """Authenticates and uploads all saved images to Google Drive."""
    logger.info("--- Starting Google Drive Upload ---")
    
    try:
        # Authentication step (requires pydrive2 setup)
        gauth = GoogleAuth()
        gauth.LocalWebserverAuth()  # Opens browser for login/permission
        drive = GoogleDrive(gauth)

        # 1. Find or create the destination folder on Google Drive
        folder_list = drive.ListFile({'q': f"title='{drive_folder_name}' and trashed=false"}).GetList()
        if folder_list:
            drive_folder = folder_list[0]
            logger.info(f"Found existing Drive folder: {drive_folder_name}")
        else:
            drive_folder = drive.CreateFile({'title': drive_folder_name, 
                                             'mimeType': 'application/vnd.google-apps.folder'})
            drive_folder.Upload()
            logger.info(f"Created new Drive folder: {drive_folder_name}")

        # 2. Upload all files from the local directory
        uploaded_count = 0
        for filename in os.listdir(local_folder_path):
            local_path = os.path.join(local_folder_path, filename)
            
            # Create a GoogleDriveFile instance
            file_drive = drive.CreateFile({'title': filename,
                                            'parents': [{'id': drive_folder['id']}]})
            file_drive.SetContentFile(local_path)
            file_drive.Upload()
            uploaded_count += 1
            logger.info(f"Uploaded {filename} to Google Drive.")

        logger.info(f"Successfully uploaded {uploaded_count} images to Google Drive.")

    except Exception as e:
        logger.error(f"Google Drive Upload Failed: {e}. Check your authentication setup.")



def main():
    """Main execution flow."""
    data = fetch_pinterest_data(KEYWORD, NUM_PINS)

    if data:
        # 1. Extract URLs
        image_urls = find_image_urls(data)

        # 2. Download, Validate, and Save Locally
        saved_count = process_and_save_images(image_urls, OUTPUT_DIR, MIN_SIZE)
        
        # 3. Google Drive Step (See Section 3 below)
        upload_to_drive(OUTPUT_DIR) # Uncomment this if you implement the function

if __name__ == '__main__':
    main()