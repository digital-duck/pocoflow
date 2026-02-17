"""PocoFlow Batch Flow — image filter pipeline.

Demonstrates: batch-over-flows pattern using a loop in a single node.
Original PocketFlow uses BatchFlow + self.params; PocoFlow loops inside exec().
"""

import os
from PIL import Image, ImageEnhance, ImageFilter
from pocoflow import Node, Flow, Store


class ProcessImages(Node):
    """Processes multiple images with multiple filters in a single node."""

    def prep(self, store):
        images = store.get("images") or ["cat.jpg", "dog.jpg", "bird.jpg"]
        filters = store.get("filters") or ["grayscale", "blur", "sepia"]
        return [(img, f) for img in images for f in filters]

    def exec(self, prep_result):
        os.makedirs("output", exist_ok=True)
        results = []

        for img_name, filter_name in prep_result:
            img_path = os.path.join("images", img_name)
            image = Image.open(img_path)

            if filter_name == "grayscale":
                filtered = image.convert("L")
            elif filter_name == "blur":
                filtered = image.filter(ImageFilter.BLUR)
            elif filter_name == "sepia":
                enhancer = ImageEnhance.Color(image)
                grayscale = enhancer.enhance(0.3)
                filtered = ImageEnhance.Brightness(grayscale).enhance(1.2)
            else:
                raise ValueError(f"Unknown filter: {filter_name}")

            base_name = os.path.splitext(img_name)[0]
            output_path = os.path.join("output", f"{base_name}_{filter_name}.jpg")
            filtered.save(output_path, "JPEG")
            print(f"  Saved: {output_path}")
            results.append(output_path)

        return results

    def post(self, store, prep_result, exec_result):
        store["output_files"] = exec_result
        return "done"


def main():
    print("Processing images with filters...\n")

    store = Store(
        data={
            "images": ["cat.jpg", "dog.jpg", "bird.jpg"],
            "filters": ["grayscale", "blur", "sepia"],
            "output_files": [],
        },
        name="image_batch",
    )

    flow = Flow(start=ProcessImages())
    flow.run(store)

    print(f"\nAll images processed! {len(store['output_files'])} files created.")
    print("Check the 'output' directory for results.")


if __name__ == "__main__":
    main()
