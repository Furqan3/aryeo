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
    """Create modern real estate post with full-bleed images and elegant text overlays"""
    width, height = 1080, 1080
    
    # ==========================================
    # STEP 1: PASTE ALL IMAGES FIRST
    # ==========================================
    
    canvas = Image.new("RGB", (width, height), "#000000")
    
    # Main hero image - full canvas with subtle zoom
    hero_aspect = hero_img.width / hero_img.height
    target_aspect = width / height
    
    if hero_aspect > target_aspect:
        new_width = int(hero_img.height * target_aspect)
        left = (hero_img.width - new_width) // 2
        hero_img = hero_img.crop((left, 0, left + new_width, hero_img.height))
    else:
        new_height = int(hero_img.width / target_aspect)
        top = (hero_img.height - new_height) // 2
        hero_img = hero_img.crop((0, top, hero_img.width, top + new_height))
    
    hero_img = hero_img.resize((width, height), Image.Resampling.LANCZOS)
    
    # Enhance the hero image
    hero_img = ImageEnhance.Contrast(hero_img).enhance(1.25)
    hero_img = ImageEnhance.Sharpness(hero_img).enhance(1.3)
    hero_img = ImageEnhance.Brightness(hero_img).enhance(1.05)
    
    # Paste hero image
    canvas.paste(hero_img, (0, 0))
    
    # Add detail images in a vertical strip on the right side
    if detail_imgs:
        strip_width = 280
        img_count = min(3, len(detail_imgs))
        img_height = height // img_count
        
        for idx, img in enumerate(detail_imgs[:img_count]):
            # Square crop
            size = min(img.width, img.height)
            left = (img.width - size) // 2
            top = (img.height - size) // 2
            img = img.crop((left, top, left + size, top + size))
            img_resized = img.resize((strip_width, img_height), Image.Resampling.LANCZOS)
            
            # Enhance detail images
            img_resized = ImageEnhance.Contrast(img_resized).enhance(1.2)
            img_resized = ImageEnhance.Sharpness(img_resized).enhance(1.3)
            
            canvas.paste(img_resized, (width - strip_width, idx * img_height))
    
    # ==========================================
    # STEP 2: ADD SEMI-TRANSPARENT OVERLAYS
    # ==========================================
    
    # Right side gradient overlay (for detail images strip)
    strip_overlay_width = 300
    right_overlay = Image.new("RGBA", (strip_overlay_width, height), (0, 0, 0, 0))
    right_draw = ImageDraw.Draw(right_overlay)
    for i in range(strip_overlay_width):
        alpha = int(180 * (1 - i / strip_overlay_width))
        right_draw.line([(i, 0), (i, height)], fill=(0, 0, 0, alpha))
    canvas.paste(right_overlay, (width - strip_overlay_width, 0), right_overlay)
    
    # Bottom overlay for main property info - Modern frosted glass effect
    bottom_overlay_height = 420
    bottom_y = height - bottom_overlay_height
    
    bottom_overlay = Image.new("RGBA", (width, bottom_overlay_height), (0, 0, 0, 0))
    bottom_draw = ImageDraw.Draw(bottom_overlay)
    
    # Gradient from transparent to dark
    for i in range(bottom_overlay_height):
        ratio = (i / bottom_overlay_height) ** 1.2
        alpha = int(240 * ratio)
        bottom_draw.line([(0, i), (width, i)], fill=(8, 12, 20, alpha))
    
    # Apply gaussian blur for frosted glass effect
    bottom_overlay = bottom_overlay.filter(ImageFilter.GaussianBlur(3))
    canvas.paste(bottom_overlay, (0, bottom_y), bottom_overlay)
    
    # Premium accent line at top of bottom overlay
    accent_line = Image.new("RGBA", (width, 4), (251, 191, 36, 230))
    canvas.paste(accent_line, (0, bottom_y), accent_line)
    
    # Price card overlay - Elevated panel
    price_card_width = width - 80
    price_card_height = 160
    price_card_x = 40
    price_card_y = bottom_y + 30
    
    price_card = Image.new("RGBA", (price_card_width, price_card_height), (0, 0, 0, 0))
    price_draw = ImageDraw.Draw(price_card)
    
    # Modern card with gradient
    for i in range(price_card_height):
        alpha = 200
        r, g, b = int(20 + 5 * (i / price_card_height)), int(25 + 5 * (i / price_card_height)), int(35 + 10 * (i / price_card_height))
        price_draw.line([(0, i), (price_card_width, i)], fill=(r, g, b, alpha))
    
    # Rounded corners effect
    price_card = price_card.filter(ImageFilter.GaussianBlur(1))
    
    # Gold border for luxury feel
    price_draw.rounded_rectangle(
        [(2, 2), (price_card_width - 2, price_card_height - 2)],
        radius=15,
        outline=(251, 191, 36, 255),
        width=3
    )
    
    canvas.paste(price_card, (price_card_x, price_card_y), price_card)
    
    # ==========================================
    # STEP 3: ADD ALL TEXT ON TOP
    # ==========================================
    
    draw = ImageDraw.Draw(canvas)
    
    # Load fonts
    try:
        font_price = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        font_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        font_specs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        font_type = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        font_address = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        font_brand = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
    except:
        font_price = ImageFont.load_default()
        font_label = ImageFont.load_default()
        font_specs = ImageFont.load_default()
        font_type = ImageFont.load_default()
        font_address = ImageFont.load_default()
        font_brand = ImageFont.load_default()
    
    # Price card content
    card_padding = 35
    card_y_offset = price_card_y + 25
    
    # Price label
    draw.text((price_card_x + card_padding, card_y_offset), 
              "LISTED AT", 
              fill="#A0AEC0", 
              font=font_label)
    card_y_offset += 28
    
    # Price - Main attraction
    price_text = property_info.price
    draw.text((price_card_x + card_padding, card_y_offset), 
              price_text, 
              fill="#FBD38D", 
              font=font_price,
              stroke_width=2,
              stroke_fill="#B7791F")
    card_y_offset += 85
    
    # Property type badge (if available)
    if property_info.property_type:
        type_text = property_info.property_type.upper()
        badge_x = price_card_x + card_padding
        badge_y = card_y_offset - 10
        
        # Modern badge background
        type_bbox = draw.textbbox((0, 0), type_text, font=font_type)
        badge_width = (type_bbox[2] - type_bbox[0]) + 24
        badge_height = (type_bbox[3] - type_bbox[1]) + 12
        
        badge_overlay = Image.new("RGBA", (badge_width, badge_height), (251, 191, 36, 255))
        canvas.paste(badge_overlay, (badge_x, badge_y), badge_overlay)
        
        draw.text((badge_x + 12, badge_y + 4), 
                  type_text, 
                  fill="#1A202C", 
                  font=font_type)
    
    # Property specs - Below price card
    specs_y = price_card_y + price_card_height + 25
    specs_text = f"{property_info.bedrooms} BD  •  {property_info.bathrooms} BA  •  {property_info.square_feet:,} SF"
    
    # Center the specs
    specs_bbox = draw.textbbox((0, 0), specs_text, font=font_specs)
    specs_width = specs_bbox[2] - specs_bbox[0]
    specs_x = (width - specs_width) // 2
    
    draw.text((specs_x, specs_y), 
              specs_text, 
              fill="#FFFFFF", 
              font=font_specs,
              stroke_width=1,
              stroke_fill="#000000")
    
    # Address section - Bottom
    address_y = specs_y + 50
    pin_emoji = "📍"
    
    full_address = f"{pin_emoji} {property_info.address}, {property_info.city}, {property_info.state} {property_info.zip_code}"
    
    # Center the address
    address_bbox = draw.textbbox((0, 0), full_address, font=font_address)
    address_width = address_bbox[2] - address_bbox[0]
    address_x = (width - address_width) // 2
    
    draw.text((address_x, address_y), 
              full_address, 
              fill="#E2E8F0", 
              font=font_address)
    
    # Brand/watermark - Bottom right with luxury styling
    brand_text = "✦ PREMIUM PROPERTIES ✦"
    brand_y = height - 35
    brand_bbox = draw.textbbox((0, 0), brand_text, font=font_brand)
    brand_width = brand_bbox[2] - brand_bbox[0]
    brand_x = (width - brand_width) // 2
    
    draw.text((brand_x, brand_y), 
              brand_text, 
              fill="#9CA3AF", 
              font=font_brand,
              stroke_width=1,
              stroke_fill="#000000")
    
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
    uvicorn.run(app, host="localhost", port=8000, log_level="info")