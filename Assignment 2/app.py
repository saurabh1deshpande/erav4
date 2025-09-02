from flask import Flask, render_template_string, request
import math

app = Flask(__name__)

# --- Helper to parse model size like "7B", "350M" ---
def parse_params(val: str) -> float:
    val = val.strip().upper()
    if val.endswith("B"):
        return float(val[:-1]) * 1e9
    elif val.endswith("M"):
        return float(val[:-1]) * 1e6
    else:
        return float(val)

# --- HTML Template (Dark Professional Theme) ---
TEMPLATE = """
<!doctype html>
<html lang="en" data-bs-theme="dark">
<head>
    <meta charset="utf-8">
    <title>LLM Resource Calculator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
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
    </style>
</head>
<body>
    <div class="container py-5">
        <div class="card p-4">
            <h2 class="mb-4">LLM Resource Calculator</h2>
            <form method="post" class="row g-3">
                <div class="col-md-6">
                    <label>Model Parameters</label>
                    <input type="text" class="form-control" name="params" 
                           placeholder="e.g. 7B, 350M, 7e9" 
                           value="{{ form_data.params if form_data else '' }}" required>
                </div>
                <div class="col-md-6">
                    <label>Fine-tuning Method</label>
                    <select name="method" class="form-select">
                        <option value="full"  {% if form_data and form_data.method == 'full' %}selected{% endif %}>Full Fine-tuning</option>
                        <option value="lora"  {% if form_data and form_data.method == 'lora' %}selected{% endif %}>LoRA</option>
                        <option value="qlora" {% if form_data and form_data.method == 'qlora' %}selected{% endif %}>QLoRA</option>
                    </select>
                </div>
                <div class="col-md-6">
                    <label>Precision</label>
                    <select name="precision" class="form-select">
                        <option value="fp16" {% if form_data and form_data.precision == 'fp16' %}selected{% endif %}>FP16 / BF16</option>
                        <option value="fp32" {% if form_data and form_data.precision == 'fp32' %}selected{% endif %}>FP32</option>
                        <option value="int8" {% if form_data and form_data.precision == 'int8' %}selected{% endif %}>8-bit</option>
                        <option value="int4" {% if form_data and form_data.precision == 'int4' %}selected{% endif %}>4-bit</option>
                    </select>
                </div>
                <div class="col-md-6">
                    <label>Sequence Length (tokens)</label>
                    <input type="number" class="form-control" name="seq_len" value="{{ form_data.seq_len if form_data else 2048 }}" required>
                </div>
                <div class="col-md-6">
                    <label>Batch Size</label>
                    <input type="number" class="form-control" name="batch_size" value="{{ form_data.batch_size if form_data else 4 }}" required>
                </div>
                <div class="col-md-6">
                    <label>GPU Memory Capacity (GB per GPU)</label>
                    <input type="number" class="form-control" name="gpu_capacity" value="{{ form_data.gpu_capacity if form_data else 80 }}" required>
                </div>
                <div class="col-12">
                    <button type="submit" class="btn btn-primary px-4">Calculate</button>
                </div>
            </form>
        </div>

        {% if result %}
        <div class="card p-4 mt-4 result-card">
            <h4>Fine-tuning Requirements</h4>
            <ul class="list-group list-group-flush">
                <li class="list-group-item"><b>Total GPU Memory Needed:</b> {{ result['fine_tune']['total_mem'] }} GB</li>
                <li class="list-group-item"><b>GPUs Required:</b> {{ result['fine_tune']['gpus'] }}</li>
                <li class="list-group-item"><b>Compute per token:</b> {{ result['fine_tune']['flops'] | scientific }} FLOPs</li>
            </ul>
        </div>

        <div class="card p-4 mt-4 result-card">
            <h4>Inference Requirements</h4>
            <ul class="list-group list-group-flush">
                <li class="list-group-item"><b>GPU Memory per Batch:</b> {{ result['inference']['total_mem'] }} GB</li>
                <li class="list-group-item"><b>GPUs Required:</b> {{ result['inference']['gpus'] }}</li>
                <li class="list-group-item"><b>Compute per forward pass:</b> {{ result['inference']['flops'] | scientific }} FLOPs</li>
            </ul>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.template_filter('scientific')
def scientific_notation(value):
    return "{:.2e}".format(value)

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    form_data = None

    if request.method == "POST":
        form_data = request.form
        params = parse_params(form_data["params"])
        method = form_data["method"]
        precision = form_data["precision"]
        seq_len = int(form_data["seq_len"])
        batch_size = int(form_data["batch_size"])
        gpu_capacity = int(form_data["gpu_capacity"])

        # Bytes per param
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

        # === Fine-tuning ===
        param_mem = (params * bytes_per_param) / 1e9
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

        result = {
            "fine_tune": {
                "total_mem": round(total_mem_ft, 2),
                "gpus": gpus_ft,
                "flops": flops_ft
            },
            "inference": {
                "total_mem": round(total_mem_inf, 2),
                "gpus": gpus_inf,
                "flops": flops_inf
            }
        }

    return render_template_string(TEMPLATE, result=result, form_data=form_data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
