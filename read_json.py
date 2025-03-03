
import json
 
with open('/var/lib/dpkg/ocrlocalworkspace/results/output_d36d523a3ceac01458f5faac25f6f07cbe57aeb4.jsonl', 'r', encoding='utf-8') as f:
    data = json.load(f)
    print(data)