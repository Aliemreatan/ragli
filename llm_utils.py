# -*- coding: utf-8 -*-
import torch
import torch.nn.functional as F
from transformers import (
    AutoTokenizer, 
    AutoModel, 
    AutoModelForCausalLM, 
    pipeline, 
    BitsAndBytesConfig,
    TextIteratorStreamer
)
from sentence_transformers import CrossEncoder
from threading import Thread

class CustomEmbedder:
    def __init__(self, model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", device="cpu"):
        """VRAM tasarrufu için CPU kullanır ve hafif model seçer."""
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device)

    def encode(self, sentences):
        if isinstance(sentences, str): sentences = [sentences]
        encoded_input = self.tokenizer(sentences, padding=True, truncation=True, max_length=512, return_tensors='pt').to(self.device)
        with torch.no_grad():
            model_output = self.model(**encoded_input)
        sentence_embs = model_output[0][:, 0]
        sentence_embs = F.normalize(sentence_embs, p=2, dim=1)
        return sentence_embs.cpu().numpy()

class RerankerEngine:
    def __init__(self, model_name='BAAI/bge-reranker-base', device="cpu"):
        """Reranker CPU'da çalışarak GPU'yu Qwen'e bırakır."""
        self.device = device
        self.model = CrossEncoder(model_name, max_length=512, device=self.device)
    def predict(self, pairs):
        return self.model.predict(pairs)

class LLMEngine:
    """
    Ollama yerine doğrudan Hugging Face Transformers kütüphanesini kullanır.
    24GB VRAM için 4-bit (bitsandbytes) kuantizasyon ile optimize edilmiştir.
    """
    def __init__(self, model_name="Qwen/Qwen2.5-14B-Instruct"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🚀 Model yükleniyor (Hugging Face): {model_name}...")
        
        # 4-bit Kuantizasyon Ayarı (VRAM Tasarrufu için)
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16
        )

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True
        )
        print("✅ Model GPU'ya başarıyla yüklendi!")

    def generate(self, messages, temperature=0.4, stream=False):
        # Sohbet formatına çevir
        prompt = self.tokenizer.apply_chat_template(
            messages, 
            tokenize=False, 
            add_generation_prompt=True
        )
        inputs = self.tokenizer([prompt], return_tensors="pt").to(self.device)

        if stream:
            return self._stream_generate(inputs, temperature)
        else:
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs, 
                    max_new_tokens=1024, 
                    temperature=temperature,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            # Sadece yeni üretilen kısmı al
            new_tokens = outputs[0][inputs.input_ids.shape[-1]:]
            return self.tokenizer.decode(new_tokens, skip_special_tokens=True)

    def _stream_generate(self, inputs, temperature):
        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        generation_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=1024,
            temperature=temperature,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id
        )
        
        # Ayrı bir thread'de üretimi başlat
        thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
        thread.start()
        
        for new_text in streamer:
            yield new_text

# Singletons (Streamlit Cache mekanizması için)
_embedder = None
_reranker = None
_llm = None

def get_embedder():
    global _embedder
    if _embedder is None: _embedder = CustomEmbedder()
    return _embedder
def get_reranker():
    global _reranker
    if _reranker is None: _reranker = RerankerEngine()
    return _reranker
def get_llm():
    global _llm
    if _llm is None: _llm = LLMEngine()
    return _llm
