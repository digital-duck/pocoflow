"""PocoFlow Tool PDF Vision — extract text from PDFs using GPT-4 Vision API.

Demonstrates: PDF processing, Vision API, multi-page extraction, report generation.
"""

import os
import io
import base64
import click
import fitz  # PyMuPDF
from PIL import Image
from openai import OpenAI
from pocoflow import Node, Flow, Store


def pdf_to_images(pdf_path, max_size=2000):
    """Convert PDF pages to PIL Images."""
    doc = fitz.open(pdf_path)
    images = []
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = tuple(int(d * ratio) for d in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            images.append((img, page_num + 1))
    finally:
        doc.close()
    return images


def image_to_base64(image):
    """Convert PIL Image to base64 string."""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


class LoadPDFNode(Node):
    def prep(self, store):
        return store["pdf_path"]

    def exec(self, prep_result):
        print(f"Loading PDF: {prep_result}")
        images = pdf_to_images(prep_result)
        print(f"  Converted {len(images)} pages to images")
        return images

    def post(self, store, prep_result, exec_result):
        store["page_images"] = exec_result
        return "default"


class ExtractTextNode(Node):
    def prep(self, store):
        return store["page_images"], store["_client"], store.get("extraction_prompt")

    def exec(self, prep_result):
        images, client, custom_prompt = prep_result
        prompt = custom_prompt or "Extract all text from this image, preserving formatting."
        results = []

        for img, page_num in images:
            print(f"  Extracting text from page {page_num}...")
            b64 = image_to_base64(img)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }],
            )
            results.append({"page": page_num, "text": response.choices[0].message.content})

        return results

    def post(self, store, prep_result, exec_result):
        store["extracted_text"] = exec_result
        return "default"


class CombineNode(Node):
    def prep(self, store):
        return store["extracted_text"]

    def exec(self, prep_result):
        sorted_pages = sorted(prep_result, key=lambda x: x["page"])
        return "\n\n".join(f"=== Page {p['page']} ===\n{p['text']}" for p in sorted_pages)

    def post(self, store, prep_result, exec_result):
        store["final_text"] = exec_result
        print("\n" + "=" * 60)
        print(exec_result)
        print("=" * 60)
        return "done"


@click.command()
@click.argument("pdf_path")
@click.option("--prompt", default=None, help="Custom extraction prompt")
def main(pdf_path, prompt):
    """Extract text from a PDF using GPT-4 Vision API."""
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found")
        return

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    load = LoadPDFNode()
    extract = ExtractTextNode()
    combine = CombineNode()
    load.then("default", extract)
    extract.then("default", combine)

    store = Store(
        data={
            "pdf_path": pdf_path,
            "extraction_prompt": prompt,
            "page_images": [],
            "extracted_text": [],
            "final_text": "",
            "_client": client,
        },
        name="pdf_vision",
    )

    flow = Flow(start=load)
    flow.run(store)


if __name__ == "__main__":
    main()
