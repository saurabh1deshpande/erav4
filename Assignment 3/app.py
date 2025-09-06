from flask import Flask, render_template_string, request
import requests
import json
import math

app = Flask(__name__)

# Dummy Gemini API key (replace with your real key)
GEMINI_API_KEY = 'AIzaSyCX2Ly4Zm_zW0USf_3pJMPOL-P9humLLWc'
GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'

# Helper to parse parameter input like '7B', '750M', etc.
def parse_params(val: str) -> float:
    val = val.strip().upper()
    if val.endswith("B"):
        return float(val[:-1]) * 1e9
    elif val.endswith("M"):
        return float(val[:-1]) * 1e6
    else:
        return float(val)

# Convert number of parameters to model size in GB (assuming FP16, 2 bytes per param)
def params_to_gb(params: float, precision: str) -> float:
    if precision == "fp32":
        bytes_per_param = 4
    elif precision == "fp16":
        bytes_per_param = 2
    elif precision == "int8":
        bytes_per_param = 1
    elif precision == "int4":
        bytes_per_param = 0.5
    else:
        bytes_per_param = 2
    return params * bytes_per_param / 1e9

# Local estimation logic with method/precision
def estimate_resources_local(params, dataset_size_gb, batch_size, epochs, method, precision, seq_len=2048, gpu_capacity=80):
    model_size_gb = params_to_gb(params, precision)
    # === Fine-tuning ===
    param_mem = model_size_gb
    if method == "full":
        opt_mem = param_mem * 2
        act_mem = param_mem * (seq_len / 2048) * (batch_size / 4)
        total_mem_ft = param_mem + opt_mem + act_mem
    elif method == "lora":
        total_mem_ft = (param_mem * 0.25) + 2
    else:  # qlora
        total_mem_ft = (param_mem * 0.15) + 1.5
    gpus_ft = math.ceil(total_mem_ft / gpu_capacity)
    flops_ft = 6 * params  # FLOPs per token
    # === Inference ===
    act_mem_inf = param_mem * (seq_len / 2048) * (batch_size / 4)
    total_mem_inf = param_mem + act_mem_inf
    gpus_inf = math.ceil(total_mem_inf / gpu_capacity)
    flops_inf = 2 * params  # forward pass FLOPs
    return {
        'memory_gb': round(total_mem_ft, 2),
        'gpu_hours': round(dataset_size_gb * epochs * 0.5 / batch_size, 2),
        'inf_memory_gb': round(total_mem_inf, 2),
        'inf_gpu_hours': round(dataset_size_gb * 0.1 / batch_size, 2),
        'gpus_ft': gpus_ft,
        'flops_ft': flops_ft,
        'gpus_inf': gpus_inf,
        'flops_inf': flops_inf
    }

def estimate_resources_gemini(params, dataset_size_gb, batch_size, epochs, method, precision, seq_len=2048, gpu_capacity=80):
    model_size_gb = params_to_gb(params, precision)
    prompt = (
        f"""
        Given the following parameters for fine-tuning a large language model (LLM):\n"
        f"Number of parameters: {params:.0f}\n"
        f"Model size: {model_size_gb:.2f} GB ({precision})\n"
        f"Dataset size: {dataset_size_gb} GB\n"
        f"Batch size: {batch_size}\n"
        f"Epochs: {epochs}\n"
        f"Fine-tuning method: {method}\n"
        f"Precision: {precision}\n"
        f"Sequence length: {seq_len}\n"
        f"GPU memory per GPU: {gpu_capacity} GB\n"
        """
        "Estimate the required GPU memory (in GB), number of GPUs, and total compute (in GPU-hours) for this fine-tuning job, and also for inference (single forward pass per batch).\n"
        "Respond ONLY in the following JSON format: {\"memory_gb\": <float>, \"gpu_hours\": <float>, \"inf_memory_gb\": <float>, \"inf_gpu_hours\": <float>, \"gpus_ft\": <int>, \"flops_ft\": <float>, \"gpus_inf\": <int>, \"flops_inf\": <float>}"
    )
    headers = {
        'Content-Type': 'application/json',
        'X-goog-api-key': GEMINI_API_KEY
    }
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    try:
        response = requests.post(GEMINI_API_URL, headers=headers, data=json.dumps(data), timeout=20)
        response.raise_for_status()
        gemini_text = response.json()['candidates'][0]['content']['parts'][0]['text']
        # Extract JSON from Gemini's response
        json_start = gemini_text.find('{')
        json_end = gemini_text.rfind('}') + 1
        if json_start != -1 and json_end != -1:
            result_json = gemini_text[json_start:json_end]
            return json.loads(result_json)
        else:
            return {'error': 'Invalid JSON from Gemini'}
    except Exception as e:
        return {'error': str(e)}

TEMPLATE = """
<!doctype html>
<html lang=\"en\" data-bs-theme=\"dark\">
<head>
    <meta charset=\"utf-8\">
    <title>LLM Resource Calculator</title>
    <link href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css\" rel=\"stylesheet\">
    <style>
        body { background-color: #121212; color: #e0e0e0; }
        .card { border-radius: 16px; background-color: #1e1e1e; box-shadow: 0 4px 12px rgba(0,0,0,0.6); }
        h2, h4 { font-weight: 600; }
        label { font-weight: 500; margin-top: 10px; }
        .result-card { border-left: 5px solid #0d6efd; }
        .btn-primary { background-color: #0d6efd; border: none; }
        .btn-primary:hover { background-color: #0b5ed7; }
        .form-control, .form-select { background-color: #2a2a2a; border: 1px solid #444; color: #e0e0e0; }
        .form-control:focus, .form-select:focus { background-color: #333; border-color: #0d6efd; color: #fff; }
        .list-group-item { background-color: transparent; border-color: #333; color: #e0e0e0; }
        .inline-loader { display: none; vertical-align: middle; margin-left: 10px; }
        .show-inline-loader { display: inline-block !important; }
    </style>
</head>
<body>
    <div class=\"container py-5\">
        <div class=\"card p-4\">
            <h2 class=\"mb-4\">LLM Resource Calculator</h2>
            <form method=\"post\" class=\"row g-3\" id=\"calc-form\">
                <div class=\"col-md-6\">
                    <label>Number of Parameters</label>
                    <input type=\"text\" class=\"form-control\" name=\"params\" placeholder=\"e.g. 7B, 750M, 7e9\" value=\"{{ form_data.params if form_data else '' }}\" required>
                </div>
                <div class=\"col-md-6\">
                    <label>Dataset Size (GB)</label>
                    <input type=\"number\" step=\"0.01\" min=\"0\" class=\"form-control\" name=\"dataset_size_gb\" value=\"{{ form_data.dataset_size_gb if form_data else '' }}\" required>
                </div>
                <div class=\"col-md-6\">
                    <label>Batch Size</label>
                    <select name=\"batch_size\" class=\"form-select\">
                        {% for val in [1, 2, 4, 8, 16, 32, 64] %}
                        <option value=\"{{ val }}\" {% if form_data and form_data.batch_size == val|string %}selected{% endif %}>{{ val }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class=\"col-md-6\">
                    <label>Epochs</label>
                    <select name=\"epochs\" class=\"form-select\">
                        {% for val in [1, 2, 3, 5, 10, 20, 50] %}
                        <option value=\"{{ val }}\" {% if form_data and form_data.epochs == val|string %}selected{% endif %}>{{ val }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class=\"col-md-6\">
                    <label>Fine-tuning Method</label>
                    <select name=\"method\" class=\"form-select\">
                        <option value=\"full\" {% if form_data and form_data.method == 'full' %}selected{% endif %}>Full Fine-tuning</option>
                        <option value=\"lora\" {% if form_data and form_data.method == 'lora' %}selected{% endif %}>LoRA</option>
                        <option value=\"qlora\" {% if form_data and form_data.method == 'qlora' %}selected{% endif %}>QLoRA</option>
                    </select>
                </div>
                <div class=\"col-md-6\">
                    <label>Precision</label>
                    <select name=\"precision\" class=\"form-select\">
                        <option value=\"fp16\" {% if form_data and form_data.precision == 'fp16' %}selected{% endif %}>FP16 / BF16</option>
                        <option value=\"fp32\" {% if form_data and form_data.precision == 'fp32' %}selected{% endif %}>FP32</option>
                        <option value=\"int8\" {% if form_data and form_data.precision == 'int8' %}selected{% endif %}>8-bit</option>
                        <option value=\"int4\" {% if form_data and form_data.precision == 'int4' %}selected{% endif %}>4-bit</option>
                    </select>
                </div>
                <div class=\"col-md-6\">
                    <label>Sequence Length (tokens)</label>
                    <select name=\"seq_len\" class=\"form-select\">
                        {% for val in [512, 1024, 2048, 4096, 8192, 16384] %}
                        <option value=\"{{ val }}\" {% if form_data and form_data.seq_len == val|string %}selected{% endif %}>{{ val }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class=\"col-md-6\">
                    <label>GPU Memory Capacity (GB per GPU)</label>
                    <select name=\"gpu_capacity\" class=\"form-select\">
                        {% for val in [16, 24, 32, 40, 48, 80] %}
                        <option value=\"{{ val }}\" {% if form_data and form_data.gpu_capacity == val|string %}selected{% endif %}>{{ val }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class=\"col-md-6\">
                    <label>Calculation Method</label>
                    <select name=\"calculation_method\" class=\"form-select\">
                        <option value=\"local\" {% if form_data and form_data.calculation_method == 'local' %}selected{% endif %}>Local Estimate</option>
                        <option value=\"gemini\" {% if form_data and form_data.calculation_method == 'gemini' %}selected{% endif %}>Gemini (LLM-powered)</option>
                    </select>
                </div>
                <div class=\"col-12\" style=\"display: flex; align-items: center;\">
                    <button type=\"submit\" class=\"btn btn-primary px-4\" id=\"calc-btn\">Calculate</button>
                    <span class=\"inline-loader\" id=\"inline-loader\">
                        <span class=\"spinner-border spinner-border-sm text-primary\" role=\"status\" aria-hidden=\"true\"></span>
                        <span class=\"visually-hidden\">Loading...</span>
                    </span>
                </div>
            </form>
        </div>
        {% if result %}
        <div class=\"card p-4 mt-4 result-card\">
            <h4>Fine-tuning Requirements</h4>
            <ul class=\"list-group list-group-flush\">
                {% if result.error %}
                    <li class=\"list-group-item text-danger\"><b>Error:</b> {{ result.error }}</li>
                {% else %}
                    <li class=\"list-group-item\"><b>Total GPU Memory Needed:</b> {{ result.memory_gb }} GB</li>
                    <li class=\"list-group-item\"><b>GPUs Required:</b> {{ result.gpus_ft }}</li>
                    <li class=\"list-group-item\"><b>Compute per token:</b> {{ result.flops_ft | scientific }} FLOPs</li>
                {% endif %}
            </ul>
        </div>
        <div class=\"card p-4 mt-4 result-card\">
            <h4>Inference Requirements</h4>
            <ul class=\"list-group list-group-flush\">
                {% if result.error %}
                    <li class=\"list-group-item text-danger\"><b>Error:</b> {{ result.error }}</li>
                {% else %}
                    <li class=\"list-group-item\"><b>GPU Memory per Batch:</b> {{ result.inf_memory_gb }} GB</li>
                    <li class=\"list-group-item\"><b>GPUs Required:</b> {{ result.gpus_inf }}</li>
                    <li class=\"list-group-item\"><b>Compute per forward pass:</b> {{ result.flops_inf | scientific }} FLOPs</li>
                {% endif %}
            </ul>
        </div>
        {% endif %}
    </div>
    <script>
        const form = document.getElementById('calc-form');
        const loader = document.getElementById('inline-loader');
        if (form && loader) {
            form.addEventListener('submit', function() {
                loader.classList.add('show-inline-loader');
            });
        }
    </script>
</body>
</html>
"""

@app.template_filter('scientific')
def scientific_notation(value):
    return "{:.2e}".format(value)

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    form_data = None
    if request.method == 'POST':
        try:
            form_data = request.form
            params = parse_params(form_data['params'])
            dataset_size_gb = float(form_data['dataset_size_gb'])
            batch_size = int(form_data['batch_size'])
            epochs = int(form_data['epochs'])
            method = form_data['method']
            precision = form_data['precision']
            seq_len = int(form_data['seq_len'])
            gpu_capacity = int(form_data['gpu_capacity'])
            calculation_method = form_data.get('calculation_method', 'local')
            if calculation_method == 'gemini':
                result = estimate_resources_gemini(params, dataset_size_gb, batch_size, epochs, method, precision, seq_len, gpu_capacity)
            else:
                result = estimate_resources_local(params, dataset_size_gb, batch_size, epochs, method, precision, seq_len, gpu_capacity)
        except Exception as e:
            result = {'error': str(e)}
    return render_template_string(TEMPLATE, result=result, form_data=request.form if request.method == 'POST' else None)

if __name__ == '__main__':
    app.run(debug=True)
