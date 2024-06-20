import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re

def web_driver():
    options = webdriver.FirefoxOptions()
    options.add_argument("--verbose")
    options.add_argument('--no-sandbox')
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument("--window-size=1920, 1200")
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Firefox(options=options)
    return driver
    
driver = web_driver()
wait = WebDriverWait(driver, 10)

def login_to_pinterest_with_google(email, password):
    driver.get("https://www.pinterest.com/login/")
    time.sleep(2)
    
    # Enter the email
    email_field = driver.find_element(By.CSS_SELECTOR,'input[id="email"]')
    email_field.send_keys(email)
    
    # Enter the password
    password_field = driver.find_element(By.CSS_SELECTOR,'input[id="password"]')
    password_field.send_keys(password)

    driver.find_element(By.CSS_SELECTOR, 'div[data-test-id="registerFormSubmitButton"]').click()
    time.sleep(3)
    
    driver.save_screenshot('login.png')

# Replace with your actual Google account credentials
google_email = 'yolov2024@gmail.com'
google_password = 'Quangcuoi12345'

# Login to Pinterest
login_to_pinterest_with_google(google_email, google_password)

# Pinterest URL for coffee-related images
url = 'https://www.pinterest.com/search/pins/?q=coffee%20shop'

# Maximum number of images to download
max_images = 50
images_saved = 0
folder_path = 'real_images'  # Replace with your desired download path

# Create folder if it doesn't exist
if not os.path.exists(folder_path):
    os.makedirs(folder_path)

# Access Pinterest
driver.get(url)
time.sleep(2)

wait = WebDriverWait(driver, 10)

while images_saved < max_images:
    # Find all div elements with role="listitem"
    list_items = driver.find_elements(By.XPATH, '//div[@role="listitem"]')
    driver.save_screenshot('pinterest_login.png')
    for index, item in enumerate(list_items):
        try:
            # Find the a tag inside the div
            a_tag = item.find_element(By.TAG_NAME, 'a')
            href = a_tag.get_attribute('href')
            print(f"Found href: {href}")

            # Click on the a tag to open the larger view
            a_tag.click()
            time.sleep(2)
            
            # Wait for the larger image to load
            large_image_div = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-test-id="pin-closeup-image"]')))
            large_image = large_image_div.find_element(By.CSS_SELECTOR, 'img[src]')

            image_url = large_image.get_attribute('src')
            driver.save_screenshot('view.png')
            
            # Validate image URL
            if image_url and re.match(r"^https?://", image_url):
                image_name = f"coffee_shop_{images_saved}.jpg"
                image_path = os.path.join(folder_path, image_name)
                
                # Download and save the image
                print(f"Getting image from {image_url}")
                response = requests.get(image_url)
                with open(image_path, 'wb') as f:
                    f.write(response.content)
                print(f"Saved image {image_name}")
                
                images_saved += 1

                # Close the image view
                driver.execute_script("window.history.go(-1)")
                time.sleep(2)
                driver.save_screenshot('login.png')

            
            # Stop if maximum images are saved
            if images_saved >= max_images:
                break

        except Exception as e:
            print(f"Error processing item {index}: {e}")
            driver.execute_script("window.history.go(-1)")
            time.sleep(2)

    # Scroll down to load more images
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

# Quit the driver
driver.quit()