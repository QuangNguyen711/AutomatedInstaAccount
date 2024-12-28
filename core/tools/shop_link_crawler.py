import matplotlib.pyplot as plt
import pandas as pd
import os
import ast
import numpy as np
from PIL import Image
from tqdm import tqdm
# import google_colab_selenium as gs
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep
import time
import urllib.request
from bs4 import BeautifulSoup
from bs4.element import ResultSet
import traceback
import uuid
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from ultralytics import YOLO
import google.generativeai as genai
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time

hanoi_districts = [
    "Ba Đình, Hà Nội",
    "Hoàn Kiếm, Hà Nội",
    "Tây Hồ, Hà Nội",
    "Long Biên, Hà Nội",
    "Cầu Giấy, Hà Nội",
    "Đống Đa, Hà Nội",
    "Hai Bà Trưng, Hà Nội",
    "Hoàng Mai, Hà Nội",
    "Thanh Xuân, Hà Nội",
    "Hà Đông, Hà Nội",
    "Bắc Từ Liêm, Hà Nội",
    "Nam Từ Liêm, Hà Nội",
]

coffee_varians = ["Coffee shop", "Cà phê", "Cafe", "Coffee"]

coffee_shop_linkss = []

def coffee_shop_link_crawler(location, target, number_of_demanded_links):
    # Initialize the undetected Chrome driver
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")  # Open the browser in full-screen mode
    options.add_argument("--disable-blink-features=AutomationControlled")  # Avoid detection
    driver = uc.Chrome(options=options)  # Replace `gs.UndetectedChrome()` with `uc.Chrome()`

    # Open the Google Maps page
    driver.get('https://www.google.com/maps/@9.7847623,105.6285175,11z?hl=vi-VN&entry=ttu')
    time.sleep(5)

    # Get the search box element
    search_box = driver.find_element(By.ID, 'searchboxinput')

    # Enter the search key
    finding_key = location
    search_box.send_keys(finding_key)
    time.sleep(5)

    # Click the search button
    find_text = driver.find_element(By.ID, "searchbox-searchbutton")
    find_text.click()
    time.sleep(5)

    # Clear the search box
    search_box.clear()

    # Search for target
    search_box.send_keys(target)
    find_text.click()
    time.sleep(5)

    # Function to scroll down
    def scroll_down():
        body = driver.find_element(By.XPATH, '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[1]/div[1]')
        body.send_keys(Keys.END)
        time.sleep(3)

    # Collect links until we reach the demanded number
    coffee_shop_links = set()

    counter = 0

    while len(coffee_shop_links) < number_of_demanded_links:
        # Find all coffee shop elements
        coffee_shops = driver.find_elements(By.CLASS_NAME, "hfpxzc")

        # Collect the links
        for coffee_shop in coffee_shops:
            link = coffee_shop.get_property("href")
            if link and link not in coffee_shop_links:
                coffee_shop_links.add(link)
            if len(coffee_shop_links) >= number_of_demanded_links:
                break

        # Scroll down if not enough links are collected
        if len(coffee_shop_links) < number_of_demanded_links:
            scroll_down()

        print(f"Collected {len(coffee_shop_links)} links")

        if counter != len(coffee_shop_links):
            counter = len(coffee_shop_links)
        else:
            break

    # Save a screenshot and quit the driver
    specific_location = location.split(",")[0]
    specific_location = specific_location.replace(" ", "_")
    driver.save_screenshot(f'Checkpoint_{specific_location}.png')
    driver.quit()

    return coffee_shop_links

# Example usage: Replace `hanoi_districts` and `coffee_varians` with your data
for district in hanoi_districts:
    for coffee_variant in coffee_varians:
        coffee_shop_links = coffee_shop_link_crawler(district, coffee_variant, 50)
        coffee_shop_linkss.extend(coffee_shop_links)