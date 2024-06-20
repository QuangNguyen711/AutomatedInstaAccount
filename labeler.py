import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os

class ImageLabeler:
    def __init__(self, root, image_paths):
        self.root = root
        self.root.title("Image Labeler")
        self.image_paths = image_paths
        self.labels = [-1] * len(image_paths)
        self.current_image_index = 0

        self.label_var = tk.StringVar(value="Unlabeled")

        # Create the main frame
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create the canvas to display images
        self.canvas = tk.Canvas(self.main_frame, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Create control frame for buttons
        self.control_frame = ttk.Frame(self.main_frame)
        self.control_frame.pack(fill=tk.X, expand=False)

        self.label_label = ttk.Label(self.control_frame, textvariable=self.label_var)
        self.label_label.pack(side=tk.LEFT)

        self.prev_button = ttk.Button(self.control_frame, text="Previous (J)", command=self.show_previous_image)
        self.prev_button.pack(side=tk.LEFT)

        self.next_button = ttk.Button(self.control_frame, text="Next (L)", command=self.show_next_image)
        self.next_button.pack(side=tk.LEFT)

        self.good_button = ttk.Button(self.control_frame, text="Good (←)", command=lambda: self.set_label(1))
        self.good_button.pack(side=tk.LEFT)

        self.not_good_button = ttk.Button(self.control_frame, text="Not Good (→)", command=lambda: self.set_label(0))
        self.not_good_button.pack(side=tk.LEFT)

        # Bind keyboard events
        self.root.bind('<Left>', lambda event: self.set_label(1))
        self.root.bind('<Right>', lambda event: self.set_label(0))
        self.root.bind('<j>', lambda event: self.show_previous_image())
        self.root.bind('<l>', lambda event: self.show_next_image())

        # Display the first image
        self.display_image()

    def display_image(self):
        image_path = self.image_paths[self.current_image_index]
        image = Image.open(image_path)
        image.thumbnail((800, 600))
        self.tk_image = ImageTk.PhotoImage(image)
        self.canvas.create_image(400, 300, image=self.tk_image)

        current_label = self.labels[self.current_image_index]
        label_text = "Good" if current_label == 1 else "Not Good" if current_label == 0 else "Unlabeled"
        self.label_var.set(f"Image {self.current_image_index + 1}/{len(self.image_paths)}: {label_text}")

    def show_previous_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.display_image()

    def show_next_image(self):
        if self.current_image_index < len(self.image_paths) - 1:
            self.current_image_index += 1
            self.display_image()

    def set_label(self, label):
        old_path = self.image_paths[self.current_image_index]
        old_label = self.labels[self.current_image_index]

        # Skip renaming if the label is not changed
        if old_label != label:
            directory, filename = os.path.split(old_path)
            name, ext = os.path.splitext(filename)
            if "_" in name:
                name = name.split("_")[0]
            new_name = f"{name}_{label}{ext}"
            new_path = os.path.join(directory, new_name)
            os.rename(old_path, new_path)

            self.image_paths[self.current_image_index] = new_path
            self.labels[self.current_image_index] = label

        self.show_next_image()

    def get_labels(self):
        return self.labels

# Load images from a directory
def load_image_paths(directory):
    supported_formats = ('.jpg', '.jpeg', '.png', '.bmp', '.gif')
    return [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith(supported_formats)]

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Image Labeler")
    root.geometry("800x600")
    image_directory = "images"
    image_paths = load_image_paths(image_directory)
    app = ImageLabeler(root, image_paths)
    root.mainloop()

    # After closing the app, you can get the labels
    labels = app.get_labels()
    print(labels)
