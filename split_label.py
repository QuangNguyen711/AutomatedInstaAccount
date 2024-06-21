import os
import shutil

list_folder = ['kien_fake_images', 'kien_real_images', 'real_images_quang']

for folder_name in list_folder:
    for image_name in os.listdir (folder_name):
        label = image_name.split ("_")[-1][0]
        if label == '0':
            shutil.copy (folder_name + '/' + image_name, "bad_images/" + image_name)
        else:
            shutil.copy (folder_name + '/' + image_name, "good_images/" + image_name)
