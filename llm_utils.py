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
from logger_config import logger, timed_log

class CustomEmbedder:
    def __init__(self, model_name="BAAI/bge-m3", device="cuda"):
        self.device = device if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device)
        if self.device == "cuda":
            self.model = self.model.to(torch.bfloat16)

    def encode(self, sentences):
        if isinstance(sentences, str): sentences = [sentences]
        encoded_input = self.tokenizer(sentences, padding=True, truncation=True, max_length=512, return_tensors='pt').to(self.device)
        with torch.no_grad():
            model_output = self.model(**encoded_input)
        sentence_embs = model_output[0][:, 0]
        sentence_embs = F.normalize(sentence_embs, p=2, dim=1)
        return sentence_embs.float().cpu().numpy()

    def unload(self):
        if self.device == "cuda" and self.model is not None:
            del self.model
            del self.tokenizer
            self.model = None
            self.tokenizer = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("📦 Embedder GPU'dan kaldırıldı")

class RerankerEngine:
    def __init__(self, model_name='BAAI/bge-reranker-v2-m3', device="cuda"):
        self.device = device if torch.cuda.is_available() else "cpu"
        self.model_name = model_name
        self.model = None
        self._load_model()

    def _load_model(self):
        self.model = CrossEncoder(self.model_name, max_length=512, device=self.device)

    def predict(self, pairs):
        if self.model is None:
            self._load_model()
        return self.model.predict(pairs)

    def unload(self):
        if self.model is not None:
            del self.model
            self.model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("📦 Reranker GPU'dan kaldırıldı")

class LLMEngine:
    """
    RTX 3090 (24GB VRAM) için optimize edilmiş LLM motoru.
    8-bit quantization + sequential loading ile diğer modelleri GPU'dan kaldırır.
    """
    _instance_count = 0

    def __init__(self, model_name="Qwen/Qwen2.5-14B-Instruct", load_in_8bit=True):
        LLMEngine._instance_count += 1
        logger.info(f"🔢 LLMEngine instance #{LLMEngine._instance_count} oluşturuluyor...")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = model_name
        self.load_in_8bit = load_in_8bit
        self.tokenizer = None
        self.model = None

        logger.info(f"🚀 Model yükleniyor (Hugging Face): {model_name}...")

        if torch.cuda.is_available():
            mem_allocated = torch.cuda.memory_allocated() / 1024**3
            mem_cached = torch.cuda.memory_reserved() / 1024**3
            logger.info(f"   GPU Memory before: allocated={mem_allocated:.2f}GB, cached={mem_cached:.2f}GB")

        self._load_model()

        if torch.cuda.is_available():
            mem_allocated = torch.cuda.memory_allocated() / 1024**3
            mem_cached = torch.cuda.memory_reserved() / 1024**3
            logger.info(f"   GPU Memory after: allocated={mem_allocated:.2f}GB, cached={mem_cached:.2f}GB")

        logger.info("✅ Model GPU'ya başarıyla yüklendi!")

    def _load_model(self):
        if self.load_in_8bit:
            bnb_config = BitsAndBytesConfig(
                load_in_8bit=True,
                bnb_8bit_compute_dtype=torch.float16
            )
        else:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16
            )

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.float16 if self.load_in_8bit else torch.bfloat16
        )

    def unload(self):
        if self.model is not None:
            del self.model
            del self.tokenizer
            self.model = None
            self.tokenizer = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("🧹 LLM GPU'dan kaldırıldı")

    @timed_log
    def generate(self, messages, temperature=0.4, stream=False, max_new_tokens=1024, top_p=1.0):
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        inputs = self.tokenizer([prompt], return_tensors="pt").to(self.device)

        if stream:
            return self._stream_generate(inputs, temperature, max_new_tokens, top_p)
        else:
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            new_tokens = outputs[0][inputs.input_ids.shape[-1]:]
            return self.tokenizer.decode(new_tokens, skip_special_tokens=True)

    @timed_log
    def _stream_generate(self, inputs, temperature, max_new_tokens, top_p=1.0):
        logger.debug("Starting streaming generation")
        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        generation_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
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
_initialized = False

def get_embedder():
    global _embedder
    if _embedder is None:
        logger.info("📦 Embedder yükleniyor...")
        _embedder = CustomEmbedder()
        logger.info("✅ Embedder hazır")
    return _embedder

def get_reranker():
    global _reranker
    if _reranker is None:
        logger.info("📦 Reranker yükleniyor...")
        _reranker = RerankerEngine()
        logger.info("✅ Reranker hazır")
    return _reranker

def get_llm():
    global _llm, _initialized, _embedder, _reranker

    if _embedder is not None:
        logger.info("📦 Embedder unload ediliyor (LLM için)...")
        _embedder.unload()
        _embedder = None
    if _reranker is not None:
        logger.info("📦 Reranker unload ediliyor (LLM için)...")
        _reranker.unload()
        _reranker = None

    if _llm is None:
        logger.info("🚀 LLM yükleniyor...")
        _llm = LLMEngine(load_in_8bit=True)
        _initialized = True
        logger.info("✅ LLM hazır")
    return _llm

def reload_embedder_reranker():
    global _embedder, _reranker, _llm
    if _llm is not None:
        logger.info("📦 LLM unload ediliyor (embedder/reranker için)...")
        _llm.unload()
        _llm = None

    if _embedder is None:
        logger.info("📦 Embedder yükleniyor...")
        _embedder = CustomEmbedder()
        logger.info("✅ Embedder hazır")
    if _reranker is None:
        logger.info("📦 Reranker yükleniyor...")
        _reranker = RerankerEngine()
        logger.info("✅ Reranker hazır")

def get_gpu_memory():
    if torch.cuda.is_available():
        return {
            "allocated": torch.cuda.memory_allocated() / 1024**3,
            "reserved": torch.cuda.memory_reserved() / 1024**3,
            "total": torch.cuda.get_device_properties(0).total_mem / 1024**3
        }
    return {"allocated": 0, "reserved": 0, "total": 0}

def clear_memory():
    global _embedder, _reranker, _llm
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    if _llm is not None:
        _llm.unload()
    if _embedder is not None:
        _embedder.unload()
    if _reranker is not None:
        _reranker.unload()
    _embedder = None
    _reranker = None
    _llm = None
    logger.info("🧹 Memory temizlendi, tüm modeller kaldırıldı")
