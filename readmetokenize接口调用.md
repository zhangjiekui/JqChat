curl -X 'POST' \
  'http://10.1.150.105:8082/tokenize' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "model": "Qwen/Qwen3-Embedding-0.6B",
  "prompt": "待处理的文本",
  "add_special_tokens": true,
  "return_token_strs": false,
  "additionalProp1": {}
}'

{
  "count": 5,
  "max_model_len": 32768,
  "tokens": [
    74193,
    54542,
    9370,
    108704,
    151643
  ],
  "token_strs": null
}


curl -X 'POST' \
  'http://10.1.150.105:8082/detokenize' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "model": "Qwen/Qwen3-Embedding-0.6B",
  "tokens": [
    74193,
    54542,
    9370,
    108704,
    151643
  ],
  "additionalProp1": {}
}'

{
  "prompt": "待处理的文本<|endoftext|>"
}