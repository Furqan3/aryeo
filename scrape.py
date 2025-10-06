import requests
from bs4 import BeautifulSoup
import json
import time
from urllib.parse import urljoin, urlparse
import re

class AryeoScraper:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://app.aryeo.com"
        self.logged_in = False
        
        # Set headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        })
    
    def get_fresh_csrf_token(self):
        """
        Get a fresh CSRF token by visiting the login page
        """
        try:
            # Clear any existing cookies first
            self.session.cookies.clear()
            
            print("Getting fresh CSRF token...")
            login_url = f"{self.base_url}/login"
            
            # First request to get the login page
            response = self.session.get(login_url)
            response.raise_for_status()
            
            if response.encoding is None:
                response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for CSRF token in multiple places
            csrf_token = None
            
            # Method 1: Look for _token input field
            token_input = soup.find('input', {'name': '_token'})
            if token_input:
                csrf_token = token_input.get('value')
                print(f"Found CSRF token in input field: {csrf_token[:20]}...")
            
            # Method 2: Look for csrf-token meta tag
            if not csrf_token:
                csrf_meta = soup.find('meta', {'name': 'csrf-token'})
                if csrf_meta:
                    csrf_token = csrf_meta.get('content')
                    print(f"Found CSRF token in meta tag: {csrf_token[:20]}...")
            
            # Method 3: Look in JavaScript/window object
            if not csrf_token:
                script_tags = soup.find_all('script')
                for script in script_tags:
                    if script.string:
                        # Look for Laravel.csrfToken or similar
                        csrf_match = re.search(r'csrf["\']?\s*[:=]\s*["\']([^"\']+)["\']', script.string, re.IGNORECASE)
                        if csrf_match:
                            csrf_token = csrf_match.group(1)
                            print(f"Found CSRF token in script: {csrf_token[:20]}...")
                            break
            
            # Method 4: Look for XSRF-TOKEN cookie
            if not csrf_token:
                xsrf_cookie = self.session.cookies.get('XSRF-TOKEN')
                if xsrf_cookie:
                    # XSRF tokens are usually URL encoded
                    import urllib.parse
                    csrf_token = urllib.parse.unquote(xsrf_cookie)
                    print(f"Found CSRF token in XSRF-TOKEN cookie: {csrf_token[:20]}...")
            
            return csrf_token
            
        except Exception as e:
            print(f"Error getting CSRF token: {e}")
            return None
    
    def login(self, username, password):
        """
        Login to Aryeo platform with two-step process
        """
        try:
            # Step 1: Email check via API
            print("Step 1: Checking email with Aryeo API...")
            
            email_check_url = "https://api.aryeo.com/v1/auth/email-check"
            email_data = {"email": username}
            
            # Get fresh CSRF token first
            csrf_token = self.get_fresh_csrf_token()
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': self.base_url,
                'Referer': f"{self.base_url}/login"
            }
            
            if csrf_token:
                headers['X-CSRF-TOKEN'] = csrf_token
            
            email_response = self.session.post(
                email_check_url, 
                json=email_data,
                headers=headers
            )
            
            print(f"Email check response: {email_response.status_code}")
            
            if email_response.status_code == 200:
                email_result = email_response.json()
                print(f"Email check result: {email_result}")
                
                if email_result.get('status') == 'ACTIVE' and email_result.get('has_admin_account'):
                    print("Email verified successfully!")
                else:
                    print("Email check failed - account may not be active or admin")
                    return False
            else:
                print("Email check API call failed")
                return False
            
            # Step 2: Actual login
            print("Step 2: Performing actual login...")
            
            login_url = f"{self.base_url}/login"
            login_data = {
                'email': username,
                'password': password,
                '_token': csrf_token,
            }
            
            login_headers = {
                'Referer': login_url,
                'Origin': self.base_url,
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest',
            }
            
            if csrf_token:
                login_headers['X-CSRF-TOKEN'] = csrf_token
            
            login_response = self.session.post(
                login_url,
                data=login_data,
                headers=login_headers,
                allow_redirects=True
            )
            
            print(f"Login response status: {login_response.status_code}")
            print(f"Final URL after login: {login_response.url}")
            
            # Check for successful login
            if login_response.status_code == 200:
                response_text = login_response.text.lower()
                
                # Check if we're redirected away from login page
                if ('login' not in login_response.url and 
                    any(indicator in response_text for indicator in [
                        'dashboard', 'logout', 'profile', 'settings', 'listings'
                    ])):
                    self.logged_in = True
                    print("Two-step login successful!")
                    return True
                
                # Check for specific error messages
                if 'invalid' in response_text or 'incorrect' in response_text:
                    print("Invalid credentials provided.")
                elif 'expired' in response_text:
                    print("Session expired.")
            
            print("Login failed after email verification")
            return False
            
        except requests.RequestException as e:
            print(f"Error during two-step login: {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"Error parsing email check response: {e}")
            return False
            
            
            
        except requests.RequestException as e:
            print(f"Error during login: {e}")
            return False
    
    def debug_login_form(self):
        """
        Debug method to inspect the login form structure
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.chrome.options import Options
            
            print("=== DEBUGGING LOGIN FORM ===")
            
            chrome_options = Options()
            # Don't use headless for debugging
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            driver = webdriver.Chrome(options=chrome_options)
            
            try:
                driver.get(f"{self.base_url}/login")
                input("Press Enter after the page loads to continue debugging...")
                
                print("\n=== ALL INPUT ELEMENTS ===")
                inputs = driver.find_elements(By.TAG_NAME, "input")
                for i, inp in enumerate(inputs):
                    print(f"Input {i}:")
                    print(f"  name: {inp.get_attribute('name')}")
                    print(f"  type: {inp.get_attribute('type')}")
                    print(f"  id: {inp.get_attribute('id')}")
                    print(f"  placeholder: {inp.get_attribute('placeholder')}")
                    print(f"  class: {inp.get_attribute('class')}")
                    print(f"  visible: {inp.is_displayed()}")
                    print()
                
                print("\n=== ALL BUTTON ELEMENTS ===")
                buttons = driver.find_elements(By.TAG_NAME, "button")
                for i, btn in enumerate(buttons):
                    print(f"Button {i}:")
                    print(f"  text: {btn.text}")
                    print(f"  type: {btn.get_attribute('type')}")
                    print(f"  class: {btn.get_attribute('class')}")
                    print(f"  visible: {btn.is_displayed()}")
                    print()
                
                print("\n=== FORM ELEMENTS ===")
                forms = driver.find_elements(By.TAG_NAME, "form")
                for i, form in enumerate(forms):
                    print(f"Form {i}:")
                    print(f"  action: {form.get_attribute('action')}")
                    print(f"  method: {form.get_attribute('method')}")
                    print(f"  class: {form.get_attribute('class')}")
                    print()
                
                print("\n=== PAGE SOURCE SAMPLE ===")
                print(driver.page_source[:2000])
                
                input("Press Enter to close browser...")
                
            finally:
                driver.quit()
                
        except Exception as e:
            print(f"Debug error: {e}")

    def try_selenium_login(self, username, password):
        """
        Alternative login method using Selenium for JavaScript-heavy sites
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.keys import Keys
            import time as sleep_time
            
            print("Attempting login with Selenium...")
            
            # Setup Chrome options
            chrome_options = Options()
            # chrome_options.add_argument("--headless")  # Comment out to see browser for debugging
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            driver = webdriver.Chrome(options=chrome_options)
            
            try:
                print("Navigating to login page...")
                driver.get(f"{self.base_url}/login")
                
                # Wait for page to load completely
                sleep_time.sleep(3)
                
                print("Looking for login form elements...")
                
                # Try multiple selectors for email field
                email_field = None
                email_selectors = [
                    (By.NAME, "email"),
                    (By.ID, "email"),
                    (By.CSS_SELECTOR, "input[type='email']"),
                    (By.CSS_SELECTOR, "input[placeholder*='email' i]"),
                    (By.CSS_SELECTOR, "input[placeholder*='Email' i]"),
                    (By.XPATH, "//input[contains(@placeholder, 'email') or contains(@placeholder, 'Email')]")
                ]
                
                for selector_type, selector in email_selectors:
                    try:
                        email_field = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((selector_type, selector))
                        )
                        print(f"Found email field with selector: {selector}")
                        break
                    except:
                        continue
                
                if not email_field:
                    print("Could not find email field")
                    print("Available form elements:")
                    inputs = driver.find_elements(By.TAG_NAME, "input")
                    for i, inp in enumerate(inputs):
                        print(f"Input {i}: name='{inp.get_attribute('name')}', type='{inp.get_attribute('type')}', placeholder='{inp.get_attribute('placeholder')}'")
                    return False
                
                # Clear and fill email field
                email_field.clear()
                email_field.send_keys(username)
                print("Email field filled")
                
                # Try multiple selectors for password field
                password_field = None
                password_selectors = [
                    (By.NAME, "password"),
                    (By.ID, "password"),
                    (By.CSS_SELECTOR, "input[type='password']"),
                    (By.CSS_SELECTOR, "input[placeholder*='password' i]"),
                    (By.CSS_SELECTOR, "input[placeholder*='Password' i]"),
                    (By.XPATH, "//input[contains(@placeholder, 'password') or contains(@placeholder, 'Password') or @type='password']"),
                    (By.XPATH, "//input[@type='password']"),
                    (By.CSS_SELECTOR, "[data-testid*='password']"),
                    (By.CSS_SELECTOR, "[name*='pass']"),
                    (By.CSS_SELECTOR, "[id*='pass']")
                ]
                
                for selector_type, selector in password_selectors:
                    try:
                        password_field = driver.find_element(selector_type, selector)
                        print(f"Found password field with selector: {selector}")
                        break
                    except:
                        continue
                
                if not password_field:
                    print("Could not find password field with standard selectors")
                    print("Available form elements after email fill:")
                    inputs = driver.find_elements(By.TAG_NAME, "input")
                    for i, inp in enumerate(inputs):
                        name = inp.get_attribute('name')
                        input_type = inp.get_attribute('type')
                        placeholder = inp.get_attribute('placeholder')
                        visible = inp.is_displayed()
                        print(f"Input {i}: name='{name}', type='{input_type}', placeholder='{placeholder}', visible={visible}")
                    
                    # Try to find any input that might be a password field
                    print("Looking for any password-like input...")
                    all_inputs = driver.find_elements(By.TAG_NAME, "input")
                    for inp in all_inputs:
                        if inp.is_displayed():  # Only visible inputs
                            input_type = inp.get_attribute('type')
                            name = inp.get_attribute('name')
                            placeholder = inp.get_attribute('placeholder') or ""
                            
                            # Check if it could be a password field
                            password_indicators = ['password', 'pass', 'pwd']
                            if (input_type == 'password' or 
                                any(indicator in name.lower() for indicator in password_indicators) or
                                any(indicator in placeholder.lower() for indicator in password_indicators)):
                                password_field = inp
                                print(f"Found potential password field: name='{name}', type='{input_type}'")
                                break
                    
                    # If still not found, try clicking or interacting to reveal fields
                    if not password_field:
                        print("Trying to interact with page to reveal password field...")
                        # Sometimes password fields appear after clicking email or pressing tab
                        try:
                            email_field.click()
                            sleep_time.sleep(1)
                            
                            # Try pressing Tab to move to next field
                            from selenium.webdriver.common.keys import Keys
                            email_field.send_keys(Keys.TAB)
                            sleep_time.sleep(1)
                            
                            # Look again
                            password_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
                            if password_inputs:
                                password_field = password_inputs[0]
                                print("Found password field after interaction")
                        except:
                            pass
                
                if not password_field:
                    print("Still could not find password field. The form might be unusual.")
                    print("Full page source (first 3000 chars):")
                    print(driver.page_source[:3000])
                    return False
                
                # Clear and fill password field
                password_field.clear()
                password_field.send_keys(password)
                print("Password field filled")
                
                # Try multiple ways to submit the form
                submitted = False
                
                # Method 1: Find submit button
                submit_selectors = [
                    (By.CSS_SELECTOR, "button[type='submit']"),
                    (By.CSS_SELECTOR, "input[type='submit']"),
                    (By.CSS_SELECTOR, "button:contains('Login')"),
                    (By.CSS_SELECTOR, "button:contains('Sign in')"),
                    (By.XPATH, "//button[contains(text(), 'Login') or contains(text(), 'Sign in') or contains(text(), 'Log in')]"),
                    (By.CSS_SELECTOR, "form button"),
                ]
                
                for selector_type, selector in submit_selectors:
                    try:
                        submit_button = driver.find_element(selector_type, selector)
                        print(f"Found submit button: {submit_button.text}")
                        driver.execute_script("arguments[0].click();", submit_button)
                        submitted = True
                        break
                    except:
                        continue
                
                # Method 2: Press Enter in password field
                if not submitted:
                    print("Trying to submit by pressing Enter...")
                    password_field.send_keys(Keys.RETURN)
                    submitted = True
                
                if not submitted:
                    print("Could not submit form")
                    return False
                
                print("Form submitted, waiting for response...")
                sleep_time.sleep(3)
                
                # Wait for redirect or success (extended timeout)
                try:
                    WebDriverWait(driver, 15).until(
                        lambda d: 'login' not in d.current_url.lower() or 
                                 'dashboard' in d.current_url.lower() or
                                 'home' in d.current_url.lower()
                    )
                except:
                    pass  # Continue to check manually
                
                print(f"Current URL after login attempt: {driver.current_url}")
                
                # Check if login was successful
                current_url = driver.current_url.lower()
                page_source = driver.page_source.lower()
                
                success_indicators = [
                    'login' not in current_url,
                    'dashboard' in current_url or 'dashboard' in page_source,
                    'logout' in page_source,
                    'profile' in page_source,
                    'settings' in page_source
                ]
                
                if any(success_indicators):
                    print("Selenium login successful!")
                    
                    # Transfer cookies to requests session
                    selenium_cookies = driver.get_cookies()
                    print(f"Transferring {len(selenium_cookies)} cookies...")
                    
                    for cookie in selenium_cookies:
                        self.session.cookies.set(
                            cookie['name'], 
                            cookie['value'], 
                            domain=cookie.get('domain', ''),
                            path=cookie.get('path', '/'),
                            secure=cookie.get('secure', False)
                        )
                    
                    self.logged_in = True
                    return True
                else:
                    print("Login appears to have failed")
                    print("Checking for error messages...")
                    
                    # Look for error messages
                    error_selectors = [
                        ".alert-danger", ".error", ".invalid-feedback", 
                        "[class*='error']", "[class*='invalid']"
                    ]
                    
                    for selector in error_selectors:
                        try:
                            error_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            for error in error_elements:
                                if error.text.strip():
                                    print(f"Error message found: {error.text}")
                        except:
                            pass
                
                return False
                
            finally:
                driver.quit()
                
        except ImportError:
            print("Selenium not installed. Install with: pip install selenium")
            return False
        except Exception as e:
            print(f"Selenium login error: {e}")
            return False
    
    def scrape_listing_with_selenium(self, listing_url):
        """
        Scrape listing using Selenium to handle JavaScript-rendered content
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            import time as sleep_time
            
            print("Using Selenium to scrape JavaScript-rendered content...")
            
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            # Transfer cookies from requests session to Selenium
            driver = webdriver.Chrome(options=chrome_options)
            
            try:
                # First navigate to the base URL to set domain for cookies
                driver.get(self.base_url)
                
                # Add all cookies from the requests session
                for cookie_name, cookie_value in self.session.cookies.items():
                    driver.add_cookie({
                        'name': cookie_name,
                        'value': cookie_value,
                        'domain': '.aryeo.com'  # Adjust domain as needed
                    })
                
                # Now navigate to the actual listing page
                driver.get(listing_url)
                
                # Wait for page to load completely
                sleep_time.sleep(5)
                
                # Wait for any dynamic content to load
                try:
                    WebDriverWait(driver, 10).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                except:
                    pass
                
                # Extract data from the fully loaded page
                listing_data = self._extract_selenium_listing_data(driver)
                
                return listing_data
                
            finally:
                driver.quit()
                
        except ImportError:
            print("Selenium not available for JavaScript scraping")
            return None
        except Exception as e:
            print(f"Error scraping with Selenium: {e}")
            return None
    
    def _extract_selenium_listing_data(self, driver):
        """
        Extract data from listing page using Selenium WebDriver
        """
        data = {}
        
        try:
            # Get page source for BeautifulSoup parsing
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Extract title
            title_elem = soup.find('h1') or soup.find('title')
            if title_elem:
                data['title'] = title_elem.get_text(strip=True)
            
            # Extract all form data with Selenium
            form_data = {}
            
            # Get all input elements
            inputs = driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs:
                try:
                    name = inp.get_attribute('name')
                    value = inp.get_attribute('value') or ""
                    input_type = inp.get_attribute('type') or "text"
                    placeholder = inp.get_attribute('placeholder') or ""
                    
                    if name and input_type not in ['submit', 'button', 'hidden', 'csrf']:
                        # For certain input types, get the actual current value
                        if input_type in ['text', 'email', 'number', 'tel']:
                            try:
                                current_value = driver.execute_script("return arguments[0].value;", inp)
                                value = current_value if current_value else value
                            except:
                                pass
                        
                        form_data[name] = {
                            'value': value,
                            'type': input_type,
                            'placeholder': placeholder
                        }
                except Exception as e:
                    continue
            
            # Get all textarea elements
            textareas = driver.find_elements(By.TAG_NAME, "textarea")
            for textarea in textareas:
                try:
                    name = textarea.get_attribute('name')
                    if name:
                        # Get actual text content
                        value = driver.execute_script("return arguments[0].value;", textarea)
                        placeholder = textarea.get_attribute('placeholder') or ""
                        
                        form_data[name] = {
                            'value': value,
                            'type': 'textarea',
                            'placeholder': placeholder
                        }
                except Exception as e:
                    continue
            
            # Get all select elements
            selects = driver.find_elements(By.TAG_NAME, "select")
            for select in selects:
                try:
                    name = select.get_attribute('name')
                    if name:
                        # Get selected option
                        selected_options = select.find_elements(By.CSS_SELECTOR, "option:checked")
                        selected_value = selected_options[0].get_attribute('value') if selected_options else ""
                        selected_text = selected_options[0].text if selected_options else ""
                        
                        # Get all options
                        all_options = select.find_elements(By.TAG_NAME, "option")
                        options = []
                        for opt in all_options:
                            options.append({
                                'value': opt.get_attribute('value'),
                                'text': opt.text
                            })
                        
                        form_data[name] = {
                            'selected_value': selected_value,
                            'selected_text': selected_text,
                            'options': options,
                            'type': 'select'
                        }
                except Exception as e:
                    continue
            
            data['form_data'] = form_data
            
            # Extract images with more detail
            images = []
            img_elements = driver.find_elements(By.TAG_NAME, "img")
            for img in img_elements:
                try:
                    src = img.get_attribute('src')
                    if src and 'data:image' not in src:  # Skip base64 images
                        if src.startswith('/'):
                            src = urljoin(self.base_url, src)
                        
                        images.append({
                            'src': src,
                            'alt': img.get_attribute('alt') or "",
                            'title': img.get_attribute('title') or "",
                            'class': img.get_attribute('class') or "",
                            'width': img.get_attribute('width') or "",
                            'height': img.get_attribute('height') or "",
                            'data_src': img.get_attribute('data-src') or ""  # For lazy loading
                        })
                except Exception as e:
                    continue
            
            data['images'] = images
            
            # Look for specific real estate data
            real_estate_data = {}
            
            # Try to find property details by common patterns
            property_fields = [
                'price', 'address', 'bedrooms', 'bathrooms', 'square_feet', 'sqft',
                'lot_size', 'year_built', 'property_type', 'listing_type', 'mls',
                'description', 'features', 'amenities'
            ]
            
            for field in property_fields:
                # Try multiple selectors for each field
                selectors = [
                    f"[name*='{field}']",
                    f"[id*='{field}']", 
                    f"[class*='{field}']",
                    f"[data-field='{field}']"
                ]
                
                for selector in selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            value = elem.get_attribute('value') or elem.text
                            if value and value.strip():
                                real_estate_data[field] = value.strip()
                                break
                        if field in real_estate_data:
                            break
                    except:
                        continue
            
            if real_estate_data:
                data['property_details'] = real_estate_data
            
            # Extract any JavaScript variables or JSON data
            try:
                # Look for window variables
                js_data = driver.execute_script("""
                    var data = {};
                    for (var prop in window) {
                        if (prop.includes('listing') || prop.includes('property') || prop.includes('data')) {
                            try {
                                if (typeof window[prop] === 'object' && window[prop] !== null) {
                                    data[prop] = JSON.parse(JSON.stringify(window[prop]));
                                }
                            } catch(e) {}
                        }
                    }
                    return data;
                """)
                
                if js_data:
                    data['javascript_data'] = js_data
            except:
                pass
            
            # Get full HTML for manual inspection if needed
            data['page_url'] = driver.current_url
            data['page_title'] = driver.title
            
            # Extract any data attributes
            data_attributes = {}
            elements_with_data = driver.find_elements(By.CSS_SELECTOR, "[data-*]")
            for elem in elements_with_data[:50]:  # Limit to first 50 to avoid too much data
                try:
                    attrs = driver.execute_script("""
                        var attrs = {};
                        for (var i = 0; i < arguments[0].attributes.length; i++) {
                            var attr = arguments[0].attributes[i];
                            if (attr.name.startsWith('data-')) {
                                attrs[attr.name] = attr.value;
                            }
                        }
                        return attrs;
                    """, elem)
                    
                    if attrs:
                        tag_name = elem.tag_name
                        if tag_name not in data_attributes:
                            data_attributes[tag_name] = []
                        data_attributes[tag_name].append(attrs)
                except:
                    continue
            
            if data_attributes:
                data['data_attributes'] = data_attributes
            
            return data
            
        except Exception as e:
            print(f"Error extracting Selenium data: {e}")
            return {'error': str(e)}

    def scrape_listing(self, listing_url):
        """
        Scrape a specific listing page (enhanced version)
        """
        if not self.logged_in:
            print("Please login first!")
            return None
        
        # First try regular requests method
        print("Trying regular requests method...")
        listing_data = self._scrape_with_requests(listing_url)
        
        # If regular method returns empty data, try Selenium
        if (not listing_data or 
            not listing_data.get('form_data') or 
            len(listing_data.get('form_data', {})) == 0):
            
            print("Regular method returned limited data. Trying Selenium method...")
            selenium_data = self.scrape_listing_with_selenium(listing_url)
            
            if selenium_data:
                return selenium_data
        
        return listing_data
    
    def _scrape_with_requests(self, listing_url):
        """
        Original scraping method using requests
        """
        try:
            headers = {
                'Referer': f"{self.base_url}/dashboard",
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = self.session.get(listing_url, headers=headers)
            response.raise_for_status()
            
            if response.encoding is None:
                response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            listing_data = self._extract_listing_data(soup)
            
            return listing_data
            
        except requests.RequestException as e:
            print(f"Error scraping with requests: {e}")
            return None
    
    def _extract_listing_data(self, soup):
        """
        Extract relevant data from the listing page
        """
        data = {}
        
        try:
            # Extract title/property name
            title_elem = soup.find('h1') or soup.find('title')
            if title_elem:
                data['title'] = title_elem.get_text(strip=True)
            
            # Extract form data (input fields)
            form_data = {}
            inputs = soup.find_all('input')
            for input_elem in inputs:
                name = input_elem.get('name')
                value = input_elem.get('value', '')
                input_type = input_elem.get('type', 'text')
                
                if name and input_type not in ['submit', 'button', 'hidden']:
                    form_data[name] = value
            
            # Extract textarea data
            textareas = soup.find_all('textarea')
            for textarea in textareas:
                name = textarea.get('name')
                if name:
                    form_data[name] = textarea.get_text(strip=True)
            
            # Extract select options
            selects = soup.find_all('select')
            for select in selects:
                name = select.get('name')
                if name:
                    selected_option = select.find('option', selected=True)
                    if selected_option:
                        form_data[name] = selected_option.get('value', selected_option.get_text(strip=True))
                    else:
                        options = [opt.get('value', opt.get_text(strip=True)) for opt in select.find_all('option')]
                        form_data[f"{name}_options"] = options
            
            data['form_data'] = form_data
            
            # Extract images
            images = []
            img_tags = soup.find_all('img')
            for img in img_tags:
                src = img.get('src')
                if src:
                    if src.startswith('/'):
                        src = urljoin(self.base_url, src)
                    images.append({
                        'src': src,
                        'alt': img.get('alt', ''),
                        'class': img.get('class', [])
                    })
            data['images'] = images
            
            # Extract JSON data embedded in the page
            script_tags = soup.find_all('script', type='application/json')
            json_data = []
            for script in script_tags:
                try:
                    json_content = json.loads(script.string)
                    json_data.append(json_content)
                except (json.JSONDecodeError, AttributeError):
                    continue
            
            if json_data:
                data['embedded_json'] = json_data
            
            # Extract meta information
            meta_data = {}
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                name = meta.get('name') or meta.get('property')
                content = meta.get('content')
                if name and content:
                    meta_data[name] = content
            
            if meta_data:
                data['meta'] = meta_data
            
            return data
            
        except Exception as e:
            print(f"Error extracting data: {e}")
            return {'error': str(e)}
    
    def save_to_file(self, data, filename):
        """
        Save scraped data to a JSON file
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Data saved to {filename}")
        except Exception as e:
            print(f"Error saving data: {e}")

# Usage example
def main():
    scraper = AryeoScraper()
    
    # Login credentials
    username = "john@moshinremedia.com"
    password = "Madmax1993"
    
    # Try primary login method first
    print("Trying enhanced login method...")
    login_success = scraper.login(username, password)
    
    # If primary method fails, try Selenium
    if not login_success:
        print("\nPrimary login failed. Trying Selenium method...")
        print("Note: You need to install selenium and chromedriver for this to work.")
        print("Install with: pip install selenium")
        
        try_selenium = input("Try Selenium login? (y/n): ").lower().strip() == 'y'
        if try_selenium:
            login_success = scraper.try_selenium_login(username, password)
    
    if login_success:
        # URL to scrape
        listing_url = input("Enter the listing URL: ")
        
        # Scrape the listing
        print("Scraping listing data...")
        listing_data = scraper.scrape_listing(listing_url)
        
        if listing_data:
            # Display extracted data
            print("\n=== SCRAPED DATA ===")
            print(json.dumps(listing_data, indent=2))
            
            # Save to file
            filename = f"listing_data_{int(time.time())}.json"
            scraper.save_to_file(listing_data, filename)
        else:
            print("Failed to scrape listing data.")
    else:
        print("\nAll login methods failed.")
        print("\nPossible solutions:")
        print("1. Check if your credentials are correct")
        print("2. Try logging in manually first to ensure the account works")
        print("3. Install Selenium for browser-based login: pip install selenium")
        print("4. The site might require 2FA or have CAPTCHA protection")
        print("5. Check if your account is locked or requires verification")

if __name__ == "__main__":
    main()