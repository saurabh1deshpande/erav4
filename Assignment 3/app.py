from flask import Flask, render_template_string, request
import requests
import json

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
def params_to_gb(params: float) -> float:
    return params * 2 / 1e9

# Simple local estimation logic (placeholder)
def estimate_resources_local(params, dataset_size_gb, batch_size, epochs):
    model_size_gb = params_to_gb(params)
    # Fine-tuning
    memory_required_gb = model_size_gb * 2 + batch_size * 0.01
    compute_required_gpu_hours = dataset_size_gb * epochs * 0.5 / batch_size
    # Inference (simplified)
    inf_memory_gb = model_size_gb + batch_size * 0.005
    inf_compute_gpu_hours = dataset_size_gb * 0.1 / batch_size
    return {
        'memory_gb': round(memory_required_gb, 2),
        'gpu_hours': round(compute_required_gpu_hours, 2),
        'inf_memory_gb': round(inf_memory_gb, 2),
        'inf_gpu_hours': round(inf_compute_gpu_hours, 2)
    }

def estimate_resources_gemini(params, dataset_size_gb, batch_size, epochs):
    model_size_gb = params_to_gb(params)
    prompt = (
        f"""
        Given the following parameters for fine-tuning a large language model (LLM):\n"
        f"Number of parameters: {params:.0f}\n"
        f"Model size: {model_size_gb:.2f} GB (FP16)\n"
        f"Dataset size: {dataset_size_gb} GB\n"
        f"Batch size: {batch_size}\n"
        f"Epochs: {epochs}\n"
        """
        "Estimate the required GPU memory (in GB) and total compute (in GPU-hours) for this fine-tuning job, and also for inference (single forward pass per batch).\n"
        "Respond ONLY in the following JSON format: {\"memory_gb\": <float>, \"gpu_hours\": <float>, \"inf_memory_gb\": <float>, \"inf_gpu_hours\": <float>}"
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
        .loader-container { display: none; justify-content: center; align-items: center; margin-top: 24px; }
        .show-loader { display: flex !important; }
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
                    <label>Calculation Method</label>
                    <select name=\"method\" class=\"form-select\">
                        <option value=\"local\" {% if form_data and form_data.method == 'local' %}selected{% endif %}>Local Estimate</option>
                        <option value=\"gemini\" {% if form_data and form_data.method == 'gemini' %}selected{% endif %}>Gemini (LLM-powered)</option>
                    </select>
                </div>
                <div class=\"col-12\">
                    <button type=\"submit\" class=\"btn btn-primary px-4\">Calculate</button>
                </div>
            </form>
            <div class=\"loader-container\" id=\"loader\">
                <div class=\"spinner-border text-primary\" role=\"status\" style=\"width: 3rem; height: 3rem;\">
                  <span class=\"visually-hidden\">Loading...</span>
                </div>
                <span class=\"ms-3\">Processing...</span>
            </div>
        </div>
        {% if result %}
        <div class=\"card p-4 mt-4 result-card\">
            <h4>Fine-tuning Requirements</h4>
            <ul class=\"list-group list-group-flush\">
                {% if result.error %}
                    <li class=\"list-group-item text-danger\"><b>Error:</b> {{ result.error }}</li>
                {% else %}
                    <li class=\"list-group-item\"><b>Estimated Memory Required:</b> {{ result.memory_gb }} GB</li>
                    <li class=\"list-group-item\"><b>Estimated Compute Required:</b> {{ result.gpu_hours }} GPU-hours</li>
                {% endif %}
            </ul>
        </div>
        <div class=\"card p-4 mt-4 result-card\">
            <h4>Inference Requirements</h4>
            <ul class=\"list-group list-group-flush\">
                {% if result.error %}
                    <li class=\"list-group-item text-danger\"><b>Error:</b> {{ result.error }}</li>
                {% else %}
                    <li class=\"list-group-item\"><b>Estimated Memory Required:</b> {{ result.inf_memory_gb }} GB</li>
                    <li class=\"list-group-item\"><b>Estimated Compute Required:</b> {{ result.inf_gpu_hours }} GPU-hours</li>
                {% endif %}
            </ul>
        </div>
        {% endif %}
    </div>
    <script>
        const form = document.getElementById('calc-form');
        const loader = document.getElementById('loader');
        if (form && loader) {
            form.addEventListener('submit', function() {
                loader.classList.add('show-loader');
            });
        }
    </script>
</body>
</html>
"""

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
            if method == 'gemini':
                result = estimate_resources_gemini(params, dataset_size_gb, batch_size, epochs)
            else:
                result = estimate_resources_local(params, dataset_size_gb, batch_size, epochs)
        except Exception as e:
            result = {'error': str(e)}
    return render_template_string(TEMPLATE, result=result, form_data=request.form if request.method == 'POST' else None)

if __name__ == '__main__':
    app.run(debug=True)
