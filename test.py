import os

for file in os.listdir("images"):
    fname = file[:-4].split("_")[0]
    os.rename(f"images/{file}.png", f"images/{fname}.png")