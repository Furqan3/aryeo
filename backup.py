from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl, field_validator
from typing import List, Optional, Dict
import uvicorn
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fastapi.middleware.cors import CORSMiddleware 
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
import re
import os
import requests
from urllib.parse import urlparse, urlunparse, ParseResult
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import io
import base64
from datetime import datetime, timedelta
import logging
from functools import lru_cache
import hashlib
import zipfile
import shutil

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Social Media Content Generator API",
    description="Generate professional real estate social media content",
    version="2.2.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Add your frontend URLs
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods including OPTIONS, POST, GET, etc.
    allow_headers=["*"],  # Allows all headers
)

# Configuration - CREDENTIALS FROM DOCUMENT 2
EMAIL = "john@moshinremedia.com"
PASSWORD = "Madmax1993"
BASE_URL = "https://moshin-real-estate-media.aryeo.com"
LOGIN_URL = "https://app.aryeo.com/login"

# Session management with TTL
SESSION_TTL = timedelta(hours=2)
sessions: Dict[str, dict] = {}

# Downloads dir
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# ============================================================================
# MODELS
# ============================================================================

class ListingURLRequest(BaseModel):
    listing_url: HttpUrl
    
    @field_validator('listing_url')
    def validate_aryeo_url(cls, v):
        url_str = str(v)
        if 'aryeo.com' not in url_str:
            raise ValueError('URL must be from aryeo.com domain')
        return v

class PropertyInfo(BaseModel):
    price: str
    bedrooms: int
    bathrooms: float
    square_feet: int
    address: str
    city: str
    state: str
    zip_code: str
    property_type: Optional[str] = "Single Family Home"
    year_built: Optional[int] = None
    lot_size: Optional[str] = None
    
    @field_validator('bedrooms')
    def validate_bedrooms(cls, v):
        if v < 0 or v > 50:
            raise ValueError('Bedrooms must be between 0 and 50')
        return v
    
    @field_validator('bathrooms')
    def validate_bathrooms(cls, v):
        if v < 0 or v > 50:
            raise ValueError('Bathrooms must be between 0 and 50')
        return v
    
    @field_validator('square_feet')
    def validate_sqft(cls, v):
        if v < 100 or v > 1000000:
            raise ValueError('Square feet must be between 100 and 1,000,000')
        return v

class ImageSelection(BaseModel):
    session_id: str
    hero_image_url: str
    detail_images: List[str]
    property_info: PropertyInfo
    
    @field_validator('detail_images')
    def validate_detail_images(cls, v):
        if len(v) != 3:
            raise ValueError('Exactly 3 detail images are required')
        return v

class ScrapedImages(BaseModel):
    session_id: str
    images: List[str]
    listing_url: str
    total_found: int

class GeneratedContent(BaseModel):
    session_id: str
    image_base64: str
    caption: str
    hashtags: List[str]

# ============================================================================
# SELENIUM HELPERS - MERGED WITH LOGIN FUNCTIONALITY
# ============================================================================

def init_driver(headless: bool = True) -> webdriver.Chrome:
    """Initialize Chrome WebDriver with optimized options"""
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument('--headless=new')
    
    # Performance optimizations
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-extensions')
    
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(30)
    driver.maximize_window()
    
    return driver

def login_to_aryeo(driver: webdriver.Chrome) -> bool:
    """Login to Aryeo using credentials from document 2"""
    try:
        logger.info("Navigating to login page...")
        driver.get(LOGIN_URL)
        time.sleep(2)
        
        # Enter email
        email_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "Emailaddress"))
        )
        email_input.clear()
        email_input.send_keys(EMAIL)
        logger.info(f"Email entered: {EMAIL}")
        
        # Click continue
        continue_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        continue_btn.click()
        time.sleep(2)
        
        # Enter password
        password_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "Password"))
        )
        password_input.clear()
        password_input.send_keys(PASSWORD)
        logger.info("Password entered")
        
        # Click login
        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_btn.click()
        time.sleep(3)
        
        logger.info(f"Login successful. Current URL: {driver.current_url}")
        return True
        
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        return False

def download_link(link: str) -> str:
    """Convert edit URL to download-center URL"""
    parsed = urlparse(link)
    path = parsed.path
    
    # Remove "/admin" prefix if present
    prefix = "/admin"
    if path.startswith(prefix):
        path = path[len(prefix):]
    
    # Ensure path starts with slash
    if not path.startswith("/"):
        path = "/" + path
    
    # Replace trailing "/edit" with "/download-center"
    if path.endswith("/edit"):
        path = path[:-len("/edit")] + "/download-center"
    else:
        path = path.rstrip("/") + "/download-center"
    
    # Rebuild URL
    new_parsed = ParseResult(
        scheme=parsed.scheme,
        netloc=parsed.netloc,
        path=path,
        params=parsed.params,
        query=parsed.query,
        fragment=parsed.fragment
    )
    return urlunparse(new_parsed)

def extract_id_from_url(url: str) -> str:
    """Extract listing ID from admin edit URL"""
    match = re.search(r'/listings/([0-9a-f-]+)', url)
    if match:
        return match.group(1)
    raise ValueError("Could not extract listing ID from URL")

def scrape_listing_images(driver: webdriver.Chrome, listing_url: str) -> List[str]:
    """Scrape image URLs from Aryeo listing page."""
    try:
        if not login_to_aryeo(driver):
            raise Exception("Login failed")

        logger.info(f"Navigating to listing: {listing_url}")
        listing_url=download_link(listing_url)
        driver.get(listing_url)
        time.sleep(5)
        
        # Scroll to load all images
        logger.info("Scrolling to load images...")
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        
        image_urls = []
        seen_urls = set()
        
        # Method 1: Find img elements
        images = driver.find_elements(By.TAG_NAME, "img")
        logger.info(f"Found {len(images)} img elements")
        
        for img in images:
            try:
                src = (img.get_attribute('src') or 
                       img.get_attribute('data-src') or
                       img.get_attribute('data-lazy-src'))
                
                if src and 'cdn.aryeo.com' in src and '/resized/' in src and src not in seen_urls:
                    image_urls.append(src)
                    seen_urls.add(src)
            except:
                continue
        
        # Method 2: Check for background images in style attributes
        all_elements = driver.find_elements(By.XPATH, "//*[@style]")
        logger.info(f"Checking {len(all_elements)} elements with style attributes")
        
        for elem in all_elements:
            try:
                style = elem.get_attribute('style')
                if style and 'cdn.aryeo.com' in style and '/resized/' in style:
                    # Extract URL from background-image: url(...)
                    urls = re.findall(r'url\(["\'][](https://cdn\.aryeo\.com[^"\')\s]+)["\']?\)', style)
                    for url in urls:
                        if '/resized/' in url and url not in seen_urls:
                            image_urls.append(url)
                            seen_urls.add(url)
            except:
                continue
        
        # Method 3: Execute JavaScript to find all CDN URLs in the page
        logger.info("Searching for CDN URLs in page content...")
        js_script = """
        const urls = new Set();
        
        // Check all img elements
        document.querySelectorAll('img').forEach(img => {
            const src = img.src || img.dataset.src || img.dataset.lazySrc;
            if (src && src.includes('cdn.aryeo.com') && src.includes('/resized/')) {
                urls.add(src);
            }
        });
        
        // Check all elements with background images
        document.querySelectorAll('*').forEach(el => {
            const style = window.getComputedStyle(el).backgroundImage;
            if (style && style.includes('cdn.aryeo.com') && style.includes('/resized/')) {
                const match = style.match(/url\\(["\']?(.*?)["\']?\\)/);
                if (match) urls.add(match[1]);
            }
        });
        
        return Array.from(urls);
        """
        
        js_urls = driver.execute_script(js_script)
        for url in js_urls:
            if url not in seen_urls:
                image_urls.append(url)
                seen_urls.add(url)
        
        logger.info(f"Total CDN images found: {len(image_urls)}")
        
        # Debug: if no images found, save screenshot
        if len(image_urls) == 0:
            logger.warning("No images found! Saving debug screenshot...")
            driver.save_screenshot("debug_no_images.png")
            logger.debug(f"Page title: {driver.title}")
            
            # Log sample of all img src found
            all_imgs = driver.find_elements(By.TAG_NAME, "img")
            for i, img in enumerate(all_imgs[:3]):
                logger.debug(f"Sample img {i}: {img.get_attribute('src')}")
        
        return image_urls

    except Exception as e:
        logger.error(f"Scraping error: {str(e)}")
        raise

def get_original_url(resized_url: str) -> str:
    inner_start = resized_url.find('https://cdn.aryeo.com')
    if inner_start != -1:
        inner_url = resized_url[inner_start:]
    else:
        inner_url = resized_url

    # Optionally remove /resized/large/ and large- for full original
    # But according to user, /resized/large/large- is high-res
    # So return inner_url as is
    return inner_url

def sort_images_by_quality_local(image_paths: List[str]) -> List[str]:
    """Sort images by quality based on filename and dimensions"""
    scored_images = []
    
    for path in image_paths:
        score = 0
        filename_lower = os.path.basename(path).lower()
        
        if any(x in filename_lower for x in ['large', '_lg', 'full', 'original', '_orig', 'hd', '2k', '4k']):
            score += 20
        
        if any(x in filename_lower for x in ['@2x', '@3x', 'retina']):
            score += 15
        
        if any(x in filename_lower for x in ['thumb', '_sm', 'small', '_xs', 'thumbnail']):
            score -= 5
        
        try:
            with Image.open(path) as img:
                width, height = img.size
                if width >= 1920 or height >= 1080:
                    score += 25
                elif width >= 1000 or height >= 1000:
                    score += 15
                elif width >= 800 or height >= 800:
                    score += 10
                elif width < 300 and height < 300:
                    score -= 3
        except:
            pass
        
        if filename_lower.endswith(('.jpg', '.jpeg')):
            score += 5
        
        scored_images.append((score, path))
    
    scored_images.sort(reverse=True, key=lambda x: x[0])
    
    return [path for score, path in scored_images]

# ============================================================================
# IMAGE PROCESSING (from document 1)
# ============================================================================

@lru_cache(maxsize=100)
def download_image(url_or_path: str, cookies_hash: str = None) -> Optional[Image.Image]:
    """Load image from URL or local path"""
    try:
        if url_or_path.startswith('http'):
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url_or_path, headers=headers, timeout=30)
            response.raise_for_status()
            content = response.content
        else:
            with open(url_or_path, 'rb') as f:
                content = f.read()
        
        img = Image.open(io.BytesIO(content))
        
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        
        return img
    except Exception as e:
        logger.error(f"Image load error for {url_or_path}: {str(e)}")
        return None

def create_social_media_post(hero_img: Image.Image, detail_imgs: list, property_info) -> Image.Image:
    """
    Enhanced real estate social media post with improved typography.
    
    Typography improvements:
    - Better font hierarchy with distinct sizes
    - Improved spacing and letter-spacing for readability
    - Better contrast and visual balance
    - Optimized text positioning and alignment
    - Enhanced readability with proper line heights
    """
    width, height = 1080, 1080
    
    # ==========================================
    # COLOR PALETTE
    # ==========================================
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    DARK_GRAY = (20, 20, 20)  # Softer than pure black
    
    # ==========================================
    # LAYOUT DIMENSIONS
    # ==========================================
    HERO_HEIGHT = 540
    INFO_BAR_HEIGHT = 90  # Slightly increased for better breathing room
    DETAIL_HEIGHT = 270
    BOTTOM_HEIGHT = height - HERO_HEIGHT - INFO_BAR_HEIGHT - DETAIL_HEIGHT
    
    # ==========================================
    # LOAD FONTS WITH BETTER HIERARCHY
    # ==========================================
    try:
        # Info bar fonts - improved sizes
        font_bold_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        font_bold_value = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        font_regular_specs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        font_regular_specs_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        
        # Bottom section fonts - better hierarchy
        font_title_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 70)
        font_address = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except:
        font_bold_label = font_bold_value = font_regular_specs = font_title_large = font_address = ImageFont.load_default()
        font_regular_specs_small = ImageFont.load_default()
    
    # Create canvas
    canvas = Image.new("RGB", (width, height), WHITE)
    draw = ImageDraw.Draw(canvas)
    
    # ==========================================
    # HELPER FUNCTIONS
    # ==========================================
    def wrap_phrases(draw, phrases, font, max_width, separator=" | "):
        lines = []
        current = []
        for phrase in phrases:
            test = current + [phrase]
            test_text = separator.join(test)
            bbox = draw.textbbox((0, 0), test_text, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(separator.join(current))
                current = [phrase]
        if current:
            lines.append(separator.join(current))
        return lines
    
    def wrap_text(draw, text, font, max_width):
        words = text.split()
        lines = []
        current = ""
        for word in words:
            test = current + " " + word if current else word
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines
    
    # ==========================================
    # HERO IMAGE
    # ==========================================
    hero_aspect = hero_img.width / hero_img.height
    target_aspect = width / HERO_HEIGHT
    if hero_aspect > target_aspect:
        new_width = int(hero_img.height * target_aspect)
        left = (hero_img.width - new_width) // 2
        hero_img = hero_img.crop((left, 0, left + new_width, hero_img.height))
    else:
        new_height = int(hero_img.width / target_aspect)
        top = (hero_img.height - new_height) // 2
        hero_img = hero_img.crop((0, top, hero_img.width, top + new_height))
    
    hero_img = hero_img.resize((width, HERO_HEIGHT), Image.Resampling.LANCZOS)
    hero_img = ImageEnhance.Contrast(hero_img).enhance(1.1)
    hero_img = ImageEnhance.Sharpness(hero_img).enhance(1.1)
    canvas.paste(hero_img, (0, 0))
    
    # ==========================================
    # INFO BAR (IMPROVED TYPOGRAPHY)
    # ==========================================
    info_y = HERO_HEIGHT
    draw.rectangle([(0, info_y), (width, info_y + INFO_BAR_HEIGHT)], fill=DARK_GRAY)
    
    section_width = width // 3
    margin = 25
    
    # Left: PRICE (improved hierarchy)
    price_label = "PRICE:"
    price_value = "$"+property_info.price
    
    # Calculate total width for centering
    label_bbox = draw.textbbox((0, 0), price_label, font=font_bold_label)
    value_bbox = draw.textbbox((0, 0), price_value, font=font_bold_value)
    spacing = 8
    total_width = (label_bbox[2] - label_bbox[0]) + spacing + (value_bbox[2] - value_bbox[0])
    
    start_x = (section_width - total_width) // 2
    label_y = info_y + 25
    value_y = info_y + 45
    
    draw.text((start_x, label_y), price_label, fill=WHITE, font=font_bold_label)
    draw.text((start_x, value_y), price_value, fill=WHITE, font=font_bold_value)
    
    # Middle: SPECS (cleaner separator, better spacing)
    baths_str = str(int(property_info.bathrooms)) if property_info.bathrooms == int(property_info.bathrooms) else str(property_info.bathrooms)
    specs_phrases = [
        f"{property_info.bedrooms} BEDS",
        f"{baths_str} BATHS",
        f"{property_info.square_feet:,} SQ FT"
    ]
    if property_info.year_built:
        specs_phrases.append(f"BUILT {property_info.year_built}")

    
    # Use cleaner separator
    specs_lines = wrap_phrases(draw, specs_phrases, font_regular_specs, section_width - margin * 2, " · ")
    
    # Adjust font if needed
    if len(specs_lines) > 2:
        specs_lines = wrap_phrases(draw, specs_phrases, font_regular_specs_small, section_width - margin * 2, " · ")
        font_used = font_regular_specs_small
    else:
        font_used = font_regular_specs
    
    line_height = 28
    total_text_height = line_height * len(specs_lines)
    start_y = info_y + (INFO_BAR_HEIGHT - total_text_height) // 2
    
    for idx, line in enumerate(specs_lines):
        line_bbox = draw.textbbox((0, 0), line, font=font_used)
        line_x = section_width + (section_width - (line_bbox[2] - line_bbox[0])) // 2
        draw.text((line_x, start_y + idx * line_height), line, fill=WHITE, font=font_used)
    
    # Right: PROPERTY TYPE
    type_text = property_info.property_type.upper() if property_info.property_type else "MODERN ESTATE"
    type_bbox = draw.textbbox((0, 0), type_text, font=font_bold_value)
    type_x = (section_width * 2) + (section_width - (type_bbox[2] - type_bbox[0])) // 2
    type_y = info_y + (INFO_BAR_HEIGHT - (type_bbox[3] - type_bbox[1])) // 2
    draw.text((type_x, type_y), type_text, fill=WHITE, font=font_bold_value)
    
    # ==========================================
    # DETAIL IMAGES
    # ==========================================
    detail_y = info_y + INFO_BAR_HEIGHT
    detail_width = width // 3
    if len(detail_imgs) >= 3:
        for idx, img in enumerate(detail_imgs[:3]):
            target_aspect = detail_width / DETAIL_HEIGHT
            img_aspect = img.width / img.height
            if img_aspect > target_aspect:
                new_width = int(img.height * target_aspect)
                left = (img.width - new_width) // 2
                img = img.crop((left, 0, left + new_width, img.height))
            else:
                new_height = int(img.width / target_aspect)
                top = (img.height - new_height) // 2
                img = img.crop((0, top, img.width, top + new_height))
            
            img = img.resize((detail_width, DETAIL_HEIGHT), Image.Resampling.LANCZOS)
            img = ImageEnhance.Contrast(img).enhance(1.1)
            canvas.paste(img, (idx * detail_width, detail_y))
    
    # ==========================================
    # BOTTOM SECTION (ENHANCED TYPOGRAPHY)
    # ==========================================
    bottom_y = detail_y + DETAIL_HEIGHT
    draw.rectangle([(0, bottom_y), (width, height)], fill=DARK_GRAY)
    
    # Title with better spacing
    title_text = type_text
    title_x = 50
    title_y = bottom_y + 30
    draw.text((title_x, title_y), title_text, fill=WHITE, font=font_title_large)
    
    # Address with improved line height
    address_text = f"{property_info.address}, {property_info.city}, {property_info.state}"
    if property_info.zip_code:
        address_text += f" {property_info.zip_code}"
    
    address_lines = wrap_text(draw, address_text, font_address, width - 100)
    
    title_bbox = draw.textbbox((0, 0), title_text, font=font_title_large)
    address_y = title_y + (title_bbox[3] - title_bbox[1]) + 15
    line_height = 36  # Better line spacing for readability
    
    for line in address_lines:
        draw.text((title_x, address_y), line, fill=WHITE, font=font_address)
        address_y += line_height
    
    return canvas

def image_to_base64(img: Image.Image) -> str:
    """Convert PIL Image to base64"""
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=95, optimize=True)
    return base64.b64encode(buffered.getvalue()).decode()

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

def clean_expired_sessions():
    """Remove expired sessions"""
    now = datetime.now()
    expired = [
        sid for sid, data in sessions.items()
        if now - datetime.fromisoformat(data['timestamp']) > SESSION_TTL
    ]
    for sid in expired:
        del sessions[sid]
        logger.info(f"Cleaned expired session: {sid}")

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.options("/scrape")
async def options_scrape():
    return JSONResponse(
        content={"message": "OK"},
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )

@app.get("/health")
def health_check():
    clean_expired_sessions()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(sessions)
    }

@app.post("/scrape", response_model=ScrapedImages)
async def scrape_listing(request: ListingURLRequest):
    """Scrape images from Aryeo listing with authentication"""
    driver = None
    try:
        session_id = f"session_{int(time.time())}_{hash(str(request.listing_url)) % 10000}"
        
        logger.info(f"Starting scrape for session: {session_id}")
        driver = init_driver()  
        
        # Scrape with login
        remote_urls = scrape_listing_images(driver, str(request.listing_url))
        
        if not remote_urls:
            raise HTTPException(status_code=404, detail="No images found in listing")
        
        # Convert to original high-res URLs
        original_urls = [get_original_url(url) for url in remote_urls]
        
        # No download here for speed
        
        # Store session
        sessions[session_id] = {
            'images': original_urls,
            'listing_url': str(request.listing_url),
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Session {session_id} created with {len(original_urls)} images")
        
        return ScrapedImages(
            session_id=session_id,
            images=original_urls[:50],
            listing_url=str(request.listing_url),
            total_found=len(original_urls)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

@app.post("/generate", response_model=GeneratedContent)
async def generate_content(request: ImageSelection):
    """Generate social media content from selected images"""
    try:
        if request.session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found or expired")
        
        session_data = sessions[request.session_id]
        
        logger.info(f"Loading hero image: {request.hero_image_url}")
        hero_img = download_image(request.hero_image_url)
        if not hero_img:
            raise HTTPException(status_code=400, detail="Failed to load hero image")
        
        detail_imgs = []
        for idx, path in enumerate(request.detail_images):
            logger.info(f"Loading detail image {idx + 1}: {path}")
            img = download_image(path)
            if not img:
                raise HTTPException(status_code=400, detail=f"Failed to load detail image {idx + 1}")
            detail_imgs.append(img)
        
        logger.info("Creating composite image")
        final_image = create_social_media_post(hero_img, detail_imgs, request.property_info)
        
        image_base64 = image_to_base64(final_image)
        caption = generate_caption(request.property_info)
        hashtags = generate_hashtags(request.property_info)
        
        logger.info(f"Content generated successfully for session {request.session_id}")
        
        return GeneratedContent(
            session_id=request.session_id,
            image_base64=image_base64,
            caption=caption,
            hashtags=hashtags
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Content generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Content generation failed: {str(e)}")

def generate_caption(property_info: PropertyInfo) -> str:
    """Generate engaging social media caption"""
    price_num = int(re.sub(r'[^\d]', '', property_info.price))
    if price_num >= 1000000:
        price_display = f"${price_num / 1000000:.2f}M"
    else:
        price_display = property_info.price
    
    features = []
    if property_info.year_built:
        age = datetime.now().year - property_info.year_built
        if age <= 5:
            features.append("newly built")
        elif age <= 15:
            features.append("modern construction")
    
    if property_info.square_feet >= 3000:
        features.append("spacious layout")
    
    if property_info.bedrooms >= 4:
        features.append("perfect for families")
    
    if property_info.lot_size:
        features.append(f"{property_info.lot_size} lot")
    
    property_type = property_info.property_type or "home"
    
    caption_parts = [
        f"🏡 NEW LISTING ALERT! 🏡\n",
        f"\n{price_display}",
        f"\n{property_info.bedrooms} Bedrooms | {property_info.bathrooms} Bathrooms | {property_info.square_feet:,} sqft",
        f"\n\n📍 {property_info.address}",
        f"\n{property_info.city}, {property_info.state} {property_info.zip_code}",
    ]
    
    if features:
        caption_parts.append(f"\n\n✨ Features: {', '.join(features)}")
    
    caption_parts.extend([
        f"\n\nThis stunning {property_type.lower()} offers everything you've been looking for! ",
        "Don't miss this incredible opportunity to make it yours.",
        "\n\n💬 DM for more details or to schedule your private showing!",
        "\n🔗 Link in bio for virtual tour",
        "\n\n👉 Tag someone who needs to see this!"
    ])
    
    return "".join(caption_parts)

def generate_hashtags(property_info: PropertyInfo) -> List[str]:
    """Generate relevant hashtags"""
    hashtags = [
        "#realestate", "#realtor", "#homesforsale", "#househunting",
        "#dreamhome", "#realestateagent", "#newlisting", "#property",
        "#realty", "#homesweethome"
    ]
    
    city_tag = f"#{property_info.city.lower().replace(' ', '').replace('-', '')}"
    state_tag = f"#{property_info.state.lower()}realestate"
    hashtags.extend([city_tag, state_tag])
    
    property_type = property_info.property_type.lower().replace(' ', '')
    hashtags.append(f"#{property_type}")
    
    price_num = int(re.sub(r'[^\d]', '', property_info.price))
    if price_num >= 1000000:
        hashtags.extend(["#luxuryhomes", "#luxuryrealestate", "#luxuryliving"])
    elif price_num >= 500000:
        hashtags.extend(["#premiumhomes", "#upscalehomes"])
    else:
        hashtags.extend(["#affordablehomes", "#firsttimehomebuyer"])
    
    if property_info.square_feet >= 3000:
        hashtags.append("#spacioushome")
    
    if property_info.bedrooms >= 4:
        hashtags.append("#familyhome")
    
    return list(set(hashtags[:30]))

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session"""
    if session_id in sessions:
        del sessions[session_id]
        logger.info(f"Deleted session: {session_id}")
        return {"message": "Session deleted successfully"}
    raise HTTPException(status_code=404, detail="Session not found")

@app.get("/sessions")
async def list_sessions():
    """List all active sessions"""
    clean_expired_sessions()
    
    return {
        "sessions": [
            {
                "session_id": sid,
                "image_count": len(data['images']),
                "listing_url": data['listing_url'],
                "timestamp": data['timestamp'],
                "age_minutes": (datetime.now() - datetime.fromisoformat(data['timestamp'])).total_seconds() / 60
            }
            for sid, data in sessions.items()
        ],
        "total": len(sessions)
    }

@app.on_event("startup")
async def startup_event():
    logger.info("Social Media Content Generator API v2.2 started")
    logger.info(f"Session TTL: {SESSION_TTL}")
    logger.info("Login credentials loaded")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down API")
    sessions.clear()

app.mount("/", StaticFiles(directory="frontend/build", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
