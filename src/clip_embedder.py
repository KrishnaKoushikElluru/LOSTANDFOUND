# src/clip_embedder.py
import torch
import clip
from PIL import Image
import numpy as np

class CLIPEmbedder:
    def __init__(self, model_name: str = "ViT-B/32", device: str = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        # load CLIP model (OpenAI CLIP)
        self.model, self.preprocess = clip.load(model_name, device=self.device)
        self.model.eval()

    def embed_image(self, pil_img: Image.Image):
        """
        Accepts a PIL.Image and returns a normalized float32 list (same format as chroma_sync)
        """
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        inp = self.preprocess(pil_img).unsqueeze(0).to(self.device)
        with torch.no_grad():
            emb = self.model.encode_image(inp)
        emb = emb / emb.norm(dim=-1, keepdim=True)
        emb = emb.cpu().numpy().astype("float32").squeeze()
        return emb.tolist()

    def embed_text(self, text: str):
        tokens = clip.tokenize([text]).to(self.device)
        with torch.no_grad():
            emb = self.model.encode_text(tokens)
        emb = emb / emb.norm(dim=-1, keepdim=True)
        emb = emb.cpu().numpy().astype("float32").squeeze()
        return emb.tolist()
