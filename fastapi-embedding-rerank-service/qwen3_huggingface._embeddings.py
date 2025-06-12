#coding:utf8
import os
from typing import Dict, Optional, List, Union
import torch
from torch import nn
import torch.nn.functional as F

from torch import Tensor
from langchain_huggingface import HuggingFaceEmbeddings
from transformers.utils import is_flash_attn_2_available
import numpy as np
from collections import defaultdict

import logging
logger = logging.getLogger(__name__)

class Qwen3Embedding():
    def __init__(self, model_name_or_path, instruction=None, use_cuda: bool = True, max_length=8192):
        if instruction is None:
            instruction = 'Given the user query, retrieve the relevant passages that answer the query'
        self.instruction = instruction
        tokenizer_kwargs={"padding_side": "left"}
        encode_kwargs = {'normalize_embeddings': False}
        query_encode_kwargs = {'prompt': self.instruction}
        if is_flash_attn_2_available() and torch.cuda.is_available() and use_cuda:
            _model_kwargs={"attn_implementation": "flash_attention_2", "torch_dtype":torch.float16, "device_map": "auto"}
        elif torch.cuda.is_available() and use_cuda:
            _model_kwargs={"device_map": "cuda"},
        else:
            _model_kwargs={"device_map": "cpu"}
            
        model_kwargs = {"model_kwargs":  _model_kwargs}
        self.model = HuggingFaceEmbeddings(
                model_name=model_name_or_path,
                model_kwargs=model_kwargs,
                encode_kwargs=encode_kwargs,
                query_encode_kwargs = query_encode_kwargs,
            )

    

if __name__ == "__main__":
    model_path = '/data/models/Qwen/Qwen3-Embedding-0___6B'
    # from sentence_transformers import SentenceTransformer
    # model = SentenceTransformer(
    #     model_path,
    #     model_kwargs={"attn_implementation": "flash_attention_2", "torch_dtype":torch.float16, "device_map": "auto"},
    #     tokenizer_kwargs={"padding_side": "left"},
    # )

    model = Qwen3Embedding(model_path)
    queries = ['What is the capital of China?', 'Explain gravity']
    documents = [
        "The capital of China is Beijing.",
        "Gravity is a force that attracts two bodies towards each other. It gives weight to physical objects and is responsible for the movement of planets around the sun."
    ]
    dim = 768  # or 1024, depending on the model
    query_outputs = model.encode(queries, is_query=True, dim=dim)
    doc_outputs = model.encode(documents, dim=dim)
    print('query outputs', query_outputs)
    print('doc outputs', doc_outputs)
    scores = (query_outputs @ doc_outputs.T) * 100
    print(scores.tolist())