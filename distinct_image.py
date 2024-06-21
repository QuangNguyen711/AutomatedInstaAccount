import os
from PIL import Image
import numpy as np

def image_to_matrix(image_path):
    # Open the image file
    with Image.open(image_path) as img:
        # Convert the image to grayscale
        img = img.convert('L')
        # Convert the image to a numpy array
        img_matrix = np.array(img)
    return img_matrix

def remove_duplicate_images(folder_path):
    unique_images = {}
    for filename in os.listdir(folder_path):
        image_path = os.path.join(folder_path, filename)
        if os.path.isfile(image_path):
            img_matrix = image_to_matrix(image_path)
            is_duplicate = False
            for stored_matrix in unique_images.values():
                if img_matrix.shape == stored_matrix.shape and np.array_equal(img_matrix, stored_matrix):
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_images[filename] = img_matrix

    # Remove duplicates
    for filename in os.listdir(folder_path):
        if filename not in unique_images:
            os.remove(os.path.join(folder_path, filename))

    return list(unique_images.keys())

# Folder path
folder_path = 'kien_fake_images'

# Remove duplicate images and get the list of unique images
unique_images = remove_duplicate_images(folder_path)
print(f"Unique images: {unique_images}")
print(f"Unique images: {len (unique_images)}")
