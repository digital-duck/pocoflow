"""PocoFlow Parallel Batch Flow — parallel image processing.

Demonstrates: AsyncNode + asyncio.gather for parallel batch-over-flows.
Original PocketFlow uses AsyncParallelBatchFlow + AsyncNode with prep_async/post_async;
PocoFlow uses a single AsyncNode that processes all combinations in parallel.
"""

import asyncio
import os
import time
from PIL import Image, ImageEnhance, ImageFilter
from pocoflow import AsyncNode, Flow, Store


def apply_filter(image, filter_name):
    """Apply a named filter to a PIL Image."""
    if filter_name == "grayscale":
        return image.convert("L")
    elif filter_name == "blur":
        return image.filter(ImageFilter.BLUR)
    elif filter_name == "sepia":
        enhancer = ImageEnhance.Color(image)
        grayscale = enhancer.enhance(0.3)
        return ImageEnhance.Brightness(grayscale).enhance(1.2)
    else:
        raise ValueError(f"Unknown filter: {filter_name}")


class SequentialProcessImages(AsyncNode):
    """Processes image-filter combinations one at a time."""

    def prep(self, store):
        images = store.get("images") or ["cat.jpg", "dog.jpg", "bird.jpg"]
        filters = store.get("filters") or ["grayscale", "blur", "sepia"]
        return [(img, f) for img in images for f in filters]

    async def exec_async(self, prep_result):
        os.makedirs("output_sequential", exist_ok=True)
        results = []
        for img_name, filter_name in prep_result:
            # Simulate async I/O delay
            await asyncio.sleep(0.1)
            img_path = os.path.join("images", img_name)
            image = Image.open(img_path)
            filtered = apply_filter(image, filter_name)
            base = os.path.splitext(img_name)[0]
            out_path = os.path.join("output_sequential", f"{base}_{filter_name}.jpg")
            filtered.save(out_path, "JPEG")
            print(f"  [Sequential] {out_path}")
            results.append(out_path)
        return results

    def post(self, store, prep_result, exec_result):
        store["sequential_files"] = exec_result
        return "done"


class ParallelProcessImages(AsyncNode):
    """Processes image-filter combinations in parallel using asyncio.gather."""

    def prep(self, store):
        images = store.get("images") or ["cat.jpg", "dog.jpg", "bird.jpg"]
        filters = store.get("filters") or ["grayscale", "blur", "sepia"]
        return [(img, f) for img in images for f in filters]

    async def exec_async(self, prep_result):
        os.makedirs("output_parallel", exist_ok=True)

        async def process_one(img_name, filter_name):
            await asyncio.sleep(0.1)  # Simulate async I/O
            img_path = os.path.join("images", img_name)
            image = Image.open(img_path)
            filtered = apply_filter(image, filter_name)
            base = os.path.splitext(img_name)[0]
            out_path = os.path.join("output_parallel", f"{base}_{filter_name}.jpg")
            filtered.save(out_path, "JPEG")
            print(f"  [Parallel] {out_path}")
            return out_path

        tasks = [process_one(img, f) for img, f in prep_result]
        return await asyncio.gather(*tasks)

    def post(self, store, prep_result, exec_result):
        store["parallel_files"] = list(exec_result)
        return "done"


def main():
    images = ["cat.jpg", "dog.jpg", "bird.jpg"]
    filters = ["grayscale", "blur", "sepia"]

    # Sequential
    store_seq = Store(
        data={"images": images, "filters": filters, "sequential_files": []},
        name="sequential",
    )
    print("\n=== Sequential Processing ===")
    t0 = time.time()
    Flow(start=SequentialProcessImages()).run(store_seq)
    t1 = time.time()

    # Parallel
    store_par = Store(
        data={"images": images, "filters": filters, "parallel_files": []},
        name="parallel",
    )
    print("\n=== Parallel Processing ===")
    t2 = time.time()
    Flow(start=ParallelProcessImages()).run(store_par)
    t3 = time.time()

    print(f"\n--- Timing ---")
    print(f"Sequential: {t1 - t0:.2f}s ({len(store_seq['sequential_files'])} files)")
    print(f"Parallel:   {t3 - t2:.2f}s ({len(store_par['parallel_files'])} files)")
    n = len(images) * len(filters)
    print(f"Speedup: {(t1 - t0) / (t3 - t2):.1f}x for {n} image-filter combinations")


if __name__ == "__main__":
    main()
